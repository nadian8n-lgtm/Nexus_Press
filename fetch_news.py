"""Fetch, de-duplicate, edit, illustrate, and publish fresh sourced news.

RSS titles/descriptions are discovery inputs, not evidence that every claim is true.
The script does not copy publisher article bodies or photos. It publishes only content
that passes basic freshness, corroboration, and similarity checks. Automation cannot
replace reporting, human fact-checking, image-rights review, or legal advice.
"""

import base64
import html
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "news-state.json"
DATA_PATH = ROOT / "news-data.json"
IMAGE_DIR = ROOT / "news-images"
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
MAX_AGE_HOURS = max(1, int(os.getenv("NEWS_MAX_AGE_HOURS", "24")))
MAX_PER_CATEGORY = max(1, int(os.getenv("MAX_ARTICLES_PER_CATEGORY", "2")))
MAX_TOTAL = max(24, int(os.getenv("MAX_TOTAL_ARTICLES", "40")))
GENERATE_AI_IMAGES = os.getenv("GENERATE_AI_IMAGES", "true").lower() == "true"
TIMEOUT = 30
USER_AGENT = "NexusPressNews/1.0 (+https://nadian8n-lgtm.github.io/Nexus_Press/)"

CATEGORIES = {
    "ar_local": "أخبار وطنية",
    "ar_world": "أخبار دولية",
    "ar_economy": "اقتصاد",
    "ar_sports": "رياضة",
    "ar_technology": "تكنولوجيا",
}
FEEDS = [
    {"category": "ar_local", "publisher": "هسبريس", "url": "https://www.hespress.com/feed"},
    {"category": "ar_local", "publisher": "وكالة المغرب العربي للأنباء", "url": "https://www.mapnews.ma/ar/rss.xml"},
    {"category": "ar_local", "publisher": "أخبارنا", "url": "https://www.akhbarona.com/feed/index.rss"},
    {"category": "ar_local", "publisher": "Le Matin", "url": "https://lematin.ma/rssFeed/0"},
    {"category": "ar_world", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/arab-and-world.xml"},
    {"category": "ar_world", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/world.xml"},
    {"category": "ar_world", "publisher": "الجزيرة", "url": "https://www.aljazeera.net/rss/brief/news"},
    {"category": "ar_economy", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/aswaq.xml"},
    {"category": "ar_economy", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/business.xml"},
    {"category": "ar_economy", "publisher": "Le Matin", "url": "https://lematin.ma/rssFeed/4"},
    {"category": "ar_sports", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/sport.xml"},
    {"category": "ar_sports", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/sports.xml"},
    {"category": "ar_sports", "publisher": "الجزيرة", "url": "https://www.aljazeera.net/rss/brief/sport"},
    {"category": "ar_technology", "publisher": "Google News - technology search", "url": "https://news.google.com/rss/search?q=technology+OR+artificial+intelligence+when:1d&hl=ar&gl=MA&ceid=MA:ar"},
    {"category": "ar_technology", "publisher": "Google News - technology Morocco", "url": "https://news.google.com/rss/search?q=technology+Morocco+when:1d&hl=ar&gl=MA&ceid=MA:ar"},
]
STOP_WORDS = set("من في على إلى عن مع هذا هذه ذلك التي الذي حيث بعد قبل بين عبر ضمن لدى كما قد ما لا لم لن إن أن أو ثم هو هي كان تكون يتم قال قالت وأكد وأكدت بحسب وفق حول خلال اليوم أمس مصادر مصدر تقرير أخبار خبر".split())


def clean_text(value):
    value = re.sub(r"<[^>]*>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[\u064b-\u065f\u0670ـ]", "", value)
    value = re.sub(r"[إأآٱ]", "ا", value).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", value)


def tokens(value):
    return {word for word in normalize(value).split() if len(word) > 2 and word not in STOP_WORDS}


def same_event(left, right):
    a = tokens(left["title"] + " " + left["summary"])
    b = tokens(right["title"] + " " + right["summary"])
    return len(a & b) >= 2 and len(a & b) / max(1, len(a | b)) >= 0.14


def entry_date(entry):
    value = entry.get("published_parsed") or entry.get("updated_parsed")
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def fetch_candidates():
    candidates = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    for feed in FEEDS:
        try:
            response = requests.get(feed["url"], timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError("Invalid RSS feed")
            for entry in parsed.entries[:25]:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                parsed_url = urlparse(link)
                published = entry_date(entry)
                if not title or parsed_url.scheme != "https" or not parsed_url.netloc:
                    continue
                if published and published < cutoff:
                    continue
                candidates.append({
                    "category": feed["category"],
                    "categoryLabel": CATEGORIES[feed["category"]],
                    "publisher": feed["publisher"],
                    "domain": parsed_url.netloc.lower().removeprefix("www."),
                    "title": title[:300],
                    "summary": clean_text(entry.get("summary", entry.get("description", "")))[:1000],
                    "url": link,
                    "published": published.isoformat() if published else "",
                })
        except Exception as error:
            print(f"RSS unavailable ({feed['publisher']}): {error}", file=sys.stderr)
    return candidates


def group_candidates(candidates):
    groups = []
    for candidate in sorted(candidates, key=lambda item: item.get("published", ""), reverse=True):
        group = next((items for items in groups if items[0]["category"] == candidate["category"] and any(same_event(candidate, item) for item in items)), None)
        if group is None:
            groups.append([candidate])
        elif candidate["domain"] not in {item["domain"] for item in group}:
            group.append(candidate)
    # Google News is an aggregator; do not treat it as an independent publisher source.
    return [items for items in groups if len({item["domain"] for item in items if "news.google.com" not in item["domain"]}) >= 2]


def similarity(text, reference):
    def shingles(value):
        words = normalize(value).split()
        return {tuple(words[i:i + 5]) for i in range(max(0, len(words) - 4))}
    draft, source = shingles(text), shingles(reference)
    return len(draft & source) / len(draft) if draft and source else 0.0


def generate_article(group):
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY secret is missing")
    evidence = [{"publisher": x["publisher"], "headline": x["title"], "description": x["summary"], "published": x["published"]} for x in group]
    system = (
        "أنت محرر صحفي عربي. استخدم الوقائع المشتركة فقط بين المصادر المقدمة. لا تنسخ أو تترجم أو تعيد تركيب عبارات المصادر. "
        "لا تخترع أي اسم أو رقم أو تصريح أو سبب أو سياق. لا تنسب اقتباسات غير موجودة. اكتب عنواناً جديداً دقيقاً وملخصاً "
        "وثلاث إلى خمس فقرات صحفية عربية متماسكة، كل فقرة معلومة مختلفة بلا تكرار. إذا كانت البيانات غير كافية أعد publish=false. "
        "أخرج JSON صالحاً فقط بمفاتيح publish, title, summary, paragraphs. المخرجات تحرير آلي وليست مراجعة بشرية."
    )
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.3, "response_format": {"type": "json_object"}, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"reports": evidence}, ensure_ascii=False)},
        ]}, timeout=90,
    )
    response.raise_for_status()
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise ValueError("OpenAI returned an empty response")
    result = json.loads(content)
    if result.get("publish") is not True:
        raise ValueError("Insufficient material for a responsibly written story")
    title = clean_text(result.get("title", ""))
    summary = clean_text(result.get("summary", ""))
    paragraphs = result.get("paragraphs", [])
    if not isinstance(paragraphs, list):
        raise ValueError("Invalid article paragraphs")
    paragraphs = [clean_text(p) for p in paragraphs if isinstance(p, str) and clean_text(p)]
    all_text = " ".join([title, summary, *paragraphs])
    source_text = " ".join(x["title"] + " " + x["summary"] for x in group)
    if len(title) < 12 or len(summary) < 35 or len(paragraphs) < 3 or len(" ".join(paragraphs).split()) < 100:
        raise ValueError("Article failed minimum quality checks")
    if similarity(all_text, source_text) > 0.08:
        raise ValueError("Article failed the preliminary originality check")
    return {"title": title, "summary": summary, "paragraphs": paragraphs}


def image_svg(category, title, story_id):
    palette = {"ar_local": ("#0b3c7a", "#e0f2fe"), "ar_world": ("#17365d", "#dbeafe"), "ar_economy": ("#166534", "#dcfce7"), "ar_sports": ("#9a3412", "#ffedd5"), "ar_technology": ("#5b21b6", "#ede9fe")}
    primary, accent = palette[category]
    safe_title = html.escape(title[:70])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" aria-label="رسم تحريري توضيحي، وليس صورة توثيقية"><defs><linearGradient id="g"><stop stop-color="{primary}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs><rect width="1200" height="675" fill="url(#g)"/><circle cx="1000" cy="100" r="220" fill="{accent}" opacity=".18"/><text x="600" y="235" text-anchor="middle" font-family="Tahoma,Arial" font-size="38" fill="{accent}">نكسوس بريس · رسم توضيحي</text><foreignObject x="100" y="275" width="1000" height="250"><div xmlns="http://www.w3.org/1999/xhtml" style="font:bold 36px Tahoma,Arial;color:white;text-align:center;direction:rtl;line-height:1.55">{safe_title}</div></foreignObject></svg>'''


def create_image(category, title, story_id):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / f"{category}-{story_id}.png"
    if GENERATE_AI_IMAGES and API_KEY:
        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-image-1", "size": "1024x1024", "quality": "low", "n": 1,
                     "prompt": f"Create an original editorial illustration for an Arabic newspaper about this topic: {title}. No text, no logos, no real people, no imitation of any existing photograph or artist. Clearly illustrative, not documentary."},
                timeout=120,
            )
            response.raise_for_status()
            image_data = response.json()["data"][0].get("b64_json")
            if image_data:
                path.write_bytes(base64.b64decode(image_data))
                return f"./news-images/{path.name}", "رسم توضيحي مولّد بالذكاء الاصطناعي، وليس صورة توثيقية"
        except Exception as error:
            print(f"AI image generation failed; using original SVG fallback: {error}", file=sys.stderr)
    svg_path = IMAGE_DIR / f"{category}-{story_id}.svg"
    svg_path.write_text(image_svg(category, title, story_id), encoding="utf-8")
    return f"./news-images/{svg_path.name}", "رسم توضيحي أصلي، وليس صورة توثيقية"


def render_article(article):
    title = html.escape(article["title"])
    summary = html.escape(article["summary"])
    paragraphs = "\n".join(f"<p>{html.escape(p)}</p>" for p in article["paragraphs"])
    sources = "\n".join(f'<li><a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(s["publisher"])} — {html.escape(s["title"])}</a></li>' for s in article["sources"])
    canonical = "https://nadian8n-lgtm.github.io/Nexus_Press/" + article["url"].removeprefix("./")
    adsense_client = os.getenv("ADSENSE_CLIENT", "").strip()
    ad_script = f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(adsense_client, quote=True)}" crossorigin="anonymous"></script>' if adsense_client.startswith("ca-pub-") else ""
    comments = f'''<section class="comments" id="comments"><h2>التعليقات</h2><p>التعليقات مستضافة عبر GitHub Discussions. احترم قواعد الحوار.</p><script src="https://utteranc.es/client.js" repo="nadian8n-lgtm/Nexus_Press" issue-term="pathname" label="comments" theme="github-light" crossorigin="anonymous" async></script><noscript><a href="https://github.com/nadian8n-lgtm/Nexus_Press/discussions">شارك رأيك في نقاشات GitHub</a></noscript></section>'''
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | نكسوس بريس</title><meta name="description" content="{summary[:155]}"><link rel="canonical" href="{html.escape(canonical, quote=True)}"><link rel="stylesheet" href="./style.css">{ad_script}</head>
<body><header class="site-header"><div class="container header-inner"><a class="brand" href="./index.html"><img src="./image_MUwSAA.png" alt="شعار نكسوس بريس"><span>نكسوس بريس</span></a><a href="./index.html">الرئيسية</a></div></header>
<nav class="site-nav"><div class="container nav-inner"><a class="nav-link" href="./index.html">الرئيسية</a><a class="nav-link" href="./index.html#comments">الأقسام</a></div></nav>
<main class="container main-content"><article class="post"><span class="badge">{html.escape(article['categoryLabel'])}</span><h1>{title}</h1><p class="card-meta">{html.escape(article['published'])} · إعداد نكسوس بريس</p><img class="article-image" src="{html.escape(article['image'], quote=True)}" alt="{html.escape(article['imageAlt'])}"><p class="article-lead">{summary}</p><div class="article-body">{paragraphs}</div>
<div class="ad-slot in-feed-ad"><span>مساحة إعلانية</span><small>تظهر الإعلانات بعد قبول AdSense وإضافة معرّف الناشر</small></div><section class="sources"><h2>المصادر</h2><ul>{sources}</ul></section>{comments}</article></main>
<footer class="site-footer"><div class="container footer-columns"><div><a class="footer-brand" href="./index.html">نكسوس بريس</a><p>الخبر مع مصادره.</p></div><nav><a href="./about.html">من نحن</a><a href="./contact.html">اتصل بنا</a><a href="./privacy-policy.html">الخصوصية</a></nav><div class="footer-ad ad-slot"><span>مساحة إعلانية</span><small>تخضع لموافقة AdSense</small></div></div><div class="container footer-bottom">© نكسوس بريس</div></footer></body></html>'''


def main():
    if not API_KEY:
        raise RuntimeError("GitHub Actions secret OPENAI_API_KEY is required")
    state = read_json(STATE_PATH, {})
    if not isinstance(state, dict): state = {}
    seen = set(state.get("seen_story_ids", []))
    existing = read_json(DATA_PATH, [])
    if not isinstance(existing, list): existing = []
    new_items, category_counts = [], {}

    for group in group_candidates(fetch_candidates()):
        category = group[0]["category"]
        if category_counts.get(category, 0) >= MAX_PER_CATEGORY:
            continue
        fingerprint = " ".join(sorted(tokens(" ".join(x["title"] for x in group))))
        story_id = sha256((category + "|" + fingerprint).encode("utf-8")).hexdigest()[:14]
        if story_id in seen:
            continue
        try:
            report = generate_article(group)
        except Exception as error:
            print(f"Skipped candidate in {category}: {error}", file=sys.stderr)
            continue
        dates = [x["published"] for x in group if x["published"]]
        image, image_alt = create_image(category, report["title"], story_id)
        article = {
            **report,
            "storyId": story_id,
            "category": category,
            "categoryLabel": CATEGORIES[category],
            "published": max(dates)[:10] if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "نكسوس بريس",
            "sources": [{"publisher": x["publisher"], "title": x["title"], "url": x["url"]} for x in group],
            "url": f"./article-{category}-{story_id}.html",
            "image": image,
            "imageAlt": image_alt,
        }
        (ROOT / article["url"].removeprefix("./")).write_text(render_article(article), encoding="utf-8")
        new_items.append(article)
        seen.add(story_id)
        category_counts[category] = category_counts.get(category, 0) + 1

    if new_items:
        new_ids = {item["storyId"] for item in new_items}
        merged = new_items + [item for item in existing if isinstance(item, dict) and item.get("storyId") not in new_ids]
        # Never claim the required article count with fabricated or duplicated stories.
        DATA_PATH.write_text(json.dumps(merged[:MAX_TOTAL], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state["seen_story_ids"] = list(seen)[-2000:]
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(new_items)} new unique article(s).")


if __name__ == "__main__":
    main()
