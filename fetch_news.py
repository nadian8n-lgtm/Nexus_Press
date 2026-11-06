"""Publish distinct, source-linked news articles from RSS leads.

AI-generated text is not human reporting. The script never copies publisher article
bodies or photos; it creates original SVG illustrations when image generation is unavailable.
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
DATA = ROOT / "news-data.json"
STATE = ROOT / "news-state.json"
IMAGES = ROOT / "news-images"
KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
AGE_HOURS = max(1, int(os.getenv("NEWS_MAX_AGE_HOURS", "48")))
PER_CATEGORY = max(1, int(os.getenv("MAX_ARTICLES_PER_CATEGORY", "3")))
MAX_STORIES = max(30, int(os.getenv("MAX_TOTAL_ARTICLES", "100")))
UA = "NexusPress/1.0 (+https://nadian8n-lgtm.github.io/Nexus_Press/)"
CATEGORIES = {"ar_local":"أخبار وطنية", "ar_world":"أخبار دولية", "ar_economy":"اقتصاد", "ar_sports":"رياضة", "ar_technology":"تكنولوجيا"}
FEEDS = [
 ("ar_local", "هسبريس", "https://www.hespress.com/feed"),
 ("ar_local", "وكالة المغرب العربي للأنباء", "https://www.mapnews.ma/ar/rss.xml"),
 ("ar_local", "أخبارنا", "https://www.akhbarona.com/feed/index.rss"),
 ("ar_world", "العربية", "https://www.alarabiya.net/ar/rss2/arab-and-world.xml"),
 ("ar_world", "سكاي نيوز عربية", "https://www.skynewsarabia.com/rss/world.xml"),
 ("ar_world", "الجزيرة", "https://www.aljazeera.net/rss/brief/news"),
 ("ar_economy", "العربية", "https://www.alarabiya.net/ar/rss2/aswaq.xml"),
 ("ar_economy", "سكاي نيوز عربية", "https://www.skynewsarabia.com/rss/business.xml"),
 ("ar_sports", "العربية", "https://www.alarabiya.net/ar/rss2/sport.xml"),
 ("ar_sports", "سكاي نيوز عربية", "https://www.skynewsarabia.com/rss/sports.xml"),
 ("ar_sports", "الجزيرة", "https://www.aljazeera.net/rss/brief/sport"),
 ("ar_technology", "Google News technology RSS", "https://news.google.com/rss/search?q=technology+OR+artificial+intelligence+when:2d&hl=ar&gl=MA&ceid=MA:ar"),
]
STOP = set("من في على إلى عن مع هذا هذه ذلك التي الذي حيث بعد قبل بين عبر ضمن لدى كما قد ما لا لم لن إن أن أو ثم هو هي كان تكون يتم قال قالت وأكد وأكدت بحسب وفق حول خلال اليوم أمس مصادر مصدر خبر أخبار تقرير".split())


def clean(value):
    value = re.sub(r"<[^>]*>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def norm(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[\u064b-\u065f\u0670ـ]", "", value)
    value = re.sub(r"[إأآٱ]", "ا", value).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", value)


def words(value):
    return {w for w in norm(value).split() if len(w) > 2 and w not in STOP}


def similar(a, b):
    left, right = words(a), words(b)
    return bool(left and right) and len(left & right) / len(left | right) >= 0.62


def read_json(path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError, json.JSONDecodeError):
        return default


def feed_date(entry):
    value = entry.get("published_parsed") or entry.get("updated_parsed")
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_candidates():
    found = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=AGE_HOURS)
    for category, publisher, feed_url in FEEDS:
        try:
            response = requests.get(feed_url, timeout=25, headers={"User-Agent": UA})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.bozo and not feed.entries:
                raise ValueError("Invalid RSS response")
            for entry in feed.entries[:30]:
                title, url = clean(entry.get("title", "")), entry.get("link", "")
                parsed, date = urlparse(url), feed_date(entry)
                if not title or parsed.scheme != "https" or not parsed.netloc or (date and date < cutoff):
                    continue
                summary = clean(entry.get("summary", entry.get("description", "")))[:900]
                found.append({"category":category,"publisher":publisher,"domain":parsed.netloc.lower().removeprefix("www."),"title":title[:250],"summary":summary,"url":url,"published":date.isoformat() if date else ""})
        except Exception as error:
            print(f"RSS unavailable ({publisher}): {error}", file=sys.stderr)
    return found


def collect_groups(candidates):
    groups = []
    for item in sorted(candidates, key=lambda x: x["published"], reverse=True):
        group = next((g for g in groups if g[0]["category"] == item["category"] and any(similar(item["title"], old["title"]) for old in g)), None)
        if group is None:
            groups.append([item])
        elif item["domain"] not in {x["domain"] for x in group}:
            group.append(item)
    # Keep unmatched reports too: disclose that they are single-source rather than leaving sections empty.
    return sorted(groups, key=lambda g: (len(g), g[0]["published"]), reverse=True)


def write_image(category, title, story_id):
    IMAGES.mkdir(exist_ok=True)
    if os.getenv("GENERATE_AI_IMAGES", "true").lower() == "true" and KEY:
        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
                json={"model":"gpt-image-1","size":"1024x1024","quality":"low","n":1,"prompt":f"Original editorial illustration for an Arabic newspaper story about {title}. No letters, no logos, no real people, no copied photo. Clearly an illustration, not documentary."},
                timeout=120,
            )
            response.raise_for_status()
            encoded = response.json().get("data", [{}])[0].get("b64_json")
            if encoded:
                name = f"{category}-{story_id}.png"
                (IMAGES / name).write_bytes(base64.b64decode(encoded))
                return f"./news-images/{name}", "رسم توضيحي مولّد بالذكاء الاصطناعي، وليس صورة توثيقية"
        except Exception as error:
            print(f"Image generation unavailable; using local illustration: {error}", file=sys.stderr)
    palette = {"ar_local":("#0b3c7a","#e0f2fe"),"ar_world":("#17365d","#dbeafe"),"ar_economy":("#166534","#dcfce7"),"ar_sports":("#9a3412","#ffedd5"),"ar_technology":("#5b21b6","#ede9fe")}
    primary, accent = palette[category]
    safe = html.escape(title[:70])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675"><defs><linearGradient id="g"><stop stop-color="{primary}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs><rect width="1200" height="675" fill="url(#g)"/><circle cx="980" cy="115" r="190" fill="{accent}" opacity=".2"/><text x="600" y="210" text-anchor="middle" font-family="Arial" font-size="36" fill="{accent}">Nexus Press · رسم توضيحي</text><foreignObject x="90" y="255" width="1020" height="280"><div xmlns="http://www.w3.org/1999/xhtml" style="font:bold 36px Tahoma,Arial;color:white;text-align:center;direction:rtl;line-height:1.55">{safe}</div></foreignObject></svg>'
    name = f"{category}-{story_id}.svg"
    (IMAGES / name).write_text(svg, encoding="utf-8")
    return f"./news-images/{name}", "رسم توضيحي أصلي، وليس صورة للواقعة"


def generate(group):
    evidence = [{"publisher":x["publisher"],"title":x["title"],"summary":x["summary"],"date":x["published"]} for x in group]
    prompt = ("اكتب تقريراً صحفياً عربياً أصلياً اعتماداً فقط على الوقائع الواردة. لا تنسخ أو تترجم صياغة المصادر، ولا تخترع معلومات أو اقتباسات. "
              "اكتب عنواناً واضحاً وملخصاً وثلاث فقرات مختلفة، لا تكرر المعنى. إذا كان مصدر واحد فقط فاذكر ذلك بصراحة في إحدى الفقرات. "
              "إذا لم تكف المعلومات أعد publish=false. أخرج JSON فقط بالمفاتيح publish,title,summary,paragraphs.")
    response = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}, json={"model":MODEL,"temperature":0.25,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":prompt},{"role":"user","content":json.dumps(evidence,ensure_ascii=False)}]}, timeout=90)
    response.raise_for_status()
    content = response.json().get("choices",[{}])[0].get("message",{}).get("content")
    if not content: raise ValueError("Empty writing response")
    result = json.loads(content)
    if result.get("publish") is not True: raise ValueError("المصادر لا تتضمن معلومات كافية للنشر")
    title, summary = clean(result.get("title")), clean(result.get("summary"))
    paragraphs = [clean(p) for p in result.get("paragraphs",[]) if isinstance(p,str) and clean(p)]
    if len(title)<10 or len(summary)<20 or len(paragraphs)<3 or len(set(paragraphs)) != len(paragraphs):
        raise ValueError("المقال لم يجتز فحص الجودة والتكرار")
    source_text = " ".join(x["title"]+" "+x["summary"] for x in group)
    def shingles(text):
        ws=norm(text).split(); return {tuple(ws[i:i+5]) for i in range(max(0,len(ws)-4))}
    article_shingles, source_shingles = shingles(" ".join([title,summary,*paragraphs])), shingles(source_text)
    if article_shingles and len(article_shingles & source_shingles)/len(article_shingles) > .12:
        raise ValueError("المقال قريب نصياً من المقتطفات الأصلية")
    return title, summary, paragraphs


def article_page(item):
    title=html.escape(item["title"]); summary=html.escape(item["summary"])
    paras="".join(f"<p>{html.escape(p)}</p>" for p in item["paragraphs"])
    sources="".join(f'<li><a href="{html.escape(s["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(s["publisher"])} — {html.escape(s["title"])}</a></li>' for s in item["sources"])
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | نكسوس بريس</title><meta name="description" content="{summary[:155]}"><link rel="stylesheet" href="./style.css"></head><body><header class="site-header"><div class="container header-inner"><a class="brand" href="./index.html"><img src="./image_MUwSAA.png" alt="نكسوس بريس"><span>نكسوس بريس</span></a><a href="./index.html">الرئيسية</a></div></header><nav class="site-nav"><div class="container nav-inner"><a class="nav-link" href="./index.html">الرئيسية</a><a class="nav-link" href="./index.html#articles">الأقسام</a></div></nav><main class="container main-content"><article class="post"><span class="badge">{html.escape(item['categoryLabel'])}</span><h1>{title}</h1><p class="card-meta">{html.escape(item['published'])} · نكسوس بريس</p><img class="article-image" src="{html.escape(item['image'],quote=True)}" alt="{html.escape(item['imageAlt'],quote=True)}"><p class="article-lead">{summary}</p><div class="article-body">{paras}</div><section class="sources"><h2>المصادر</h2><ul>{sources}</ul></section><section class="comments"><h2>تعليقات القراء</h2><a href="https://github.com/nadian8n-lgtm/Nexus_Press/discussions">شارك في نقاش GitHub Discussions</a></section></article></main><footer class="site-footer"><div class="container footer-inner"><a href="./about.html">من نحن</a><a href="./contact.html">اتصل بنا</a><a href="./privacy-policy.html">الخصوصية</a></div></footer></body></html>'''


def main():
    if not KEY: raise RuntimeError("أضف OPENAI_API_KEY في Actions secrets")
    existing=read_json(DATA,[])
    if not isinstance(existing,list): existing=[]
    state=read_json(STATE,{})
    if not isinstance(state,dict): state={}
    seen=set(state.get("seen_story_ids",[]))
    counts={c:sum(1 for x in existing if isinstance(x,dict) and x.get("category")==c) for c in CATEGORIES}
    new=[]
    for group in collect_groups(fetch_candidates()):
        category=group[0]["category"]
        if counts.get(category,0)>=PER_CATEGORY: continue
        fingerprint=" ".join(sorted(words(" ".join(x["title"] for x in group))))
        story_id=sha256((category+"|"+fingerprint).encode()).hexdigest()[:14]
        if not fingerprint or story_id in seen: continue
        if any(similar(" ".join(words(x.get("title","")))," ".join(words(group[0]["title"]))) for x in existing if isinstance(x,dict) and x.get("category")==category):
            continue
        try: title,summary,paragraphs=generate(group)
        except Exception as error:
            print(f"Skipped {category} story: {error}",file=sys.stderr); continue
        date=max((x["published"] for x in group if x["published"]),default=datetime.now(timezone.utc).isoformat())[:10]
        image,image_alt=write_image(category,title,story_id)
        item={"storyId":story_id,"title":title,"summary":summary,"paragraphs":paragraphs,"category":category,"categoryLabel":CATEGORIES[category],"url":f"./article-{category}-{story_id}.html","image":image,"imageAlt":image_alt,"published":date,"source":"نكسوس بريس","sources":[{"publisher":x["publisher"],"title":x["title"],"url":x["url"]} for x in group]}
        (ROOT/item["url"].removeprefix("./")).write_text(article_page(item),encoding="utf-8")
        new.append(item);seen.add(story_id);counts[category]=counts.get(category,0)+1
    merged=new+[x for x in existing if isinstance(x,dict) and x.get("storyId") not in {n["storyId"] for n in new}]
    DATA.write_text(json.dumps(merged[:MAX_STORIES],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    state["seen_story_ids"]=sorted(seen)[-3000:]
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if not new: print("No source-backed story passed checks. Existing articles were kept unchanged.")
    print(f"Published {len(new)} new articles; total visible articles: {min(len(merged),MAX_STORIES)}")

if __name__ == "__main__":
    main()
