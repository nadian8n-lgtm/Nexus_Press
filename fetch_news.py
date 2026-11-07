"""Nexus Press pipeline (Google Gemini API / Google AI Studio key).

Each run: reads RSS feeds, picks fresh stories (categories with < 6 articles first),
writes an ORIGINAL 800-1500 word article with Gemini, checks it against the sources for copied wording,
generates a unique illustration with a Gemini image model, compresses it to WebP,
updates articles.json and rebuilds the whole site.

Env:
  GEMINI_API_KEY      (required)  key from https://aistudio.google.com/apikey
  GEMINI_TEXT_MODEL   default gemini-2.5-flash
  GEMINI_IMAGE_MODEL  default gemini-2.5-flash-image   (needs a billing-enabled project)
  MAX_PER_RUN (2) | MIN_PER_CATEGORY (6) | KEEP_PER_CATEGORY (15) | PAUSE_SECONDS (8)
"""
import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import build_site

ROOT = Path(__file__).parent
API = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.getenv("GEMINI_API_KEY", "")
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL") or "gemini-2.5-flash"
IMG_MODEL = os.getenv("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image"
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN") or "2")
MIN_PER_CAT = int(os.getenv("MIN_PER_CATEGORY") or "6")
KEEP = int(os.getenv("KEEP_PER_CATEGORY") or "15")
PAUSE = int(os.getenv("PAUSE_SECONDS") or "8")
MIN_WORDS, MAX_WORDS = 800, 1500
MAX_OVERLAP = 0.05  # max share of 5-word sequences allowed to match the source text

FEEDS = {
    "ar_local": [("Hespress", "https://www.hespress.com/feed"), ("Hespress English", "https://en.hespress.com/feed")],
    "ar_world": [("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"), ("The Guardian", "https://www.theguardian.com/world/rss")],
    "ar_economy": [("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"), ("The Guardian Business", "https://www.theguardian.com/business/rss")],
    "ar_tech": [("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"), ("The Guardian Technology", "https://www.theguardian.com/technology/rss")],
    "ar_sports": [("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"), ("The Guardian Sport", "https://www.theguardian.com/sport/rss")],
    "ar_arts": [("BBC Arts", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"), ("The Guardian Culture", "https://www.theguardian.com/culture/rss")],
}
ICONS = {"ar_local": "🇲🇦", "ar_world": "🌍", "ar_economy": "💹", "ar_tech": "💻", "ar_sports": "⚽", "ar_arts": "🎭"}
COLORS = {"ar_local": "#0b3c7a", "ar_world": "#0369a1", "ar_economy": "#047857",
          "ar_tech": "#6d28d9", "ar_sports": "#b45309", "ar_arts": "#be185d"}

SYSTEM = """أنت صحفي عربي محترف بخبرة طويلة في غرف الأخبار، تكتب مقالات إخبارية أصلية بأسلوب صحفي رصين وسلس.
القواعد:
- اكتب بصياغتك الخاصة تماماً. لا تنقل جملاً من المصدر ولا تترجمها حرفياً ولا تحاكِ ترتيب فقراته.
- استخدم فقط الوقائع والأرقام والأسماء الواردة في المواد المقدمة، ويمكنك إضافة خلفية عامة معروفة ومؤكدة فقط.
- لا تخترع اقتباسات ولا أرقاماً ولا أسماء ولا تواريخ ولا تصريحات. إن لم تكن متأكداً فاحذف المعلومة.
- الفقرة الأولى «هوك» جذاب يشدّ القارئ (مشهد، مفارقة، سؤال أو معلومة لافتة) ثم يدخل في صلب الخبر.
- بنية المقال: هوك، ثم الخبر الأساسي، ثم الخلفية والسياق، ثم الأطراف والمواقف الواردة في المصدر، ثم التحليل والدلالات، ثم ما ينتظر القارئ لاحقاً.
- الطول بين 900 و1300 كلمة، بفقرات متوازنة (3 إلى 5 جمل لكل فقرة). يمكن استخدام عناوين فرعية على شكل فقرة قصيرة تبدأ بـ '## '.
- لا تخاطب القارئ بعبارات مثل «بصفتي». لا تنسب المقال لشخص حقيقي.
- أعد JSON فقط بالشكل: {"title": "...", "summary": "جملتان كحد أقصى", "image_prompt": "English prompt", "body": ["فقرة", "فقرة", ...]}
- image_prompt: وصف إنجليزي لمشهد توضيحي يدل على موضوع المقال، بدون نصوص أو شعارات أو وجوه أشخاص حقيقيين أو شخصيات عامة."""

image_ok = True  # switched off for the rest of the run if the image API refuses (quota / billing)


def http(url, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "NexusPressBot/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def gemini(model, payload, tries=4):
    url = f"{API}/models/{model}:generateContent"
    for n in range(1, tries + 1):
        try:
            return json.loads(http(url, json.dumps(payload).encode(),
                                   {"x-goog-api-key": KEY, "Content-Type": "application/json"}, timeout=300))
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", "ignore")[:500]
            if ex.code in (429, 500, 503) and n < tries and "limit: 0" not in body:
                wait = 30 * n
                print(f"Gemini {ex.code} (model {model}), retrying in {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini API error {ex.code} (model {model}): {body}")
    raise RuntimeError("Gemini API: retries exhausted")


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


def overlap(paras, sources, n=5):
    """Share of the article's n-word sequences that also appear in the source text (plagiarism guard)."""
    def grams(text):
        w = re.findall(r"\w+", text.lower())
        return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
    mine = grams(" ".join(paras))
    if not mine:
        return 0.0
    theirs = set()
    for s in sources:
        theirs |= grams((s.get("text") or "") + " " + s.get("desc", ""))
    return len(mine & theirs) / len(mine)


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    return json.loads(text)


def write_article(cat_name, sources):
    material = "\n\n".join(f"[{s['publisher']}] {s['title']}\n{s['text'] or s['desc']}" for s in sources)
    user = f"القسم: {cat_name}\nالمواد المرجعية:\n{material}\n\nاكتب المقال الآن."
    best = None
    for attempt in range(3):
        res = gemini(TEXT_MODEL, {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json", "maxOutputTokens": 16384}})
        cands = res.get("candidates") or []
        if not cands or "content" not in cands[0]:
            print("empty/blocked response:", json.dumps(res.get("promptFeedback", res))[:300])
            continue
        text = "".join(p.get("text", "") for p in cands[0]["content"].get("parts", []) if not p.get("thought"))
        try:
            art = parse_json(text)
            body = [str(p) for p in art["body"]]
        except Exception as ex:
            print("bad JSON from model, retrying:", ex)
            continue
        n, ov = words(body), overlap(body, sources)
        print(f"attempt {attempt + 1}: {n} words, overlap {ov:.1%}")
        if MIN_WORDS <= n <= MAX_WORDS and ov <= MAX_OVERLAP:
            art["body"] = body
            return art
        if n >= MIN_WORDS and ov <= MAX_OVERLAP:
            best = {**art, "body": body}
        user += (f"\n\nملاحظة: المحاولة السابقة كانت {n} كلمة وتشابه {ov:.0%} مع المصدر. "
                 "المطلوب بين 900 و1300 كلمة وبصياغة جديدة كلياً بعيدة عن عبارات المصدر.")
    return best


def make_image(prompt, art_id, cat):
    global image_ok
    out = ROOT / "images"
    out.mkdir(exist_ok=True)
    if image_ok:
        try:
            from PIL import Image
            full = ("Create a realistic editorial photograph-style illustration for a news article. "
                    "No text, no letters, no logos, no brand names, no flags with text, no real or recognizable people. "
                    "Scene: " + prompt)
            cfg = {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}
            try:
                res = gemini(IMG_MODEL, {"contents": [{"parts": [{"text": full}]}], "generationConfig": cfg}, tries=2)
            except RuntimeError as ex:
                if " 400 " not in str(ex):
                    raise
                cfg.pop("imageConfig")
                res = gemini(IMG_MODEL, {"contents": [{"parts": [{"text": full}]}], "generationConfig": cfg}, tries=2)
            data = None
            for p in (res.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                d = p.get("inlineData") or p.get("inline_data")
                if d and not p.get("thought"):
                    data = d["data"]
            if not data:
                raise RuntimeError("no image in response: " + json.dumps(res)[:300])
            img = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
            img.thumbnail((1000, 1000))
            path = out / f"{art_id}.webp"
            img.save(path, "WEBP", quality=72, method=6)
            return f"images/{path.name}"
        except Exception as ex:
            print("image failed, using fallback:", ex)
            if any(k in str(ex) for k in (" 429 ", "RESOURCE_EXHAUSTED", " 403 ", " 404 ")):
                image_ok = False
                print("-> image generation disabled for this run (needs a billing-enabled Google project or a valid GEMINI_IMAGE_MODEL).")
    svg = out / f"{art_id}.svg"
    svg.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{COLORS[cat]}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs>'
        f'<rect width="1000" height="560" fill="url(#g)"/><circle cx="780" cy="160" r="210" fill="#fff" opacity=".07"/>'
        f'<circle cx="200" cy="470" r="260" fill="#fff" opacity=".06"/>'
        f'<text x="500" y="330" font-size="190" text-anchor="middle" opacity=".9">{ICONS[cat]}</text></svg>', encoding="utf-8")
    return f"images/{svg.name}"


def tokens(t):
    return {w for w in re.findall(r"[A-Za-z\u0600-\u06FF]{4,}", t.lower())}


def main():
    if not KEY:
        build_site.build()
        raise SystemExit("ERROR: GEMINI_API_KEY is empty. Create a key at https://aistudio.google.com/apikey and add it in "
                         "GitHub: Settings > Secrets and variables > Actions > Secrets (exact name GEMINI_API_KEY).")
    jf, sf = ROOT / "articles.json", ROOT / "news-state.json"
    data = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    arts = {k: data.get("articles", {}).get(k, []) for k in build_site.CATEGORIES}
    used = set(json.loads(sf.read_text(encoding="utf-8")).get("used", [])) if sf.exists() else set()

    made, stuck, errors = 0, set(), []
    while made < MAX_PER_RUN and len(stuck) < len(arts):
        # neediest category first; once all have >= MIN_PER_CAT, rotate to the one with the oldest latest article
        cat = min((k for k in arts if k not in stuck),
                  key=lambda k: (len(arts[k]) >= MIN_PER_CAT, len(arts[k]), arts[k][0]["date"] if arts[k] else ""))
        pool = [i for n, u in FEEDS[cat] for i in read_feed(n, u) if i["url"] not in used]
        if not pool:
            print("no fresh stories for", cat)
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
            errors.append(str(ex))
            stuck.add(cat)
            continue
        if not art:
            print("article rejected (length / similarity), skipping story")
            continue
        aid = f"{cat}-{datetime.now(timezone.utc):%Y%m%d%H%M}-{hashlib.md5(main_item['url'].encode()).hexdigest()[:6]}"
        arts[cat].insert(0, {
            "id": aid, "title": art["title"].strip(), "summary": art["summary"].strip(),
            "content": "\n\n".join(p.strip() for p in art["body"]),
            "image": make_image(art.get("image_prompt", art["title"]), aid, cat), "image_alt": art["title"].strip(),
            "date": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in chosen]})
        made += 1
        print(f"published ({made}/{MAX_PER_RUN}):", art["title"])
        time.sleep(PAUSE)

    for cat in arts:
        for old in arts[cat][KEEP:]:
            (ROOT / old["image"]).unlink(missing_ok=True)
        arts[cat] = arts[cat][:KEEP]
    jf.write_text(json.dumps({"categories": build_site.CATEGORIES, "articles": arts}, ensure_ascii=False, indent=1), encoding="utf-8")
    sf.write_text(json.dumps({"used": sorted(used)[-3000:]}), encoding="utf-8")
    build_site.build()
    if made == 0 and MAX_PER_RUN > 0:
        raise SystemExit("ERROR: no article was generated.\n" + "\n".join(errors[-3:]) +
                         "\nRead the lines above: 'feed failed', 'generation failed' or 'Gemini API error' show the cause.")


if __name__ == "__main__":
    main()
