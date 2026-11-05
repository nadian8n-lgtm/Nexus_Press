"""Fetch independently corroborated news and publish original Arabic reports.

This publisher deliberately fails closed: it does not publish an item unless at least
 two independent approved publishers report the same event, and it does not copy source
 article text or images. RSS excerpts are evidence leads, not a substitute for editorial
 verification. The OpenAI API key is read from the OPENAI_API_KEY environment variable.
"""

import html
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "news-data.json"
IMAGE_DIR = ROOT / "news-images"
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_AGE_HOURS = int(os.getenv("NEWS_MAX_AGE_HOURS", "30"))
MAX_NEW_PER_CATEGORY = int(os.getenv("MAX_NEW_PER_CATEGORY", "1"))
MAX_STORIES = 6
TIMEOUT = 25
USER_AGENT = "NexusPressNewsBot/1.0 (+https://nadian8n-lgtm.github.io/Nexus_Press/)"

# RSS is used only to discover and cross-check reports. The publisher names/URLs are
# deliberately explicit so the automation does not silently trust arbitrary websites.
FEEDS = [
    {"category": "ar_local", "label": "أخبار وطنية", "publisher": "هسبريس", "url": "https://www.hespress.com/feed"},
    {"category": "ar_local", "label": "أخبار وطنية", "publisher": "وكالة المغرب العربي للأنباء", "url": "https://www.mapnews.ma/ar/rss.xml"},
    {"category": "ar_local", "label": "أخبار وطنية", "publisher": "أخبارنا", "url": "https://www.akhbarona.com/feed/index.rss"},
    {"category": "ar_local", "label": "أخبار وطنية", "publisher": "Le Matin", "url": "https://lematin.ma/rssFeed/0"},
    {"category": "ar_world", "label": "أخبار دولية", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/arab-and-world.xml"},
    {"category": "ar_world", "label": "أخبار دولية", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/world.xml"},
    {"category": "ar_world", "label": "أخبار دولية", "publisher": "الجزيرة", "url": "https://www.aljazeera.net/rss/brief/news"},
    {"category": "ar_economy", "label": "اقتصاد", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/aswaq.xml"},
    {"category": "ar_economy", "label": "اقتصاد", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/business.xml"},
    {"category": "ar_economy", "label": "اقتصاد", "publisher": "Le Matin", "url": "https://lematin.ma/rssFeed/4"},
    {"category": "ar_sports", "label": "رياضة", "publisher": "العربية", "url": "https://www.alarabiya.net/ar/rss2/sport.xml"},
    {"category": "ar_sports", "label": "رياضة", "publisher": "سكاي نيوز عربية", "url": "https://www.skynewsarabia.com/rss/sports.xml"},
    {"category": "ar_sports", "label": "رياضة", "publisher": "الجزيرة", "url": "https://www.aljazeera.net/rss/brief/sport"},
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


def similar_event(left, right):
    a = tokens(left.get("title", "") + " " + left.get("summary", ""))
    b = tokens(right.get("title", "") + " " + right.get("summary", ""))
    if len(a & b) < 2:
        return False
    return len(a & b) / max(1, len(a | b)) >= 0.16


def entry_date(entry):
    struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not struct_time:
        return None
    try:
        return datetime(*struct_time[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_candidates():
    all_candidates = []
    for feed in FEEDS:
        try:
            response = requests.get(feed["url"], timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError("RSS غير صالح أو فارغ")
            for entry in parsed.entries[:20]:
                title = clean_text(entry.get("title", ""))
                link = entry.get("link", "")
                parsed_url = urlparse(link)
                when = entry_date(entry)
                if not title or parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                    continue
                if when and when < datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS):
                    continue
                summary = clean_text(entry.get("summary", entry.get("description", "")))[:1200]
                all_candidates.append({
                    "category": feed["category"],
                    "categoryLabel": feed["label"],
                    "publisher": feed["publisher"],
                    "domain": parsed_url.netloc.lower().removeprefix("www."),
                    "title": title[:300],
                    "summary": summary,
                    "url": link,
                    "published": when.isoformat() if when else "",
                })
        except Exception as error:
            print(f"Feed unavailable ({feed['publisher']}): {error}", file=sys.stderr)
    return all_candidates


def corroborated_groups(candidates):
    groups = []
    for candidate in sorted(candidates, key=lambda item: item.get("published", ""), reverse=True):
        matching = next((group for group in groups if group[0]["category"] == candidate["category"] and any(similar_event(candidate, item) for item in group)), None)
        if matching is None:
            groups.append([candidate])
        elif candidate["domain"] not in {item["domain"] for item in matching}:
            matching.append(candidate)
    return [group for group in groups if len({item["domain"] for item in group}) >= 2]


def load_existing():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def source_url_set(items):
    found = set()
    for item in items:
        for source in item.get("sources", []):
            if source.get("url"):
                found.add(source["url"])
        if item.get("sourceUrl"):
            found.add(item["sourceUrl"])
    return found


def text_similarity(text, reference):
    def ngrams(value):
        words = normalize(value).split()
        return {tuple(words[index:index + 5]) for index in range(max(0, len(words) - 4))}
    article_grams = ngrams(text)
    reference_grams = ngrams(reference)
    if not article_grams or not reference_grams:
        return 0.0
    return len(article_grams & reference_grams) / len(article_grams)


def generate_original_report(group):
    if not API_KEY:
        raise RuntimeError("مفتاح OPENAI_API_KEY غير موجود في GitHub Secrets؛ لن يتم نشر نص غير محرر")
    sources = [{"publisher": item["publisher"], "title": item["title"], "excerpt": item["summary"], "url": item["url"], "published": item["published"]} for item in group]
    system = (
        "أنت محرر صحفي عربي محترف في غرفة أخبار. اكتب تقريراً إخبارياً أصلياً باللغة العربية الفصحى، "
        "اعتماداً حصراً على الوقائع المشتركة الواردة في بيانات المصادر المرفقة. لا تنسخ أي عبارة من العناوين أو المقتطفات، "
        "ولا تترجمها حرفياً ولا تعِد صياغة المقالات. لا تخترع اقتباسات أو أرقاماً أو أسماء أو سياقاً غير موجود. "
        "إذا لم تتفق المصادر على واقعة، استبعدها. لا تدّعِ أن المعلومات مؤكدة بما يتجاوز ما تثبته المصادر. "
        "اكتب عنواناً صحفياً جديداً غير مطابق للعناوين الأصلية، ومقدمة واضحة، وثلاث إلى خمس فقرات قصيرة، "
        "واذكر داخل النص عند الحاجة أن التفاصيل منسوبة إلى المصادر. تجنب الرأي والتضخيم والعناوين المضللة. "
        "أخرج JSON صالحاً فقط بالمفاتيح title, summary, body، حيث body مصفوفة فقرات نصية."
    )
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({"sources": sources, "requirements": "اكتب مادة تحريرية أصلية 220 إلى 350 كلمة كحد تقريبي؛ لا تضف معلومات غير مسندة."}, ensure_ascii=False)},
            ],
        },
        timeout=90,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    title = clean_text(result.get("title", ""))
    summary = clean_text(result.get("summary", ""))
    body = [clean_text(paragraph) for paragraph in result.get("body", []) if clean_text(paragraph)]
    if len(title) < 12 or len(summary) < 30 or len(body) < 3 or len(" ".join(body).split()) < 120:
        raise ValueError("النص المولد لا يفي بحدود الجودة الدنيا")
    original_text = " ".join([title, summary, *body])
    evidence_text = " ".join(item["title"] + " " + item["summary"] for item in group)
    if text_similarity(original_text, evidence_text) > 0.12:
        raise ValueError("تم رفض المسودة: تشابه لفظي مرتفع مع مقتطفات المصادر")
    for source in group:
        if text_similarity(title, source["title"]) > 0.35:
            raise ValueError("تم رفض العنوان: قريب لفظياً من عنوان مصدر")
    return {"title": title, "summary": summary, "body": body}


def write_original_image(category, title, slot, story_id):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    palettes = {
        "ar_local": ("#0b3c7a", "#e0f2fe", "خبر وطني"),
        "ar_world": ("#17365d", "#dbeafe", "أخبار دولية"),
        "ar_economy": ("#166534", "#dcfce7", "اقتصاد"),
        "ar_sports": ("#9a3412", "#ffedd5", "رياضة"),
    }
    primary, secondary, label = palettes[category]
    safe_title = html.escape(title[:70])
    image_name = f"{category}-{slot}-{story_id}.svg"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" aria-label="صورة تحريرية أصلية: {safe_title}">
<defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="{primary}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs>
<rect width="1200" height="675" fill="url(#g)"/><circle cx="1010" cy="100" r="220" fill="{secondary}" opacity=".15"/><circle cx="170" cy="620" r="280" fill="{secondary}" opacity=".12"/>
<path d="M0 500 350 330l210 125 220-200 420 245v175H0z" fill="{secondary}" opacity=".12"/>
<text x="600" y="260" text-anchor="middle" direction="rtl" font-family="Tahoma,Arial,sans-serif" font-size="38" font-weight="700" fill="{secondary}">{label} · نكسوس بريس</text>
<foreignObject x="100" y="315" width="1000" height="220"><div xmlns="http://www.w3.org/1999/xhtml" style="font: bold 36px Tahoma,Arial,sans-serif;color:white;text-align:center;direction:rtl;line-height:1.55">{safe_title}</div></foreignObject>
</svg>'''
    (IMAGE_DIR / image_name).write_text(svg, encoding="utf-8")
    return f"./news-images/{image_name}"


def render_article(item):
    title = html.escape(item["title"])
    summary = html.escape(item["summary"])
    paragraphs = "\n".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in item["body"])
    sources = "\n".join(
        f'<li><a href="{html.escape(source["url"], quote=True)}" rel="noopener noreferrer" target="_blank">{html.escape(source["publisher"])}: {html.escape(source["title"])}</a></li>'
        for source in item["sources"]
    )
    image = html.escape(item["image"], quote=True)
    category_label = html.escape(item["categoryLabel"])
    date = html.escape(item["published"])
    return f'''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} - نكسوس بريس</title>
<meta name="description" content="{summary[:155]}"><meta name="robots" content="index,follow"><link rel="canonical" href="https://nadian8n-lgtm.github.io/Nexus_Press/{html.escape(item['url'].removeprefix('./'), quote=True)}"><link rel="stylesheet" href="./style.css"></head>
<body><header class="site-header"><div class="container header-inner"><a class="brand" href="./index.html"><img src="./image_MUwSAA.png" alt=""><span>نكسوس بريس</span></a><a href="./index.html">العودة إلى الرئيسية</a></div></header>
<main class="container main-content"><article class="post"><span class="badge">{category_label}</span><h1>{title}</h1><p class="card-meta">نُشر: {date} · تحرير نكسوس بريس</p><img class="article-image" src="{image}" alt="صورة تحريرية أصلية للخبر"><p class="article-lead">{summary}</p><div class="article-body">{paragraphs}</div><section class="sources"><h2>المصادر والتحقق</h2><p>استند هذا التقرير إلى تقاطع المعلومات المنشورة لدى المصادر التالية. تُنسب المعلومات إلى مصادرها؛ ولا يعني ذلك وجود شراكة معها.</p><ul>{sources}</ul></section></article></main>
<footer class="site-footer"><div class="container footer-inner"><span>© نكسوس بريس</span><a href="./privacy-policy.html">سياسة الخصوصية</a><a href="./contact.html">اتصل بنا</a></div></footer></body></html>'''


def publish():
    existing = load_existing()
    seen_urls = source_url_set(existing)
    candidates = fetch_candidates()
    groups = corroborated_groups(candidates)
    if not groups:
        print("No independently corroborated fresh stories. Nothing will be published.")
        return

    new_items = []
    category_counts = {}
    for group in groups:
        category = group[0]["category"]
        if category_counts.get(category, 0) >= MAX_NEW_PER_CATEGORY:
            continue
        urls = {source["url"] for source in group}
        if urls and urls.issubset(seen_urls):
            continue
        try:
            report = generate_original_report(group)
        except Exception as error:
            print(f"Rejected story in {category}: {error}", file=sys.stderr)
            continue
        story_id = sha256("|".join(sorted(urls)).encode("utf-8")).hexdigest()[:10]
        label = group[0]["categoryLabel"]
        published_dates = [source["published"] for source in group if source["published"]]
        published_date = max(published_dates)[:10] if published_dates else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_items.append({
            **report,
            "category": category,
            "categoryLabel": label,
            "published": published_date,
            "source": "تحرير نكسوس بريس",
            "sources": [{"publisher": source["publisher"], "title": source["title"], "url": source["url"], "published": source["published"]} for source in group],
            "sourceUrl": group[0]["url"],
            "storyId": story_id,
            "image": "",
        })
        category_counts[category] = category_counts.get(category, 0) + 1

    if not new_items:
        print("No new stories passed the sourcing and originality checks.")
        return

    merged = []
    for category in {item["category"] for item in new_items} | {item.get("category") for item in existing}:
        fresh = [item for item in new_items if item["category"] == category]
        prior = [item for item in existing if item.get("category") == category and item.get("storyId") not in {story["storyId"] for story in fresh}]
        combined = (fresh + prior)[:MAX_STORIES]
        for slot, item in enumerate(combined):
            item["url"] = f"./news-{category}-{slot}.html"
            if not item.get("storyId"):
                item["storyId"] = sha256(item.get("sourceUrl", item["title"]).encode("utf-8")).hexdigest()[:10]
            item["image"] = write_original_image(category, item["title"], slot, item["storyId"])
            (ROOT / f"news-{category}-{slot}.html").write_text(render_article(item), encoding="utf-8")
        merged.extend(combined)

    DATA_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(new_items)} newly corroborated, original articles.")


if __name__ == "__main__":
    publish()
