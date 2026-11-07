"""Nexus Press pipeline.

Each run: reads RSS feeds, picks fresh stories (priority to categories that have < 6 articles),
writes an original 800-1500 word article with the OpenAI API, generates a unique illustration
with the OpenAI image API, compresses it to WebP, updates articles.json and rebuilds the site.

Env: OPENAI_API_KEY (required), OPENAI_MODEL, OPENAI_IMAGE_MODEL, MAX_PER_RUN (default 2),
     MIN_PER_CATEGORY (default 6), KEEP_PER_CATEGORY (default 15)
Run `python fetch_news.py` locally or let GitHub Actions run it every hour.
"""
import base64
import hashlib
import io
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import build_site

ROOT = Path(__file__).parent
API = "https://api.openai.com/v1"
KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL") or "gpt-4.1"
IMG_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN", "2"))
MIN_PER_CAT = int(os.getenv("MIN_PER_CATEGORY", "6"))
KEEP = int(os.getenv("KEEP_PER_CATEGORY", "15"))
MIN_WORDS, MAX_WORDS = 800, 1500

FEEDS = {
    "ar_local": [("Hespress", "https://www.hespress.com/feed"), ("Hespress English", "https://en.hespress.com/feed")],
    "ar_world": [("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"), ("The Guardian", "https://www.theguardian.com/world/rss")],
    "ar_economy": [("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"), ("The Guardian Business", "https://www.theguardian.com/business/rss")],
    "ar_tech": [("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"), ("The Guardian Technology", "https://www.theguardian.com/technology/rss")],
    "ar_sports": [("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"), ("The Guardian Sport", "https://www.theguardian.com/sport/rss")],
    "ar_arts": [("BBC Arts", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"), ("The Guardian Culture", "https://www.theguardian.com/culture/rss")],
}

SYSTEM = """أنت صحفي عربي محترف بخبرة طويلة في غرف الأخبار. تكتب مقالات إخبارية أصلية بأسلوب صحفي رصين.
القواعد:
- اكتب بصياغتك الخاصة تماماً. لا تنقل جملاً من المصدر ولا تترجمها حرفياً.
- استخدم فقط الوقائع والأرقام والأسماء الواردة في المواد المقدمة، ويمكنك إضافة خلفية عامة معروفة ومؤكدة فقط.
- لا تخترع اقتباسات ولا أرقاماً ولا أسماء ولا تواريخ. إن لم تكن متأكداً فاحذف المعلومة.
- الفقرة الأولى «هوك» جذاب يشدّ القارئ (مشهد، مفارقة، سؤال أو معلومة لافتة) ثم يدخل في صلب الخبر.
- بنية المقال: هوك، ثم الخبر الأساسي، ثم الخلفية والسياق، ثم الأطراف والتصريحات الواردة في المصدر، ثم التحليل والدلالات، ثم ما ينتظر القارئ لاحقاً.
- الطول بين 900 و1300 كلمة، بفقرات متوازنة (3 إلى 5 جمل لكل فقرة). يمكن استخدام عناوين فرعية على شكل فقرة قصيرة تبدأ بـ '## '.
- لا تخاطب القارئ بعبارات مثل «بصفتي». لا تنسب المقال لشخص حقيقي.
- أعد JSON فقط بالشكل: {"title": "...", "summary": "جملتان كحد أقصى", "image_prompt": "English prompt", "body": ["فقرة", "فقرة", ...]}
- image_prompt: وصف إنجليزي لمشهد توضيحي يدل على موضوع المقال، بدون نصوص أو شعارات أو وجوه أشخاص حقيقيين أو شخصيات عامة."""


def http(url, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "NexusPressBot/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def openai(path, payload):
    return json.loads(http(f"{API}/{path}", json.dumps(payload).encode(),
                           {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}, timeout=300))


def read_feed(name, url):
    out = []
    try:
        root = ET.fromstring(http(url, timeout=30))
    except Exception as ex:
        print("feed failed", name, ex)
        return out
    for it in root.iter("item"):
        t, l = it.findtext("title"), it.findtext("link")
        if t and l:
            desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
            out.append({"publisher": name, "title": t.strip(), "url": l.strip(), "desc": re.sub(r"\s+", " ", desc).strip()})
    return out


def page_text(url):
    try:
        raw = http(url, timeout=30).decode("utf-8", "ignore")
    except Exception:
        return ""
    raw = re.sub(r"(?is)<(script|style|nav|footer|header|aside).*?</\1>", " ", raw)
    paras = [re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", raw)]
    return " ".join(p for p in paras if len(p) > 60)[:6000]


def words(paras):
    return len(re.findall(r"\S+", " ".join(paras)))


def write_article(cat_name, sources):
    material = "\n\n".join(f"[{s['publisher']}] {s['title']}\n{s['text'] or s['desc']}" for s in sources)
    user = f"القسم: {cat_name}\nالمواد المرجعية:\n{material}\n\nاكتب المقال الآن."
    art = None
    for attempt in range(3):
        res = openai("chat/completions", {"model": MODEL, "response_format": {"type": "json_object"}, "temperature": 0.7,
                                          "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]})
        art = json.loads(res["choices"][0]["message"]["content"])
        n = words(art["body"])
        if MIN_WORDS <= n <= MAX_WORDS:
            return art
        print(f"word count {n} out of range, retry {attempt + 1}")
        user += f"\n\nملاحظة: المحاولة السابقة كانت {n} كلمة. المطلوب بين 900 و1300 كلمة."
    return art if art and words(art["body"]) >= MIN_WORDS else None


def make_image(prompt, art_id, cat):
    out = ROOT / "images"
    out.mkdir(exist_ok=True)
    try:
        from PIL import Image
        full = ("Editorial illustration for a news article, realistic photographic style, no text, no letters, no logos, "
                "no real or recognizable people, no brand names. Scene: " + prompt)
        res = openai("images/generations", {"model": IMG_MODEL, "prompt": full, "size": "1536x1024", "quality": "low", "n": 1})
        img = Image.open(io.BytesIO(base64.b64decode(res["data"][0]["b64_json"]))).convert("RGB")
        img.thumbnail((1000, 1000))
        path = out / f"{art_id}.webp"
        img.save(path, "WEBP", quality=72, method=6)
        return f"images/{path.name}"
    except Exception as ex:
        print("image failed, using fallback:", ex)
        colors = {"ar_local": "#0b3c7a", "ar_world": "#0369a1", "ar_economy": "#047857",
                  "ar_tech": "#6d28d9", "ar_sports": "#b45309", "ar_arts": "#be185d"}
        svg = out / f"{art_id}.svg"
        svg.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{colors[cat]}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs>'
            f'<rect width="1000" height="560" fill="url(#g)"/><circle cx="780" cy="160" r="210" fill="#fff" opacity=".07"/>'
            f'<circle cx="200" cy="470" r="260" fill="#fff" opacity=".06"/></svg>', encoding="utf-8")
        return f"images/{svg.name}"


def tokens(t):
    return {w for w in re.findall(r"[A-Za-z\u0600-\u06FF]{4,}", t.lower())}


def main():
    if not KEY:
        print("OPENAI_API_KEY missing: rebuilding site only.")
        build_site.build()
        return
    jf, sf = ROOT / "articles.json", ROOT / "news-state.json"
    data = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    arts = {k: data.get("articles", {}).get(k, []) for k in build_site.CATEGORIES}
    used = set(json.loads(sf.read_text(encoding="utf-8")).get("used", [])) if sf.exists() else set()

    made, stuck = 0, set()
    while made < MAX_PER_RUN and len(stuck) < len(arts):
        # neediest category first; once all have >= MIN_PER_CAT, rotate to the one with the oldest latest article
        cat = min((k for k in arts if k not in stuck),
                  key=lambda k: (len(arts[k]) >= MIN_PER_CAT, len(arts[k]), arts[k][0]["date"] if arts[k] else ""))
        pool = [i for n, u in FEEDS[cat] for i in read_feed(n, u) if i["url"] not in used]
        if not pool:
            stuck.add(cat)
            continue
        main_item = pool[0]
        tk = tokens(main_item["title"])
        extra = next((i for i in pool[1:] if i["publisher"] != main_item["publisher"] and len(tk & tokens(i["title"])) >= 2), None)
        chosen = [main_item] + ([extra] if extra else [])
        used.update(i["url"] for i in chosen)
        for s in chosen:
            s["text"] = page_text(s["url"])
        try:
            art = write_article(build_site.CATEGORIES[cat], chosen)
        except Exception as ex:
            print("generation failed:", ex)
            stuck.add(cat)
            continue
        if not art:
            continue
        aid = f"{cat}-{datetime.now(timezone.utc):%Y%m%d%H%M}-{hashlib.md5(main_item['url'].encode()).hexdigest()[:6]}"
        arts[cat].insert(0, {
            "id": aid, "title": art["title"].strip(), "summary": art["summary"].strip(),
            "content": "\n\n".join(p.strip() for p in art["body"]),
            "image": make_image(art.get("image_prompt", art["title"]), aid, cat), "image_alt": art["title"].strip(),
            "date": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in chosen]})
        made += 1
        print("published:", art["title"])

    for cat in arts:
        for old in arts[cat][KEEP:]:
            (ROOT / old["image"]).unlink(missing_ok=True)
        arts[cat] = arts[cat][:KEEP]
    jf.write_text(json.dumps({"categories": build_site.CATEGORIES, "articles": arts}, ensure_ascii=False, indent=1), encoding="utf-8")
    sf.write_text(json.dumps({"used": sorted(used)[-3000:]}), encoding="utf-8")
    build_site.build()


if __name__ == "__main__":
    main()
