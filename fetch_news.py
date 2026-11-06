"""Fetch RSS leads, author original reports, and publish source-linked articles.

The script uses RSS headlines/descriptions as leads and never copies full source articles
or source photos. It prefers reports covered by multiple publishers. If only one source
is available, that limitation is stated on the article rather than pretending corroboration.
AI-generated copy and images are not human reporting, legal clearance, or a guarantee of accuracy.
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
MAX_AGE_HOURS = max(1, int(os.getenv("NEWS_MAX_AGE_HOURS", "48")))
MAX_PER_CATEGORY = max(1, int(os.getenv("MAX_ARTICLES_PER_CATEGORY", "6")))
MAX_TOTAL = max(24, int(os.getenv("MAX_TOTAL_ARTICLES", "100")))
GENERATE_AI_IMAGES = os.getenv("GENERATE_AI_IMAGES", "true").lower() == "true"
TIMEOUT = 25
USER_AGENT = "NexusPressNews/1.0 (+https://nadian8n-lgtm.github.io/Nexus_Press/)"
CATEGORIES = {"ar_local":"أخبار وطنية","ar_world":"أخبار دولية","ar_economy":"اقتصاد","ar_sports":"رياضة","ar_technology":"تكنولوجيا"}
FEEDS = [
 {"category":"ar_local","publisher":"هسبريس","url":"https://www.hespress.com/feed"},
 {"category":"ar_local","publisher":"وكالة المغرب العربي للأنباء","url":"https://www.mapnews.ma/ar/rss.xml"},
 {"category":"ar_local","publisher":"أخبارنا","url":"https://www.akhbarona.com/feed/index.rss"},
 {"category":"ar_local","publisher":"Le Matin","url":"https://lematin.ma/rssFeed/0"},
 {"category":"ar_world","publisher":"العربية","url":"https://www.alarabiya.net/ar/rss2/arab-and-world.xml"},
 {"category":"ar_world","publisher":"سكاي نيوز عربية","url":"https://www.skynewsarabia.com/rss/world.xml"},
 {"category":"ar_world","publisher":"الجزيرة","url":"https://www.aljazeera.net/rss/brief/news"},
 {"category":"ar_economy","publisher":"العربية","url":"https://www.alarabiya.net/ar/rss2/aswaq.xml"},
 {"category":"ar_economy","publisher":"سكاي نيوز عربية","url":"https://www.skynewsarabia.com/rss/business.xml"},
 {"category":"ar_economy","publisher":"Le Matin","url":"https://lematin.ma/rssFeed/4"},
 {"category":"ar_sports","publisher":"العربية","url":"https://www.alarabiya.net/ar/rss2/sport.xml"},
 {"category":"ar_sports","publisher":"سكاي نيوز عربية","url":"https://www.skynewsarabia.com/rss/sports.xml"},
 {"category":"ar_sports","publisher":"الجزيرة","url":"https://www.aljazeera.net/rss/brief/sport"},
 {"category":"ar_technology","publisher":"Google News RSS","url":"https://news.google.com/rss/search?q=technology+OR+artificial+intelligence+when:2d&hl=ar&gl=MA&ceid=MA:ar"},
 {"category":"ar_technology","publisher":"Google News RSS Morocco","url":"https://news.google.com/rss/search?q=technology+Morocco+when:2d&hl=ar&gl=MA&ceid=MA:ar"},
]
STOP=set("من في على إلى عن مع هذا هذه ذلك التي الذي حيث بعد قبل بين عبر ضمن لدى كما قد ما لا لم لن إن أن أو ثم هو هي كان تكون يتم قال قالت وأكد وأكدت بحسب وفق حول خلال اليوم أمس مصادر مصدر خبر أخبار تقرير".split())

def clean(value):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",value or ""))).strip()

def norm(value):
    value=unicodedata.normalize("NFKC",value or "").lower()
    value=re.sub(r"[\u064b-\u065f\u0670ـ]","",value)
    value=re.sub(r"[إأآٱ]","ا",value).replace("ى","ي").replace("ة","ه")
    return re.sub(r"[^\w\u0600-\u06ff]+"," ",value)

def tokens(value): return {w for w in norm(value).split() if len(w)>2 and w not in STOP}
def event_match(a,b):
    x,y=tokens(a["title"]+" "+a["summary"]),tokens(b["title"]+" "+b["summary"])
    return len(x&y)>=2 and len(x&y)/max(1,len(x|y))>=.12

def load_json(path,default):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError,json.JSONDecodeError): return default

def published_date(entry):
    parsed=entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:return None
    try:return datetime(*parsed[:6],tzinfo=timezone.utc)
    except (TypeError,ValueError):return None

def fetch():
    found=[]; cutoff=datetime.now(timezone.utc)-timedelta(hours=MAX_AGE_HOURS)
    for feed in FEEDS:
        try:
            response=requests.get(feed["url"],timeout=TIMEOUT,headers={"User-Agent":USER_AGENT});response.raise_for_status()
            parsed=feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries: raise ValueError("Invalid RSS")
            for entry in parsed.entries[:30]:
                title=clean(entry.get("title","")); url=entry.get("link",""); u=urlparse(url); date=published_date(entry)
                if not title or u.scheme not in {"http","https"} or not u.netloc:continue
                if date and date<cutoff:continue
                found.append({"category":feed["category"],"categoryLabel":CATEGORIES[feed["category"]],"publisher":feed["publisher"],"domain":u.netloc.lower().removeprefix("www."),"title":title[:250],"summary":clean(entry.get("summary",entry.get("description","")))[:900],"url":url,"published":date.isoformat() if date else ""})
        except Exception as error: print(f"RSS unavailable: {feed['publisher']}: {error}",file=sys.stderr)
    return found

def clusters(items):
    result=[]
    for item in sorted(items,key=lambda x:x.get("published", ""),reverse=True):
        group=next((g for g in result if g[0]["category"]==item["category"] and any(event_match(item,old) for old in g)),None)
        if group is None:result.append([item])
        elif item["domain"] not in {x["domain"] for x in group}:group.append(item)
    # Prefer independently covered events; use a clearly disclosed single-source item only as fallback.
    multi=[g for g in result if len({x["domain"] for x in g if "news.google.com" not in x["domain"]})>=2]
    seen={x["url"] for g in multi for x in g}
    single=[g for g in result if len(g)==1 and g[0]["url"] not in seen]
    return multi+single

def overlap(article,source):
    def grams(s):
        w=norm(s).split();return {tuple(w[i:i+5]) for i in range(max(0,len(w)-4))}
    a,b=grams(article),grams(source)
    return len(a&b)/len(a) if a and b else 0

def generate(group):
    records=[{"publisher":x["publisher"],"headline":x["title"],"description":x["summary"],"date":x["published"]} for x in group]
    system=("أنت محرر صحفي عربي. أنشئ تقريراً أصلياً اعتماداً حصراً على الوقائع الواردة في البيانات القصيرة. لا تنسخ أو تترجم صياغة العناوين أو المقتطفات، ولا تخترع أسماء أو أرقاماً أو تصريحات. لا تدّع التحقق المستقل. إذا كان المصدر واحداً، وضح ذلك في التقرير. إذا كانت البيانات غير كافية فأعد publish=false. اكتب عنواناً جديداً وملخصاً و3 فقرات مختلفة دون تكرار. أخرج JSON فقط بالمفاتيح publish,title,summary,paragraphs,translations. translations كائن فيه fr وen، ولكل منهما title وsummary وparagraphs مترجمة. لا تغيّر الحقائق عند الترجمة.")
    if not API_KEY:raise RuntimeError("OPENAI_API_KEY is missing")
    r=requests.post("https://api.openai.com/v1/chat/completions",headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},json={"model":MODEL,"temperature":.25,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":system},{"role":"user","content":json.dumps({"sources":records},ensure_ascii=False)}]},timeout=120)
    r.raise_for_status(); content=r.json().get("choices",[{}])[0].get("message",{}).get("content")
    if not content:raise ValueError("Empty OpenAI response")
    data=json.loads(content)
    if data.get("publish") is not True:raise ValueError("Insufficient material")
    title=clean(data.get("title"));summary=clean(data.get("summary"));paragraphs=[clean(x) for x in data.get("paragraphs",[]) if isinstance(x,str) and clean(x)]
    if len(title)<10 or len(summary)<20 or len(paragraphs)<3:raise ValueError("Article quality check failed")
    source_text=" ".join(x["title"]+" "+x["summary"] for x in group)
    if overlap(" ".join([title,summary,*paragraphs]),source_text)>.10:raise ValueError("Similarity check rejected draft")
    translations=data.get("translations") if isinstance(data.get("translations"),dict) else {}
    clean_translations={}
    for language in ("fr","en"):
        tr=translations.get(language,{})
        if isinstance(tr,dict):
            clean_translations[language]={"title":clean(tr.get("title")),"summary":clean(tr.get("summary")),"paragraphs":[clean(p) for p in tr.get("paragraphs",[]) if isinstance(p,str) and clean(p)]}
    return {"title":title,"summary":summary,"paragraphs":paragraphs,"translations":clean_translations}

def svg_art(category,title,story_id):
    colors={"ar_local":("#0b3c7a","#e0f2fe"),"ar_world":("#17365d","#dbeafe"),"ar_economy":("#166534","#dcfce7"),"ar_sports":("#9a3412","#ffedd5"),"ar_technology":("#5b21b6","#ede9fe")}; primary,accent=colors[category]
    safe=html.escape(title[:65])
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" aria-label="Editorial illustration, not documentary"><defs><linearGradient id="g"><stop stop-color="{primary}"/><stop offset="1" stop-color="#071c35"/></linearGradient></defs><rect width="1200" height="675" fill="url(#g)"/><circle cx="980" cy="120" r="190" fill="{accent}" opacity=".2"/><text x="600" y="230" text-anchor="middle" font-family="Arial" font-size="36" fill="{accent}">Nexus Press · illustration</text><foreignObject x="100" y="270" width="1000" height="250"><div xmlns="http://www.w3.org/1999/xhtml" style="font:bold 34px Tahoma,Arial;color:white;text-align:center;direction:rtl;line-height:1.6">{safe}</div></foreignObject></svg>'

def create_image(category,title,story_id):
    IMAGE_DIR.mkdir(parents=True,exist_ok=True)
    if GENERATE_AI_IMAGES and API_KEY:
        try:
            r=requests.post("https://api.openai.com/v1/images/generations",headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"},json={"model":"gpt-image-1","size":"1024x1024","quality":"low","n":1,"prompt":f"Original editorial illustration for a news article about: {title}. No text, logo, recognizable real person, existing photograph, or copied style. Clearly illustrative, not documentary."},timeout=150)
            r.raise_for_status(); encoded=r.json()["data"][0].get("b64_json")
            if encoded:
                path=IMAGE_DIR/f"{category}-{story_id}.png";path.write_bytes(base64.b64decode(encoded));return f"./news-images/{path.name}","AI-generated editorial illustration, not documentary"
        except Exception as e:print(f"Image API failed; using local SVG: {e}",file=sys.stderr)
    path=IMAGE_DIR/f"{category}-{story_id}.svg";path.write_text(svg_art(category,title,story_id),encoding="utf-8");return f"./news-images/{path.name}","Original illustration, not a documentary photo"

def article_html(item):
    payload=json.dumps({"title":item["title"],"summary":item["summary"],"paragraphs":item["paragraphs"],"translations":item.get("translations",{}),"categoryLabel":item["categoryLabel"]},ensure_ascii=False).replace("</","<\\/")
    title=html.escape(item["title"]);sources="".join(f'<li><a href="{html.escape(s["url"],quote=True)}" target="_blank" rel="noopener">{html.escape(s["publisher"])} — {html.escape(s["title"])}</a></li>' for s in item["sources"])
    image=html.escape(item["image"],quote=True);article_url=html.escape(item["url"].removeprefix("./"),quote=True)
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | نكسوس بريس</title><link rel="canonical" href="https://nadian8n-lgtm.github.io/Nexus_Press/{article_url}"><link rel="stylesheet" href="./style.css"><meta name="description" content="{html.escape(item['summary'][:155],quote=True)}"></head><body>
<div class="utility-bar"><div class="container utility-inner"><span>نكسوس بريس</span><label class="language-picker">🌐 <select id="language-select" aria-label="Language"><option value="ar">العربية</option><option value="fr">Français</option><option value="en">English</option></select></label></div></div>
<header class="site-header"><div class="container header-inner"><a class="brand" href="./index.html"><img src="./image_MUwSAA.png" alt="Nexus Press"><span>نكسوس بريس</span></a><div class="header-ad ad-slot">مساحة إعلانية</div></div></header>
<nav class="site-nav"><div class="container nav-inner"><a class="nav-link" href="./index.html">الرئيسية</a><a class="nav-link" href="./index.html#articles">الأقسام</a></div></nav>
<main class="container main-content"><article class="post"><span class="badge" id="category">{html.escape(item['categoryLabel'])}</span><h1 id="article-title">{title}</h1><p class="card-meta">{html.escape(item['published'])} · Nexus Press</p><img class="article-image" src="{image}" alt="{html.escape(item['imageAlt'],quote=True)}"><p class="article-lead" id="article-summary">{html.escape(item['summary'])}</p><div class="article-body" id="article-body">{''.join(f'<p>{html.escape(p)}</p>' for p in item['paragraphs'])}</div>
<section class="sources"><h2>المصادر / Sources</h2><ul>{sources}</ul></section><section class="comments"><h2>التعليقات</h2><script src="https://utteranc.es/client.js" repo="nadian8n-lgtm/Nexus_Press" issue-term="pathname" label="comments" theme="github-light" crossorigin="anonymous" async></script><noscript><a href="https://github.com/nadian8n-lgtm/Nexus_Press/discussions">شارك في النقاش</a></noscript></section></article></main>
<footer class="site-footer"><div class="container footer-columns"><a class="footer-brand" href="./index.html">نكسوس بريس</a><nav><a href="./about.html">من نحن</a><a href="./contact.html">اتصل بنا</a><a href="./privacy-policy.html">الخصوصية</a></nav><div class="footer-ad ad-slot">مساحة إعلانية</div></div><div class="container footer-bottom">© Nexus Press</div></footer>
<script type="application/json" id="article-data">{payload}</script><script>
(()=>{{const data=JSON.parse(document.getElementById('article-data').textContent),select=document.getElementById('language-select');function setLang(lang){{document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';const t=data.translations[lang];if(lang!=='ar'&&t&&t.title){{document.getElementById('article-title').textContent=t.title;document.getElementById('article-summary').textContent=t.summary||data.summary;document.getElementById('article-body').replaceChildren(...(t.paragraphs||[]).map(p=>{{const el=document.createElement('p');el.textContent=p;return el}}));document.getElementById('category').textContent=lang==='fr'?'Actualités':'News'}}else{{document.getElementById('article-title').textContent=data.title;document.getElementById('article-summary').textContent=data.summary;document.getElementById('article-body').replaceChildren(...data.paragraphs.map(p=>{{const el=document.createElement('p');el.textContent=p;return el}}));document.getElementById('category').textContent=data.categoryLabel}}localStorage.setItem('nexus-language',lang)}}const lang=localStorage.getItem('nexus-language')||'ar';select.value=lang;setLang(lang);select.addEventListener('change',()=>setLang(select.value))}})();
</script></body></html>'''

def main():
    if not API_KEY:raise RuntimeError("OPENAI_API_KEY is missing")
    state=load_json(STATE_PATH,{})
    if not isinstance(state,dict):state={}
    seen=set(state.get("seen_story_ids",[]));existing=load_json(DATA_PATH,[])
    if not isinstance(existing,list):existing=[]
    counts={}
    for item in existing:
        if isinstance(item,dict):counts[item.get("category")]=counts.get(item.get("category"),0)+1
    new=[]
    groups=clusters(fetch())
    for group in groups:
        category=group[0]["category"]
        if counts.get(category,0)>=MAX_PER_CATEGORY:continue
        fingerprint=" ".join(sorted(tokens(" ".join(x["title"] for x in group))))
        story_id=sha256((category+"|"+fingerprint).encode()).hexdigest()[:14]
        if story_id in seen:continue
        try:report=generate(group)
        except Exception as error:print(f"Skipped {category}: {error}",file=sys.stderr);continue
        urls=sorted({x["url"] for x in group})
        date=max((x["published"] for x in group if x["published"]),default=datetime.now(timezone.utc).isoformat())[:10]
        image,image_alt=create_image(category,report["title"],story_id)
        item={**report,"storyId":story_id,"category":category,"categoryLabel":CATEGORIES[category],"published":date,"source":"نكسوس بريس","sources":[{"publisher":x["publisher"],"title":x["title"],"url":x["url"]} for x in group],"sourceConfidence":"multiple_sources" if len({x["domain"] for x in group})>1 else "single_source","url":f"./article-{category}-{story_id}.html","image":image,"imageAlt":image_alt}
        (ROOT/item["url"].removeprefix("./")).write_text(article_html(item),encoding="utf-8")
        new.append(item);seen.add(story_id);counts[category]=counts.get(category,0)+1
    merged=new+[x for x in existing if isinstance(x,dict) and x.get("storyId") not in {y["storyId"] for y in new}]
    DATA_PATH.write_text(json.dumps(merged[:MAX_TOTAL],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    state["seen_story_ids"]=list(seen)[-3000:]
    STATE_PATH.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Published {len(new)} new articles; dataset now has {min(len(merged),MAX_TOTAL)} items.")

if __name__=="__main__":main()
