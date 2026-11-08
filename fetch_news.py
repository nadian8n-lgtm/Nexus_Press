"""Nexus Press pipeline - self-healing multi-provider version.

Each run: reads RSS feeds, picks fresh stories (categories with < 6 articles first),
writes an ORIGINAL 800-1500 word Arabic article, checks it against the sources for copied wording,
creates a unique illustration, compresses it to WebP, updates articles.json and rebuilds the site.

TEXT providers (tried in this order, only those with a key):
  1) Gemini  (GEMINI_API_KEY, Google AI Studio)  - model is AUTO-DISCOVERED, so renamed/retired models never break the run
  2) Groq    (GROQ_API_KEY, free)                - optional fallback
  3) OpenRouter (OPENROUTER_API_KEY, ':free' models) - optional fallback
IMAGE providers (IMAGE_PROVIDERS, default "gemini,pollinations"), then a local SVG as last resort.

Other env: GEMINI_TEXT_MODEL / GEMINI_IMAGE_MODEL (optional overrides), MAX_PER_RUN (2),
MIN_PER_CATEGORY (6), KEEP_PER_CATEGORY (15), PAUSE_SECONDS (8)
"""
import base64
import hashlib
import io
import json
import os
import re
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
IMAGE_PROVIDERS = [p.strip() for p in (os.getenv("IMAGE_PROVIDERS") or "gemini,pollinations").split(",") if p.strip()]
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN") or "2")
MIN_PER_CAT = int(os.getenv("MIN_PER_CATEGORY") or "6")
KEEP = int(os.getenv("KEEP_PER_CATEGORY") or "15")
PAUSE = int(os.getenv("PAUSE_SECONDS") or "8")
MIN_WORDS, MAX_WORDS = 800, 1500
MAX_OVERLAP = 0.05  # max share of 5-word sequences allowed to match the source text

COMPAT = {  # OpenAI-compatible free providers: base url, key, preferred model name fragments
    "groq": ("https://api.groq.com/openai/v1", lambda: GROQ_KEY,
             ["gpt-oss-120b", "llama-3.3-70b", "qwen", "llama-4", "gpt-oss-20b", "llama-3.1-8b"]),
    "openrouter": ("https://openrouter.ai/api/v1", lambda: OPENROUTER_KEY,
                   ["llama-3.3-70b", "gpt-oss-120b", "qwen", "deepseek", "gemma", "mistral"]),
}
BAD_MODEL_WORDS = ("whisper", "guard", "tts", "orpheus", "safeguard", "compound", "embed", "moderation", "image", "vision")

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

STATE = {"models": None, "gemini_text": None, "compat": {}, "dead_text": set(), "dead_image": set(),
         "poll_last": 0.0, "poll_fail": 0}


# ----------------------------------------------------------------------------- http helpers
class ApiError(RuntimeError):
    def __init__(self, code, body, label=""):
        super().__init__(f"{label} HTTP {code}: {str(body)[:300]}")
        self.code, self.body = code, str(body)


def request(url, payload=None, headers=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    h = {"User-Agent": "NexusPressBot/1.0", **(headers or {})}
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


# ----------------------------------------------------------------------------- feeds & article
def read_feed(name, url):
    out = []
    try:
        root = ET.fromstring(request(url, timeout=30))
    except Exception as ex:
        print("feed failed", name, str(ex)[:120])
        return out
    for it in root.iter("item"):
        t, l = it.findtext("title"), it.findtext("link")
        if t and l:
            desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
            out.append({"publisher": name, "title": t.strip(), "url": l.strip(), "desc": re.sub(r"\s+", " ", desc).strip()})
    return out


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


def write_article(cat_name, sources):
    material = "\n\n".join(f"[{s['publisher']}] {s['title']}\n{s['text'] or s['desc']}" for s in sources)
    user = f"القسم: {cat_name}\nالمواد المرجعية:\n{material}\n\nاكتب المقال الآن."
    best = None
    for attempt in range(3):
        text = generate_text(SYSTEM, user)
        try:
            art = parse_json(text)
            body = [str(p) for p in art["body"]]
            art["title"], art["summary"] = str(art["title"]), str(art.get("summary", ""))
        except Exception as ex:
            print("bad JSON from model, retrying:", str(ex)[:100])
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


# ----------------------------------------------------------------------------- images
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
                        return base64.b64decode(d["data"])
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


def image_pollinations(prompt, seed):
    wait = 16 - (time.time() - STATE["poll_last"])  # anonymous tier: 1 request / 15 s
    if wait > 0:
        time.sleep(wait)
    STATE["poll_last"] = time.time()
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:450]) +
           f"?width=1280&height=720&nologo=true&model=flux&seed={seed}")
    data = request(url, timeout=180)
    if len(data) < 15000:
        raise ApiError(0, "image too small / not an image", "pollinations")
    return data


def make_image(prompt, art_id, cat):
    out = ROOT / "images"
    out.mkdir(exist_ok=True)
    full = ("Realistic editorial photograph-style illustration for a news article, no text, no letters, no logos, "
            "no watermark, no brand names, no real or recognizable people. Scene: " + prompt)
    try:
        from PIL import Image
    except ImportError:
        Image = None
        print("Pillow missing -> using fallback image")
    if Image:
        for prov in IMAGE_PROVIDERS:
            if prov in STATE["dead_image"] or (prov == "gemini" and not GEMINI_KEY):
                continue
            try:
                raw = image_gemini(full) if prov == "gemini" else image_pollinations(full, int(hashlib.md5(art_id.encode()).hexdigest()[:6], 16))
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                img.thumbnail((1000, 1000))
                path = out / f"{art_id}.webp"
                img.save(path, "WEBP", quality=72, method=6)
                if prov == "pollinations":
                    STATE["poll_fail"] = 0
                return f"images/{path.name}"
            except Exception as ex:
                print(f"image provider '{prov}' failed:", str(ex)[:160])
                if prov == "pollinations":
                    STATE["poll_fail"] += 1
                    if STATE["poll_fail"] >= 2:
                        STATE["dead_image"].add(prov)
                else:
                    STATE["dead_image"].add(prov)
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


# ----------------------------------------------------------------------------- main
def main():
    if not (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY):
        build_site.build()
        raise SystemExit("ERROR: no AI key found. Add GEMINI_API_KEY (https://aistudio.google.com/apikey) in GitHub: "
                         "Settings > Secrets and variables > Actions > Secrets. Optional fallbacks: GROQ_API_KEY, OPENROUTER_API_KEY.")
    jf, sf = ROOT / "articles.json", ROOT / "news-state.json"
    data = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else {}
    arts = {k: data.get("articles", {}).get(k, []) for k in build_site.CATEGORIES}
    used = set(json.loads(sf.read_text(encoding="utf-8")).get("used", [])) if sf.exists() else set()

    made, stuck, errors = 0, set(), []
    while made < MAX_PER_RUN and len(stuck) < len(arts) and len(errors) < 2:
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
        for s in chosen:
            s["text"] = page_text(s["url"])
        try:
            art = write_article(build_site.CATEGORIES[cat], chosen)
        except Exception as ex:  # providers down: do NOT burn the story, stop after 2 failures
            print("generation failed:", str(ex)[:300])
            errors.append(str(ex))
            continue
        used.update(i["url"] for i in chosen)
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
    total = sum(len(v) for v in arts.values())
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
