"""Nexus Press pipeline - self-healing multi-provider version.

Each run: reads RSS feeds of famous WORLD and ARABIC newspapers (no Moroccan outlet is used as a source),
picks fresh stories (categories with < 6 articles first), writes an ORIGINAL Arabic article, checks it against the
sources for copied wording, creates a UNIQUE illustration (no watermark, duplicate-checked), compresses it to WebP,
updates articles.json, creates the daily poll and rebuilds the site.

Morocco news (category ar_local) = what is trending in Morocco on Google (Google Trends RSS), written from the
non-Moroccan coverage of that trend.

TEXT providers (tried in this order, only those with a key): Gemini -> Groq -> OpenRouter
IMAGE providers (IMAGE_PROVIDERS, default "genai,pollinations": official Google Gen AI JS SDK through gen_image.mjs first, then Pollinations with your key; also available: gemini), then a local SVG that is replaced automatically on a later run.

Env: GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY, POLLINATIONS_API_KEY (sk_... key => no watermark, no rate limit),
GEMINI_TEXT_MODEL / GEMINI_IMAGE_MODEL (optional), MAX_PER_RUN (2), MIN_PER_CATEGORY (6), KEEP_PER_CATEGORY (15),
PAUSE_SECONDS (8), CLOUDINARY_URL (or CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET) -> images are also
uploaded to Cloudinary and served from its CDN (auto format/size, much faster), REGEN_IMAGES = none | svg (default: replaces up to 8 placeholder images per run) | svgall (all placeholders) | all (redraw every image once)
"""
import base64
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import build_site

ROOT = Path(__file__).parent
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
POLL_KEY = next((os.getenv(n, "").strip() for n in ("POLLINATIONS_API_KEY", "POLLINATIONS_KEY", "POLLINATIONS_TOKEN") if os.getenv(n, "").strip()), "")
IMAGE_PROVIDERS = [p.strip() for p in (os.getenv("IMAGE_PROVIDERS") or "genai,pollinations").split(",") if p.strip()]
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN") or "2")
MIN_PER_CAT = int(os.getenv("MIN_PER_CATEGORY") or "6")
KEEP = int(os.getenv("KEEP_PER_CATEGORY") or "15")
PAUSE = int(os.getenv("PAUSE_SECONDS") or "8")
REGEN = (os.getenv("REGEN_IMAGES") or "svg").lower()
MIN_WORDS, MAX_WORDS = 800, 1500
MIN_WORDS_TREND, MAX_WORDS_TREND = 550, 1300   # trend stories have thinner source material
MAX_OVERLAP = 0.05  # max share of 5-word sequences allowed to match the source text
DUP_DIST = 8        # images whose 64-bit hash differs by <= 8 bits from an existing one are treated as duplicates
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 NexusPressBot/2.0"

COMPAT = {  # OpenAI-compatible free providers: base url, key, preferred model name fragments
    "groq": ("https://api.groq.com/openai/v1", lambda: GROQ_KEY,
             ["gpt-oss-120b", "llama-3.3-70b", "qwen", "llama-4", "gpt-oss-20b", "llama-3.1-8b"]),
    "openrouter": ("https://openrouter.ai/api/v1", lambda: OPENROUTER_KEY,
                   ["llama-3.3-70b", "gpt-oss-120b", "qwen", "deepseek", "gemma", "mistral"]),
}
BAD_MODEL_WORDS = ("whisper", "guard", "tts", "orpheus", "safeguard", "compound", "embed", "moderation", "image", "vision")

