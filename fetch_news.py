import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

ROOT = Path(__file__).resolve().parent
PLACEHOLDER = "./placeholder.svg"
CATEGORIES = [
    {"key": "ar_local", "label": "أخبار وطنية", "feed": "https://www.hespress.com/feed"},
    {"key": "ar_world", "label": "أخبار دولية", "feed": "https://www.aljazeera.net/rss/brief/news"},
    {"key": "ar_economy", "label": "اقتصاد", "feed": "https://www.aljazeera.net/rss/brief/economy"},
    {"key": "ar_sports", "label": "رياضة", "feed": "https://www.aljazeera.net/rss/brief/sport"},
]


def clean_text(value):
    value = re.sub(r"<[^>]*>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def entry_image(entry):
    candidates = []
    for media in entry.get("media_content", []):
        candidates.append(media.get("url", ""))
    for media in entry.get("media_thumbnail", []):
        candidates.append(media.get("url", ""))
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image/"):
            candidates.append(link.get("href", ""))
    for candidate in candidates:
        parsed = urlparse(candidate)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return candidate
    return PLACEHOLDER


def published(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
    return ""


def render_article(category, item):
    title = html.escape(item["title"])
    summary = html.escape(item["summary"])
    image = html.escape(item["image"], quote=True)
    source = html.escape(item["source"])
    date = html.escape(item["published"])
    article_url = html.escape(item["sourceUrl"], quote=True)
    page_title = f"{title} - نكسوس بريس"
    paragraphs = "".join(f"<p>{html.escape(part)}</p>" for part in re.split(r"(?<=[.!؟])\s+", item["summary"]) if part)
    if not paragraphs:
        paragraphs = "<p>تابع تفاصيل هذا الخبر من مصدره الأصلي عبر الرابط أدناه.</p>"
    return f'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{summary[:155]}">
  <link rel="stylesheet" href="./style.css">
</head>
<body>
<header class="site-header"><div class="container header-inner"><a class="brand" href="./index.html"><img src="./image_MUwSAA.png" alt=""><span>نكسوس بريس</span></a><a href="./index.html">العودة إلى الرئيسية</a></div></header>
<main class="container main-content"><article class="post"><span class="badge">{html.escape(category['label'])}</span><h1>{title}</h1><p class="card-meta">{date} · {source}</p><img class="article-image" src="{image}" alt="" onerror="this.onerror=null;this.src='./placeholder.svg'"><div class="article-body">{paragraphs}</div><p><a class="source-link" href="{article_url}" target="_blank" rel="noopener noreferrer">اقرأ الخبر كاملاً في المصدر الأصلي</a></p></article></main>
<footer class="site-footer"><div class="container footer-inner"><span>© نكسوس بريس</span><a href="./privacy-policy.html">سياسة الخصوصية</a></div></footer>
</body></html>'''


def fetch_category(category):
    response = requests.get(category["feed"], timeout=20, headers={"User-Agent": "NexusPress/1.0 (+GitHub Pages publisher)"})
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items = []
    for entry in parsed.entries[:6]:
        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", entry.get("description", "")))
        link = entry.get("link", "")
        parsed_link = urlparse(link)
        if not title or parsed_link.scheme not in ("http", "https") or not parsed_link.netloc:
            continue
        items.append({
            "title": title,
            "category": category["key"],
            "categoryLabel": category["label"],
            "url": f"./news-{category['key']}-{len(items)}.html",
            "image": entry_image(entry),
            "published": published(entry),
            "source": parsed_link.netloc.removeprefix("www."),
            "sourceUrl": link,
            "summary": summary or "لا يتوفر ملخص لهذا الخبر؛ يمكن متابعة التفاصيل من المصدر الأصلي.",
        })
    return items


def main():
    all_items = []
    updated_categories = set()
    for category in CATEGORIES:
        try:
            items = fetch_category(category)
            if not items:
                raise ValueError("لم يُرجع موجز الأخبار مواد صالحة")
            for item in items:
                article_path = ROOT / item["url"].removeprefix("./")
                article_path.write_text(render_article(category, item), encoding="utf-8")
            all_items.extend(items)
            updated_categories.add(category["key"])
            print(f"{category['label']}: نُشرت {len(items)} مواد")
        except Exception as error:
            print(f"تعذر تحديث {category['label']}: {error}")

    data_path = ROOT / "news-data.json"
    try:
        existing = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    except (OSError, json.JSONDecodeError):
        existing = []
    retained = [item for item in existing if item.get("category") not in updated_categories]
    data_path.write_text(json.dumps(all_items + retained, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