# ----------------------------------------------------------------------------- sources: famous world + Arabic outlets only
BBC = "https://feeds.bbci.co.uk"
NYT = "https://rss.nytimes.com/services/xml/rss/nyt"
GUARD = "https://www.theguardian.com"
FEEDS = {
    "ar_world": [("BBC عربي", f"{BBC}/arabic/rss.xml"), ("BBC News", f"{BBC}/news/world/rss.xml"),
                 ("الجزيرة", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b682-8f6c4a1f1e9d"),
                 ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml"),
                 ("فرانس 24", "https://www.france24.com/ar/rss"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-all"),
                 ("سكاي نيوز عربية", "https://www.skynewsarabia.com/web/rss"), ("CNN بالعربية", "https://arabic.cnn.com/api/v1/rss/rss.xml"),
                 ("الشرق الأوسط", "https://aawsat.com/feed"), ("العربية", "https://www.alarabiya.net/feed/rss2/ar.xml"),
                 ("The Guardian", f"{GUARD}/world/rss"), ("The New York Times", f"{NYT}/World.xml")],
    "ar_economy": [("BBC عربي", f"{BBC}/arabic/business/rss.xml"), ("BBC Business", f"{BBC}/news/business/rss.xml"),
                   ("The Guardian", f"{GUARD}/business/rss"), ("The New York Times", f"{NYT}/Business.xml"),
                   ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
                   ("الشرق الأوسط", "https://aawsat.com/feed/business"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-eco")],
    "ar_tech": [("BBC عربي", f"{BBC}/arabic/science-and-tech/rss.xml"), ("BBC Technology", f"{BBC}/news/technology/rss.xml"),
                ("The Guardian", f"{GUARD}/technology/rss"), ("The New York Times", f"{NYT}/Technology.xml"),
                ("Wired", "https://www.wired.com/feed/rss"), ("The Verge", "https://www.theverge.com/rss/index.xml")],
    "ar_sports": [("BBC عربي", f"{BBC}/arabic/sports/rss.xml"), ("BBC Sport", f"{BBC}/sport/rss.xml"),
                  ("The Guardian", f"{GUARD}/sport/rss"), ("The New York Times", f"{NYT}/Sports.xml"),
                  ("ESPN", "https://www.espn.com/espn/rss/news"), ("سكاي نيوز عربية", "https://www.skynewsarabia.com/web/rss/sport")],
    "ar_arts": [("BBC عربي", f"{BBC}/arabic/arts/rss.xml"), ("BBC Arts", f"{BBC}/news/entertainment_and_arts/rss.xml"),
                ("The Guardian", f"{GUARD}/culture/rss"), ("The New York Times", f"{NYT}/Arts.xml"),
                ("Variety", "https://variety.com/feed/"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-cul")],
}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=MA"   # what Morocco is searching for right now
BLOCK_TOPICS = ("porn", "sex", "xxx", "onlyfans", "nude", "سكس", "نيك", "اباح", "إباح", "عاري", "فضيحة جنس")

ICONS = {"ar_local": "🇲🇦", "ar_world": "🌍", "ar_economy": "💹", "ar_tech": "💻", "ar_sports": "⚽", "ar_arts": "🎭"}
COLORS = {"ar_local": "#0b3c7a", "ar_world": "#0369a1", "ar_economy": "#047857",
          "ar_tech": "#6d28d9", "ar_sports": "#b45309", "ar_arts": "#be185d"}

SYSTEM = """أنت صحفي عربي محترف بخبرة طويلة في غرف الأخبار، تكتب مقالات إخبارية أصلية بأسلوب صحفي رصين وسلس.
القواعد:
- اكتب بصياغتك الخاصة تماماً. لا تنقل جملاً من المصدر ولا تترجمها حرفياً ولا تحاكِ ترتيب فقراته.
- استخدم فقط الوقائع والأرقام والأسماء الواردة في المواد المقدمة، ويمكنك إضافة خلفية عامة معروفة ومؤكدة فقط.
- لا تخترع اقتباسات ولا أرقاماً ولا أسماء ولا تواريخ ولا تصريحات. إن لم تكن متأكداً فاحذف المعلومة.
- الفقرة الأولى «هوك» جذاب يشدّ القارئ (مشهد، مفارقة، سؤال أو معلومة لافتة) ثم يدخل في صلب الخبر، وتأتي بلا عنوان.
- بعد الفقرة الأولى قسّم المقال إلى 5 أو 6 أقسام، يبدأ كل قسم بعنوان فرعي قصير (من 3 إلى 6 كلمات) يُكتب كعنصر مستقل في القائمة يبدأ بـ '## '، ثم فقرة أو فقرتان تحته. الأقسام بهذا الترتيب:
  1) تفاصيل الخبر: ماذا حدث بالضبط ومتى وأين ومن المعنيون.
  2) خلفية عن الموضوع: كيف كان الوضع سابقاً وما الذي قاد إلى هذا الخبر (مثلاً: إذا كان قراراً جديداً فاشرح باختصار ما كان معمولاً به قبله).
  3) المواقف والأطراف: ما قالته الأطراف أو الجهات المعنية كما ورد في المواد المرجعية فقط.
  4) تأثير الخبر على القارئ: كيف قد يمسّ هذا الخبر المواطنين أو القرّاء في حياتهم اليومية أو في قراراتهم، بصياغة حذرة ("قد"، "من المتوقع") دون جزم أو وعود.
  5) قراءة وتحليل: دلالات الخبر ومقارنته بأحداث مشابهة معروفة.
  6) ما الذي ينتظرنا: الخطوات أو التطورات المحتملة القادمة.
- الفقرات قصيرة ومريحة للقراءة على الهاتف: من جملتين إلى 4 جمل، بلا كتل نصية طويلة. العناوين الفرعية جمل وصفية قصيرة لا علامات ترقيم زائدة فيها.
- الخلفية والتأثير يعتمدان فقط على المواد المقدمة أو على معلومات عامة معروفة ومؤكدة؛ وإن لم تتوفر تفاصيل فاشرح السياق العام دون اختلاق وقائع محددة.
- الطول بين {LO} و{HI} كلمة. لا تخاطب القارئ بعبارات مثل «بصفتي». لا تنسب المقال لشخص حقيقي. التزم الحياد ولا تُبدِ رأياً سياسياً أو دينياً.
- أعد JSON فقط بالشكل: {"title": "...", "summary": "جملتان كحد أقصى", "image_prompt": "English prompt", "body": ["فقرة افتتاحية", "## عنوان فرعي", "فقرة", "## عنوان فرعي", "فقرة", ...]}
- image_prompt: وصف إنجليزي مفصّل (40 إلى 70 كلمة) لمشهد فوتوغرافي تحريري يعبّر مباشرة عن حدث المقال نفسه، بعناصر بصرية ملموسة وخاصة بهذا الخبر
  (المكان، الأشياء، الأجواء، الإضاءة، زاوية التصوير)، وليس مشهداً عاماً يصلح لأي خبر. بدون نصوص أو حروف أو شعارات أو علامات تجارية،
  وبدون وجوه أشخاص حقيقيين أو شخصيات عامة (استعمل أشخاصاً مجهولين من الخلف أو من بعيد أو أيدٍ وأدوات ومعالم)."""

TREND_NOTE = """

ملاحظة خاصة: هذا الموضوع يتصدّر اهتمام الباحثين في المغرب على Google اليوم. اكتب المقال للقارئ المغربي والعربي بما يشرح له الخبر وسياقه
اعتماداً على المواد المرجعية فقط. لا تذكر أرقام البحث. إذا كانت المواد قليلة فاكتب مقالاً أقصر وأدق بدل اختراع معلومات."""

POLL_SYSTEM = """أنت محرر تفاعل في جريدة إلكترونية عربية. اصنع استطلاع رأي يومياً واحداً مرتبطاً بموضوع بارز من العناوين المقدمة.
- سؤال واحد واضح ومحايد لا يوحي بإجابة، ولا يتهم أحداً، ولا يمس المقدسات أو الأديان، ولا يسخر من ضحايا.
- من 3 إلى 4 خيارات قصيرة (حتى 6 كلمات لكل خيار) بينها خيار محايد مثل «لا رأي لي» أو «أحتاج إلى مزيد من المعلومات».
- أعد JSON فقط: {"question": "...", "options": ["...", "..."]}"""

IMG_STYLE = {
    "ar_local": "documentary photography, authentic everyday scene",
    "ar_world": "photojournalism, wide dramatic news photograph",
    "ar_economy": "business photojournalism, markets, ports, factories or city skyline",
    "ar_tech": "modern technology editorial photograph, clean futuristic atmosphere",
    "ar_sports": "dynamic sports photography, stadium energy, motion",
    "ar_arts": "cultural editorial photography, rich color and atmosphere",
}
ANGLES = ["wide establishing shot", "low-angle shot", "aerial drone view", "intimate close-up of a telling object", "shot from behind a silhouette",
          "symmetrical centered composition", "telephoto compressed perspective", "shallow depth of field detail shot"]
LIGHTS = ["soft early-morning light", "dramatic overcast sky", "warm golden hour", "cool blue hour", "crisp midday sunlight",
          "moody night with practical lights", "diffused window light", "stormy contrasty light"]

STATE = {"models": None, "gemini_text": None, "compat": {}, "dead_text": set(), "dead_image": set(),
         "poll_last": 0.0, "poll_fail": 0, "feeds": {}, "hashes": None}


# ----------------------------------------------------------------------------- http helpers
class ApiError(RuntimeError):
    def __init__(self, code, body, label=""):
        super().__init__(f"{label} HTTP {code}: {str(body)[:300]}")
        self.code, self.body = code, str(body)


def request(url, payload=None, headers=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    h = {"User-Agent": UA, **(headers or {})}
    if payload is not None:
        h["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as ex:
        raise ApiError(ex.code, ex.read().decode("utf-8", "ignore"), url.split("?")[0]) from None


def call_json(url, payload, headers, label, tries=3):
    """POST json and parse the reply. Retries only real rate-limits (not 'limit: 0' / 404 / 403)."""
    for n in range(1, tries + 1):
        try:
            return json.loads(request(url, payload, headers, timeout=300))
        except ApiError as ex:
            retriable = ex.code in (429, 500, 502, 503) and "limit: 0" not in ex.body
            m = re.search(r'"retryDelay":\s*"(\d+)', ex.body)
            wait = int(m.group(1)) + 2 if m else 25 * n
            if retriable and n < tries and wait <= 120:
                print(f"{label}: HTTP {ex.code}, waiting {wait}s then retrying")
                time.sleep(wait)
                continue
            raise
    raise ApiError(0, "retries exhausted", label)


# ----------------------------------------------------------------------------- Gemini (auto-discovery)
def gemini_models():
    if STATE["models"] is not None:
        return STATE["models"]
    out, token = {}, ""
    try:
        for _ in range(6):
            url = f"{GEMINI_API}/models?pageSize=100" + (f"&pageToken={token}" if token else "")
            res = json.loads(request(url, headers={"x-goog-api-key": GEMINI_KEY}, timeout=30))
            for m in res.get("models", []):
                out[m["name"].split("/", 1)[-1]] = m.get("supportedGenerationMethods", [])
            token = res.get("nextPageToken", "")
            if not token:
                break
    except Exception as ex:
        print("model listing failed (continuing with built-in names):", ex)
    STATE["models"] = out
    return out


def gemini_text_candidates():
    pat = re.compile(r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?(-preview[\w.-]*)?$")
    found = []
    for name, methods in gemini_models().items():
        m = pat.match(name)
        if m and "generateContent" in methods:
            found.append((-float(m.group(1)), bool(m.group(2)), bool(m.group(3)), name))
    found.sort()
    seeds = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.6-flash",
             "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash"]
    out = []
    for n in [os.getenv("GEMINI_TEXT_MODEL")] + [f[3] for f in found] + seeds:
        if n and n not in out:
            out.append(n)
    return out[:12]


def reply_text(res):
    cands = res.get("candidates") or []
    if not cands or "content" not in cands[0]:
        return ""
    return "".join(p.get("text", "") for p in cands[0]["content"].get("parts", []) if not p.get("thought"))


def gemini_text(system, user):
    order = [STATE["gemini_text"]] if STATE["gemini_text"] else []
    order += [m for m in gemini_text_candidates() if m not in order]
    last = ApiError(0, "no candidate model", "gemini")
    for model in order:
        try:
            res = call_json(f"{GEMINI_API}/models/{model}:generateContent", {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json", "maxOutputTokens": 16384}},
                {"x-goog-api-key": GEMINI_KEY}, model)
        except ApiError as ex:
            print(f"gemini model '{model}' unusable (HTTP {ex.code}) -> trying next")
            last = ex
            if STATE["gemini_text"] == model:
                STATE["gemini_text"] = None
            continue
        text = reply_text(res)
        if text:
            if STATE["gemini_text"] != model:
                print(f"using gemini model: {model}")
            STATE["gemini_text"] = model
            return text
        print(f"gemini model '{model}' returned no text (blocked?):", json.dumps(res.get("promptFeedback", ""))[:200])
        last = ApiError(0, "empty response", model)
    raise last


# ----------------------------------------------------------------------------- Groq / OpenRouter
def compat_text(name, system, user):
    base, keyf, prefs = COMPAT[name]
    key = keyf()
    auth = {"Authorization": f"Bearer {key}"}
    if name not in STATE["compat"]:
        ids = [m["id"] for m in json.loads(request(f"{base}/models", headers=auth, timeout=30)).get("data", [])]
        if name == "openrouter":
            ids = [i for i in ids if i.endswith(":free")]
        ids = [i for i in ids if not any(b in i.lower() for b in BAD_MODEL_WORDS)]
        order = []
        for p in prefs:
            order += [i for i in ids if p in i.lower() and i not in order]
        STATE["compat"][name] = order[:5]
        print(f"{name} candidate models:", STATE["compat"][name])
    last = ApiError(0, "no candidate model", name)
    for model in STATE["compat"][name]:
        payload = {"model": model, "temperature": 0.8, "max_tokens": 8000,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "response_format": {"type": "json_object"}}
        try:
            try:
                res = call_json(f"{base}/chat/completions", payload, auth, f"{name}:{model}")
            except ApiError as ex:
                if ex.code != 400:
                    raise
                payload.pop("response_format")
                res = call_json(f"{base}/chat/completions", payload, auth, f"{name}:{model}")
            text = (res["choices"][0]["message"].get("content") or "").strip()
            if text:
                return text
        except (ApiError, KeyError, IndexError) as ex:
            print(f"{name} model '{model}' unusable -> trying next ({str(ex)[:120]})")
            last = ex if isinstance(ex, ApiError) else ApiError(0, str(ex), name)
    raise last


def generate_text(system, user):
    providers = []
    if GEMINI_KEY:
        providers.append("gemini")
    if GROQ_KEY:
        providers.append("groq")
    if OPENROUTER_KEY:
        providers.append("openrouter")
    last = None
    for p in providers:
        if p in STATE["dead_text"]:
            continue
        try:
            return gemini_text(system, user) if p == "gemini" else compat_text(p, system, user)
        except Exception as ex:
            print(f"provider '{p}' failed:", str(ex)[:200])
            STATE["dead_text"].add(p)
            last = ex
    raise last or RuntimeError("No text provider available (add GEMINI_API_KEY, GROQ_API_KEY or OPENROUTER_API_KEY).")


# ----------------------------------------------------------------------------- feeds, trends & article
def local(tag):
    return tag.split("}")[-1]


def child(el, *names):
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def read_feed(name, url):
    """RSS or Atom -> list of stories. Moroccan outlets are dropped. Cached per run."""
    if url in STATE["feeds"]:
        return STATE["feeds"][url]
    out = []
    try:
        root = ET.fromstring(request(url, timeout=30))
    except Exception as ex:
        print("feed failed", name, str(ex)[:100])
        STATE["feeds"][url] = out
        return out
    for it in root.iter():
        if local(it.tag) not in ("item", "entry"):
            continue
        t = child(it, "title")
        lk = child(it, "link")
        link = ""
        if lk is not None:
            link = (lk.get("href") or lk.text or "").strip()
        d = child(it, "description", "summary", "content")
        title = (t.text or "").strip() if t is not None else ""
        if not (title and link) or build_site.is_moroccan(link, name):
            continue
        desc = re.sub(r"<[^>]+>", " ", (d.text or "") if d is not None else "")
        out.append({"publisher": name, "title": title, "url": link, "desc": re.sub(r"\s+", " ", desc).strip()})
    print(f"feed ok: {name} ({len(out)})" if out else f"feed empty: {name}")
    STATE["feeds"][url] = out
    return out


def interleave(lists):
    out, i = [], 0
    while any(i < len(x) for x in lists):
        out += [x[i] for x in lists if i < len(x)]
        i += 1
    return out


def read_trends():
    """Google Trends 'trending now' for Morocco -> [{query, traffic, news:[{publisher,title,url,desc}]}]"""
    out = []
    try:
        root = ET.fromstring(request(TRENDS_URL, headers={"Accept-Language": "ar,fr;q=0.8"}, timeout=30))
    except Exception as ex:
        print("google trends failed:", str(ex)[:120])
        return out
    for it in root.iter("item"):
        d = {"query": "", "traffic": "", "news": []}
        for ch in it:
            tag = local(ch.tag)
            if tag == "title":
                d["query"] = (ch.text or "").strip()
            elif tag == "approx_traffic":
                d["traffic"] = (ch.text or "").strip()
            elif tag == "news_item":
                n = {local(x.tag): (x.text or "").strip() for x in ch}
                if n.get("news_item_url"):
                    d["news"].append({"publisher": n.get("news_item_source") or urllib.parse.urlparse(n["news_item_url"]).netloc,
                                      "title": n.get("news_item_title", ""), "url": n["news_item_url"],
                                      "desc": n.get("news_item_snippet") or n.get("news_item_title", "")})
        if d["query"] and not any(b in d["query"].lower() for b in BLOCK_TOPICS):
            out.append(d)
    print(f"google trends MA: {len(out)} trends")
    return out


def tokens(t):
    return {w for w in re.findall(r"[A-Za-z\u0600-\u06FF]{4,}", t.lower())}


def pick_trend(used):
    """Next unused Moroccan trend that has coverage from NON-Moroccan outlets."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    world = None
    for t in read_trends():
        key = f"trend:{t['query']}:{day}"
        if key in used:
            continue
        srcs = [n for n in t["news"] if not build_site.is_moroccan(n["url"], n["publisher"]) and n["url"] not in used][:3]
        if not srcs:  # look for the same story in the big world/Arabic feeds
            if world is None:
                world = interleave([read_feed(n, u) for n, u in FEEDS["ar_world"]])
            tk = tokens(t["query"])
            need = 1 if len(tk) <= 2 else 2
            srcs = [i for i in world if i["url"] not in used and tk and len(tk & tokens(i["title"] + " " + i["desc"])) >= need][:2]
        if srcs:
            return t, srcs, key
        used.add(key)
        print("trend skipped (only Moroccan coverage):", t["query"])
    return None


def page_text(url):
    try:
        raw = request(url, timeout=30).decode("utf-8", "ignore")
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
    text = re.sub(r"(?is)<think>.*?</think>", "", text).strip()
    a, b = text.find("{"), text.rfind("}")
    return json.loads(text[a:b + 1])


def write_article(cat_name, sources, trend=None):
    lo, hi = (MIN_WORDS_TREND, MAX_WORDS_TREND) if trend else (MIN_WORDS, MAX_WORDS)
    system = SYSTEM.replace("{LO}", str(lo)).replace("{HI}", str(hi))
    material = "\n\n".join(f"[{s['publisher']}] {s['title']}\n{s['text'] or s['desc']}" for s in sources)
    user = f"القسم: {cat_name}\n"
    if trend:
        user += f"الموضوع الرائج في المغرب على Google: {trend['query']}\n"
        system += TREND_NOTE
    user += f"المواد المرجعية:\n{material}\n\nاكتب المقال الآن."
    best = None
    for attempt in range(3):
        text = generate_text(system, user)
        try:
            art = parse_json(text)
            body = [str(p) for p in art["body"]]
            art["title"], art["summary"] = str(art["title"]), str(art.get("summary", ""))
        except Exception as ex:
            print("bad JSON from model, retrying:", str(ex)[:100])
            continue
        n, ov = words(body), overlap(body, sources)
        heads = sum(1 for p in body if p.lstrip().startswith("## "))
        print(f"attempt {attempt + 1}: {n} words, {heads} subheadings, overlap {ov:.1%}")
        if heads < 4 and attempt < 2:
            user += "\n\nملاحظة: المقال يحتاج 5 إلى 6 عناوين فرعية مستقلة تبدأ بـ '## ' كما في البنية المطلوبة (تفاصيل، خلفية، مواقف، تأثير، تحليل، ما بعد الخبر)."
            continue
        if lo <= n <= hi and ov <= MAX_OVERLAP:
            art["body"] = body
            return art
        if n >= lo and ov <= MAX_OVERLAP:
            best = {**art, "body": body}
        user += (f"\n\nملاحظة: المحاولة السابقة كانت {n} كلمة وتشابه {ov:.0%} مع المصدر. "
                 f"المطلوب بين {lo} و{hi} كلمة وبصياغة جديدة كلياً بعيدة عن عبارات المصدر.")
    return best


# ----------------------------------------------------------------------------- images (unique, expressive, no watermark)
def dhash(img):
    g = list(img.convert("L").resize((9, 8)).tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (g[r * 9 + c] > g[r * 9 + c + 1])
    return bits


def known_hashes():
    if STATE["hashes"] is None:
        STATE["hashes"] = {}
        try:
            from PIL import Image
            for p in (ROOT / "images").glob("*.webp"):
                try:
                    STATE["hashes"][p.stem] = dhash(Image.open(p))
                except Exception:
                    pass
        except ImportError:
            pass
    return STATE["hashes"]


def is_duplicate(h, skip=""):
    return any(bin(h ^ o).count("1") <= DUP_DIST for k, o in known_hashes().items() if k != skip)


def build_prompt(prompt, art_id, cat, attempt):
    r = random.Random(f"{art_id}-{attempt}")
    return ("Editorial news photograph, ultra detailed, natural colors, no text, no letters, no numbers, no logos, no watermark, "
            "no brand names, no recognizable real people. " + IMG_STYLE.get(cat, "") + ". " + r.choice(ANGLES) + ", " + r.choice(LIGHTS) +
            ". Scene: " + prompt)


def image_gemini(prompt):
    models = gemini_models()
    cands = [n for n, m in models.items() if "image" in n and "generateContent" in m and not any(x in n for x in ("imagen", "veo"))]
    cands.sort(key=lambda n: ("flash" not in n, "preview" in n, n))
    order = []
    for n in [os.getenv("GEMINI_IMAGE_MODEL")] + cands + ["gemini-2.5-flash-image"]:
        if n and n not in order:
            order.append(n)
    last = ApiError(0, "no image model", "gemini")
    for model in order[:5]:
        cfg = {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}
        for attempt in range(2):
            try:
                res = call_json(f"{GEMINI_API}/models/{model}:generateContent",
                                {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
                                {"x-goog-api-key": GEMINI_KEY}, model, tries=2)
                for p in (res.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                    d = p.get("inlineData") or p.get("inline_data")
                    if d and not p.get("thought"):
                        return base64.b64decode(d["data"]), False
                last = ApiError(0, "no image in response", model)
                break
            except ApiError as ex:
                last = ex
                if ex.code == 400 and "imageConfig" in cfg:
                    cfg.pop("imageConfig")
                    continue
                break
        print(f"gemini image model '{model}' unusable ({str(last)[:110]})")
    raise last


def image_genai(prompt, seed):
    """Illustration through the official Google Gen AI JS SDK (gen_image.mjs, needs Node 18+ and `npm i @google/genai`)."""
    tmp = ROOT / "images" / f".genai-{seed}.bin"
    tmp.parent.mkdir(exist_ok=True)
    try:
        r = subprocess.run(["node", str(ROOT / "gen_image.mjs"), str(tmp), prompt], capture_output=True, text=True, timeout=480,
                           env={**os.environ, "GEMINI_API_KEY": GEMINI_KEY})
    except Exception as ex:
        raise ApiError(0, str(ex), "genai") from None
    tail = (r.stderr or "").strip().splitlines()[-4:]
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise ApiError(0, " | ".join(tail), "genai")
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data, False


def image_pollinations(prompt, seed):
    """Returns (bytes, needs_watermark_crop). With a key: gen.pollinations.ai, nologo, no rate limit.
    Without a key (or if the key call fails): legacy anonymous endpoint (1 request / 15 s, watermark is cropped off)."""
    if POLL_KEY:
        wait = 4 - (time.time() - STATE["poll_last"])
        if wait > 0:
            time.sleep(wait)
        STATE["poll_last"] = time.time()
        q = urllib.parse.urlencode({"model": "flux", "width": 1280, "height": 720, "seed": seed, "nologo": "true"})
        try:
            data = request("https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt[:700]) + "?" + q,
                           headers={"Authorization": f"Bearer {POLL_KEY}"}, timeout=240)
            if len(data) > 15000:
                return data, False
            print("pollinations (key): response too small, falling back")
        except ApiError as ex:
            print(f"pollinations (key) failed HTTP {ex.code}: {ex.body[:150]} -> falling back to anonymous endpoint")
    wait = 16 - (time.time() - STATE["poll_last"])
    if wait > 0:
        time.sleep(wait)
    STATE["poll_last"] = time.time()
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:450]) +
           f"?width=1280&height=720&nologo=true&model=flux&seed={seed}")
    data = request(url, timeout=180)
    if len(data) < 15000:
        raise ApiError(0, "image too small / not an image", "pollinations")
    return data, True


def fallback_svg(stem, cat):
    """Placeholder used only when no provider produced a picture. Unique per article (seeded by its id), no text or emoji,
    and replaced automatically by a real illustration on a later run (see heal_images)."""
    r = random.Random(stem)
    h1 = r.randint(0, 359)
    h2 = (h1 + r.randint(35, 90)) % 360
    shapes = "".join(
        f'<circle cx="{r.randint(0, 1000)}" cy="{r.randint(0, 560)}" r="{r.randint(50, 260)}" fill="#fff" opacity="{r.choice([.04, .06, .08, .1])}"/>'
        for _ in range(7))
    shapes += "".join(
        f'<rect x="{r.randint(0, 900)}" y="{r.randint(0, 480)}" width="{r.randint(80, 360)}" height="{r.randint(6, 40)}" rx="8" fill="#fff" '
        f'opacity="{r.choice([.05, .08, .12])}" transform="rotate({r.randint(-35, 35)} 500 280)"/>' for _ in range(4))
    x1, y1, x2, y2 = r.choice([(0, 0, 1, 1), (0, 1, 1, 0), (0, 0, 0, 1), (1, 0, 0, 1)])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560"><defs><linearGradient id="g" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
            f'<stop offset="0" stop-color="hsl({h1},62%,36%)"/><stop offset="1" stop-color="hsl({h2},70%,14%)"/></linearGradient></defs>'
            f'<rect width="1000" height="560" fill="url(#g)"/>{shapes}</svg>')


def make_image(prompt, art_id, cat, file_stem=None):
    out = ROOT / "images"
    out.mkdir(exist_ok=True)
    stem = file_stem or art_id
    try:
        from PIL import Image
    except ImportError:
        Image = None
        print("Pillow missing -> using fallback image")
    if Image:
        known_hashes()
        for prov in IMAGE_PROVIDERS:
            if prov in STATE["dead_image"] or (prov in ("gemini", "genai") and not GEMINI_KEY):
                continue
            chosen, chosen_h = None, None
            for attempt in range(3):  # new seed + new angle/light each time until the picture is not a look-alike
                seed = int(hashlib.md5(f"{art_id}-{attempt}".encode()).hexdigest()[:6], 16)
                full = build_prompt(prompt, art_id, cat, attempt)
                try:
                    raw, crop = (image_gemini(full) if prov == "gemini" else image_genai(full, seed) if prov == "genai" else image_pollinations(full, seed))
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                except Exception as ex:
                    print(f"image provider '{prov}' failed:", str(ex)[:160])
                    if prov == "genai" and re.search(r"limit: 0|free.?tier|not.?found|permission|forbidden|api key|cannot find|ERR_MODULE|billing", str(ex), re.I):
                        print("genai cannot be used with this key/setup -> skipping it for this run, using the next provider")
                        STATE["dead_image"].add(prov)
                    elif prov in ("pollinations", "genai"):
                        STATE["poll_fail"] += 1
                        if STATE["poll_fail"] >= 3:
                            STATE["dead_image"].add(prov)
                    else:
                        STATE["dead_image"].add(prov)
                    break
                if prov in ("pollinations", "genai"):
                    STATE["poll_fail"] = 0
                if crop:  # anonymous Pollinations images carry a logo strip at the bottom
                    img = img.crop((0, 0, img.width, int(img.height * 0.925)))
                h = dhash(img)
                chosen, chosen_h = img, h
                if not is_duplicate(h, skip=art_id):
                    break
                print(f"image looks like an existing one, regenerating (attempt {attempt + 1})")
            if chosen is not None:
                chosen.thumbnail((1000, 1000))
                path = out / f"{stem}.webp"
                chosen.save(path, "WEBP", quality=74, method=6)
                STATE["hashes"][stem] = chosen_h
                return f"images/{path.name}"
    svg = out / f"{stem}.svg"
    svg.write_text(fallback_svg(stem, cat), encoding="utf-8")
    return f"images/{svg.name}"


def image_prompt_for(art):
    """English scene description for articles that were saved without one (older articles)."""
    if art.get("image_prompt"):
        return art["image_prompt"]
    try:
        res = parse_json(generate_text(
            'You write image prompts. Given an Arabic news headline and summary, answer ONLY JSON {"image_prompt": "..."} with a vivid 40-70 word English '
            "description of an editorial photograph that illustrates THIS specific story with concrete visual elements (place, objects, atmosphere, light). "
            "No text, logos, or recognizable real people.", f"{art['title']}\n{art.get('summary', '')}"))
        return str(res["image_prompt"])
    except Exception as ex:
        print("image prompt generation failed:", str(ex)[:100])
        return f"editorial photograph illustrating: {art['title']}"


def heal_images(arts):
    """REGEN_IMAGES=svg: replace up to 8 placeholder SVGs per run. svgall: all placeholders. all: redraw every image once."""
    if REGEN == "none" or not (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY):
        return
    todo = [(k, a) for k, v in arts.items() for a in v if (REGEN == "all" and not a.get("regen")) or a["image"].endswith(".svg")]
    limit = len(todo) if REGEN in ("all", "svgall") else 8
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M")
    for k, a in todo[:limit]:
        old = a["image"]
        new = make_image(image_prompt_for(a), a["id"], k, file_stem=f"{a['id']}-{stamp}")
        if new.endswith(".svg"):
            (ROOT / new).unlink(missing_ok=True)
            continue
        a["image"], a["regen"] = new, True
        a["cdn"] = cloudinary_upload(ROOT / new, "nexus/" + Path(new).stem)
        if old != new:
            (ROOT / old).unlink(missing_ok=True)
            (STATE["hashes"] or {}).pop(Path(old).stem, None)
        print("image regenerated:", a["id"])


# ----------------------------------------------------------------------------- Cloudinary (image CDN)
def cloudinary_cfg():
    cloud, key, sec = (os.getenv("CLOUDINARY_CLOUD_NAME", "").strip(), os.getenv("CLOUDINARY_API_KEY", "").strip(),
                       os.getenv("CLOUDINARY_API_SECRET", "").strip())
    m = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", os.getenv("CLOUDINARY_URL", "").strip())
    if m:
        key, sec, cloud = m.groups()
    return (cloud, key, sec) if cloud and key and sec else None


def cloudinary_upload(path, public_id):
    """Signed upload of a local image. Returns the secure CDN url, or '' (site then simply uses the local file)."""
    cfg = cloudinary_cfg()
    p = Path(path)
    if not cfg or not p.exists() or p.suffix == ".svg":
        return ""
    cloud, key, sec = cfg
    ts = str(int(time.time()))
    sig = hashlib.sha1(f"overwrite=true&public_id={public_id}&timestamp={ts}{sec}".encode()).hexdigest()
    boundary = "----np" + hashlib.md5(ts.encode()).hexdigest()
    parts = []
    for k, v in (("api_key", key), ("timestamp", ts), ("public_id", public_id), ("overwrite", "true"), ("signature", sig)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{p.name}"\r\nContent-Type: image/webp\r\n\r\n'.encode()
                 + p.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    try:
        req = urllib.request.Request(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload", data=b"".join(parts),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read()).get("secure_url", "")
    except urllib.error.HTTPError as ex:
        print("cloudinary upload failed:", ex.code, ex.read().decode("utf-8", "ignore")[:200])
    except Exception as ex:
        print("cloudinary upload failed:", str(ex)[:150])
    return ""


def sync_cloudinary(arts, limit=12):
    """Upload every article image that is not on the CDN yet (a few per run)."""
    if not cloudinary_cfg():
        return
    n = 0
    for v in arts.values():
        for a in v:
            if n >= limit:
                return
            if not a.get("cdn") and a["image"].endswith(".webp"):
                a["cdn"] = cloudinary_upload(ROOT / a["image"], "nexus/" + Path(a["image"]).stem)
                n += 1
                if a["cdn"]:
                    print("cloudinary ok:", a["id"])


# ----------------------------------------------------------------------------- daily poll
def ensure_poll(arts):
    pf = ROOT / "poll.json"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if json.loads(pf.read_text(encoding="utf-8")).get("id") == today:
            return
    except Exception:
        pass
    heads = [a["title"] for k in ("ar_world", "ar_economy", "ar_tech", "ar_sports", "ar_arts", "ar_local") for a in arts.get(k, [])[:2]]
    if not heads or not (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY):
        return
    try:
        res = parse_json(generate_text(POLL_SYSTEM, "العناوين:\n" + "\n".join(heads[:10])))
        q = str(res["question"]).strip()
        opts = [str(o).strip() for o in res["options"] if str(o).strip()][:5]
        if not (8 < len(q) < 160 and 3 <= len(opts) <= 5 and all(len(o) < 60 for o in opts)):
            raise ValueError("poll shape rejected")
        pf.write_text(json.dumps({"id": today, "question": q, "options": opts}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("daily poll:", q)
    except Exception as ex:  # build_site falls back to its built-in rotating question bank
        print("poll generation failed (using built-in question):", str(ex)[:150])


# ----------------------------------------------------------------------------- main
def main():
    if not (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY):
        build_site.build()
        raise SystemExit("ERROR: no AI key found. Add GEMINI_API_KEY (https://aistudio.google.com/apikey) in GitHub: "
                         "Settings > Secrets and variables > Actions > Secrets. Optional fallbacks: GROQ_API_KEY, OPENROUTER_API_KEY.")
    print("cloudinary:", "on" if cloudinary_cfg() else "off (set CLOUDINARY_URL or the 3 CLOUDINARY_* secrets)")
    print("image providers:", ",".join(IMAGE_PROVIDERS), "| node:", "ok" if subprocess.run(["node", "-v"], capture_output=True).returncode == 0 else "MISSING")
    jf, sf = ROOT / "articles.json", ROOT / "news-state.json"
    data = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    arts = {k: data.get("articles", {}).get(k, []) for k in build_site.CATEGORIES}
    used = set(json.loads(sf.read_text(encoding="utf-8")).get("used", [])) if sf.exists() else set()

    heal_images(arts)

    made, stuck, errors = 0, set(), []
    while made < MAX_PER_RUN and len(stuck) < len(arts) and len(errors) < 2:
        # neediest category first; once all have >= MIN_PER_CAT, rotate to the one with the oldest latest article
        cat = min((k for k in arts if k not in stuck),
                  key=lambda k: (len(arts[k]) >= MIN_PER_CAT, len(arts[k]), arts[k][0]["date"] if arts[k] else ""))
        trend, tkey = None, None
        if cat == "ar_local":
            pick = pick_trend(used)
            if not pick:
                print("no usable Moroccan trend right now")
                stuck.add(cat)
                continue
            trend, chosen, tkey = pick
        else:
            pool = interleave([[i for i in read_feed(n, u) if i["url"] not in used] for n, u in FEEDS[cat]])
            if not pool:
                print("no fresh stories for", cat)
                stuck.add(cat)
                continue
            main_item = pool[0]
            tk = tokens(main_item["title"])
            extra = next((i for i in pool[1:] if i["publisher"] != main_item["publisher"] and len(tk & tokens(i["title"])) >= 2), None)
            chosen = [main_item] + ([extra] if extra else [])
        for s in chosen:
            s["text"] = page_text(s["url"])
        try:
            art = write_article(build_site.CATEGORIES[cat], chosen, trend)
        except Exception as ex:  # providers down: do NOT burn the story, stop after 2 failures
            print("generation failed:", str(ex)[:300])
            errors.append(str(ex))
            continue
        used.update(i["url"] for i in chosen)
        if tkey:
            used.add(tkey)
        if not art:
            print("article rejected (length / similarity), skipping story")
            continue
        aid = f"{cat}-{datetime.now(timezone.utc):%Y%m%d%H%M}-{hashlib.md5(chosen[0]['url'].encode()).hexdigest()[:6]}"
        ip = art.get("image_prompt") or art["title"]
        arts[cat].insert(0, {
            "id": aid, "title": art["title"].strip(), "summary": art["summary"].strip(),
            "content": "\n\n".join(p.strip() for p in art["body"]),
            "image": (img := make_image(ip, aid, cat)), "cdn": cloudinary_upload(ROOT / img, "nexus/" + Path(img).stem), "image_alt": art["title"].strip(), "image_prompt": ip,
            "date": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in chosen]})
        made += 1
        print(f"published ({made}/{MAX_PER_RUN}):", art["title"])
        time.sleep(PAUSE)

    for cat in arts:
        for old in arts[cat][KEEP:]:
            (ROOT / old["image"]).unlink(missing_ok=True)
        arts[cat] = arts[cat][:KEEP]
    total = sum(len(v) for v in arts.values())
    sync_cloudinary(arts)
    ensure_poll(arts)
    jf.write_text(json.dumps({"categories": build_site.CATEGORIES, "articles": arts}, ensure_ascii=False, indent=1), encoding="utf-8")
    sf.write_text(json.dumps({"used": sorted(used)[-3000:]}), encoding="utf-8")
    build_site.build()
    if made == 0 and MAX_PER_RUN > 0:
        msg = "no new article this run.\n" + "\n".join(errors[-2:])
        if total == 0:  # first setup: fail loudly so the cause is visible
            raise SystemExit("ERROR: " + msg + "\nRead the lines above ('unusable', 'failed') to see the cause.")
        print("WARNING:", msg)  # site already has content: do not turn the hourly job red


if __name__ == "__main__":
    main()
