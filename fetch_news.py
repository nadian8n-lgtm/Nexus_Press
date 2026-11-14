"""Nexus Press pipeline - self-healing multi-provider version.

Each run: reads RSS feeds of famous WORLD and ARABIC newspapers (no Moroccan outlet is used as a source in the
international / economy / tech / sports / arts sections), picks fresh stories (categories with < 6 articles first),
writes an ORIGINAL Arabic article, checks it against the sources for copied wording, builds a strong image prompt from
the HEADLINE + FIRST THREE PARAGRAPHS, creates a UNIQUE illustration (no watermark, sharp, duplicate-checked),
compresses it to WebP, updates articles.json, creates the daily poll and rebuilds the site.

Morocco news (category ar_local) = what is trending in Morocco on Google (Google Trends RSS), written from the
non-Moroccan coverage of that trend.

City news (category ar_cities) = accidents, crime, courts and security in Moroccan cities. Discovery: Google News
(hl=ar&gl=MA) + the national press RSS feeds for the full text; every article cites its sources. Moroccan outlets are
allowed ONLY in this section.

TEXT providers (tried in this order, only those with a key): Gemini -> Groq -> OpenRouter
IMAGE providers (IMAGE_PROVIDERS, default "gemini,genai,openai"): Gemini image generation first, then the optional Gen AI SDK
and ChatGPT images. Pollinations and random stock photos were removed: they returned generic or unrelated pictures (often
people who had nothing to do with the story). If no provider works, a local SVG placeholder is used and replaced on a later run.

Env: GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY,
OPENAI_API_KEY / OPENAI_IMAGE_MODEL (optional, ChatGPT images), GEMINI_TEXT_MODEL / GEMINI_IMAGE_MODEL (optional),
MAX_PER_RUN (6), MIN_PER_CATEGORY (6), KEEP_PER_CATEGORY (30),
PAUSE_SECONDS (8), CLOUDINARY_URL (or CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET) -> images are also
uploaded to Cloudinary and served from its CDN (auto format/size, much faster), REGEN_IMAGES = none | svg (default: replaces up to 8 placeholder images per run) | svgall (all placeholders) | all (redraw every image once)
"""
import base64
import hashlib
import html as htmllib
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
import cities
import curate

ROOT = Path(__file__).parent
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()   # optional: ChatGPT images (gpt-image-1), paid
# Gemini image generation first, then the Gen AI SDK and ChatGPT images.
# Pollinations and picsum are hard-disabled: their pictures were generic and unrelated to the headline.
IMAGE_PROVIDERS = [p.strip() for p in (os.getenv("IMAGE_PROVIDERS") or "gemini,genai,openai").split(",") if p.strip()]
IMAGE_PROVIDERS = [p for p in IMAGE_PROVIDERS if p not in ("pollinations", "picsum")]
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN") or "6")
MIN_PER_CAT = int(os.getenv("MIN_PER_CATEGORY") or "6")
KEEP = int(os.getenv("KEEP_PER_CATEGORY") or "30")
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
                 ("BBC Middle East", f"{BBC}/news/world/middle_east/rss.xml"),
                 ("الجزيرة", "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b682-8f6c4a1f1e9d"),
                 ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml"),
                 ("فرانس 24", "https://www.france24.com/ar/rss"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-all"),
                 ("سكاي نيوز عربية", "https://www.skynewsarabia.com/web/rss"), ("CNN بالعربية", "https://arabic.cnn.com/api/v1/rss/rss.xml"),
                 ("الشرق الأوسط", "https://aawsat.com/feed"), ("العربية", "https://www.alarabiya.net/feed/rss2/ar.xml"),
                 ("اندبندنت عربية", "https://www.independentarabia.com/rss"),
                 ("The Guardian", f"{GUARD}/world/rss"), ("Guardian Middle East", f"{GUARD}/world/middleeast/rss"),
                 ("The New York Times", f"{NYT}/World.xml"), ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
                 ("UN News عربي", "https://news.un.org/feed/subscribe/ar/news/all/rss.xml")],
    "ar_economy": [("BBC عربي", f"{BBC}/arabic/business/rss.xml"), ("BBC Business", f"{BBC}/news/business/rss.xml"),
                   ("The Guardian", f"{GUARD}/business/rss"), ("The New York Times", f"{NYT}/Business.xml"),
                   ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
                   ("الشرق الأوسط", "https://aawsat.com/feed/business"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-eco"),
                   ("العربية", "https://www.alarabiya.net/feed/rss2/ar.xml"),
                   ("Sky News Arabia اقتصاد", "https://www.skynewsarabia.com/web/rss/economy")],
    "ar_tech": [("BBC عربي", f"{BBC}/arabic/science-and-tech/rss.xml"), ("BBC Technology", f"{BBC}/news/technology/rss.xml"),
                ("The Guardian", f"{GUARD}/technology/rss"), ("The New York Times", f"{NYT}/Technology.xml"),
                ("Wired", "https://www.wired.com/feed/rss"), ("The Verge", "https://www.theverge.com/rss/index.xml"),
                ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index")],
    "ar_sports": [("BBC عربي", f"{BBC}/arabic/sports/rss.xml"), ("BBC Sport", f"{BBC}/sport/rss.xml"),
                  ("BBC Football", f"{BBC}/sport/football/rss.xml"),
                  ("The Guardian", f"{GUARD}/sport/rss"), ("Guardian Football", f"{GUARD}/football/rss"),
                  ("The New York Times", f"{NYT}/Sports.xml"),
                  ("ESPN", "https://www.espn.com/espn/rss/news"), ("ESPN Soccer", "https://www.espn.com/espn/rss/soccer/news"),
                  ("Sky Sports Football", "https://www.skysports.com/rss/12040"),
                  ("سكاي نيوز عربية", "https://www.skynewsarabia.com/web/rss/sport")],
    "ar_arts": [("BBC عربي", f"{BBC}/arabic/arts/rss.xml"), ("BBC Arts", f"{BBC}/news/entertainment_and_arts/rss.xml"),
                ("The Guardian", f"{GUARD}/culture/rss"), ("The New York Times", f"{NYT}/Arts.xml"),
                ("Variety", "https://variety.com/feed/"), ("DW عربية", "https://rss.dw.com/xml/rss-ar-cul")],
}

# موضوعات تُتابَع عبر Google News (صحف عالمية وعربية) حتى لا يبقى قسم كرة القدم أو الشرق الأوسط بلا أخبار.
# hl=en/gl=US للاستعلامات الإنجليزية، hl=ar/gl=MA للعربية. لا تُستخدم أي صحيفة مغربية هنا.
def gn(query, lang="ar", geo="MA"):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query) +
            f"&hl={lang}&gl={geo}&ceid={geo}:{lang}")


TOPIC_FEEDS = {
    "ar_world": [
        ("فلسطين غزة", gn("فلسطين OR غزة OR الضفة الغربية")),
        ("الشرق الأوسط", gn("الشرق الأوسط OR لبنان OR سوريا OR إيران OR العراق")),
        ("Middle East", gn("Middle East Gaza Lebanon Iran", "en", "US")),
        ("أوكرانيا", gn("أوكرانيا OR روسيا OR الناتو")),
    ],
    "ar_sports": [
        ("المنتخب المغربي", gn("المنتخب المغربي OR أسود الأطلس OR حكيمي OR بونو OR زياش")),
        ("الديربي المغربي", gn("الديربي المغربي OR الوداد OR الرجاء OR الجيش الملكي")),
        ("الدوري الإنجليزي", gn("الدوري الإنجليزي OR ليفربول OR مانشستر سيتي OR أرسنال OR تشيلسي")),
        ("ريال مدريد وبرشلونة", gn("ريال مدريد OR برشلونة OR الكلاسيكو OR دوري أبطال أوروبا")),
        ("نجوم العالم", gn("ميسي OR رونالدو OR مبابي OR هالاند OR نيمار")),
        ("Morocco football", gn("Morocco national team Hakimi Bounou World Cup", "en", "US")),
    ],
    "ar_economy": [
        ("الأسواق العالمية", gn("الأسواق العالمية OR النفط OR الذهب OR الدولار OR الفيدرالي")),
        ("الاقتصاد العربي", gn("الاقتصاد العربي OR الخليج OR صندوق النقد الدولي")),
    ],
    "ar_tech": [
        ("الذكاء الاصطناعي", gn("الذكاء الاصطناعي OR OpenAI OR تشات جي بي تي OR غوغل")),
        ("التقنية العالمية", gn("أبل OR سامسونغ OR مايكروسوفت OR ميتا OR إنترنت")),
    ],
    "ar_arts": [
        ("سينما وفنون", gn("مهرجان سينمائي OR فيلم OR مسلسل OR جائزة أوسكار OR موسيقى")),
    ],
}

TRENDS_URL = "https://trends.google.com/trending/rss?geo=MA"   # what Morocco is searching for right now
BLOCK_TOPICS = ("porn", "sex", "xxx", "onlyfans", "nude", "سكس", "نيك", "اباح", "إباح", "عاري", "فضيحة جنس")

ICONS = {"ar_local": "🇲🇦", "ar_cities": "🏙️", "ar_world": "🌍", "ar_economy": "💹", "ar_tech": "💻",
         "ar_sports": "⚽", "ar_arts": "🎭"}
COLORS = {"ar_local": "#0b3c7a", "ar_cities": "#9a3412", "ar_world": "#0369a1", "ar_economy": "#047857",
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

CITY_SYSTEM = """أنت محقق صحفي مغربي مخضرم في قسم الحوادث والقضايا، تكتب لصحيفة إلكترونية عربية كبرى.
أسلوبك: سرد أدبي مشدود، بلاغة بلا مبالغة، تفاصيل حسّية دقيقة، وإيقاع يدفع القارئ إلى آخر سطر، مع التزام صارم بأخلاقيات المهنة.
القواعد الإلزامية:
- اكتب بصياغتك الخاصة تماماً ولا تنقل جملاً من المصادر.
- استخدم فقط الوقائع والأرقام والأسماء والتصريحات الواردة في المواد المقدمة. لا تخترع أي معلومة، ولا تُكمل الفراغات من خيالك.
- قرينة البراءة: كل متهم بريء حتى تثبت إدانته. استخدم «المشتبه فيه» و«حسب المصادر» و«تشير المعطيات» بدل الجزم.
- لا تذكر أسماء الضحايا ولا القاصرين ولا تفاصيل تسمح بالتعرف عليهم، ولا أسماء متهمين لم تُعلنها السلطات رسمياً.
- لا تُدِن أحداً ولا تُصدر حكماً، ولا تُشهر بأشخاص أو عائلات أو مناطق. لا خطاب كراهية ولا مسّ بالمقدسات أو الأديان.
- لا وصف دموي مقزز ولا تفاصيل جنسية، وتجنّب الإثارة الرخيصة. الإثارة تكون في السرد لا في الإسفاف.
- لا تذكر أسماء الصحف داخل النص؛ يكفي أن يقول «حسب ما أوردته مصادر إعلامية».
البنية (5 إلى 6 أقسام، كل قسم يبدأ بـ '## ' في عنصر مستقل):
  1) المشهد الافتتاحي: ابدأ بمشهد حسّي أو لحظة زمنية تضع القارئ داخل الحدث، بلا عنوان.
  2) ما حدث بالضبط: التسلسل الزمني والمكان والأطراف، كما ورد في المواد.
  3) من المتضرر: أثر الحادث على السكان والضحايا وعائلاتهم، بلغة إنسانية حذرة.
  4) الأطراف الرسمية: ما قالته السلطات أو النيابة أو الدرك أو الشرطة، حرفياً إن ورد.
  5) السياق الاجتماعي: هل الحادث معزول أم يعكس ظاهرة أوسع؟ اعتمد على المعطيات المتوفرة فقط.
  6) ما ينتظره الملف: الإجراءات القضائية أو الأمنية المحتملة، بصيغة «من المتوقع» و«يُنتظر».
- الطول بين {LO} و{HI} كلمة. فقرات من جملتين إلى 4 جمل.
- أعد JSON فقط: {"title": "...", "summary": "جملتان", "image_prompt": "English prompt", "body": ["فقرة", "## عنوان", "فقرة", ...]}"""

PROMPT_SYSTEM = """You are the award-winning picture editor of an international news agency.
You receive a news headline and the first three paragraphs of an Arabic article.
Write ONE image-generation prompt (English, 55-85 words) for a single editorial photograph that could run on the front page next to THIS story.
How to build it:
- Read the headline and the three paragraphs, then extract: the place, the time of day, the weather, the main human activity, and 2-3 concrete objects that only belong to this story.
- Describe ONE frozen moment that tells the story without showing violence or identifiable faces.
- Specify: subject and action, setting and background, two or three props, light direction and quality, camera angle, lens (24mm/35mm/50mm/85mm), depth of field, colour palette, and emotional tone.
- Photorealistic documentary/photojournalism style, natural skin texture, sharp focus, high dynamic range.
- Never include: text, letters, numbers, logos, watermarks, brand names, flags with writing, identifiable real people or celebrities, posed fashion/beauty portraits, glamour or influencer photos, dead bodies, blood, weapons pointed at people, religious symbols being desecrated, or sexual content.
- The frame must show the event itself (a place, objects, action, atmosphere), never a person posing for the camera.
- Do not describe the article itself; describe what the camera sees.
Answer ONLY JSON: {"image_prompt": "..."}"""

TREND_NOTE = """

ملاحظة خاصة: هذا الموضوع يتصدّر اهتمام الباحثين في المغرب على Google اليوم. اكتب المقال للقارئ المغربي والعربي بما يشرح له الخبر وسياقه
اعتماداً على المواد المرجعية فقط. لا تذكر أرقام البحث. إذا كانت المواد قليلة فاكتب مقالاً أقصر وأدق بدل اختراع معلومات."""

POLL_SYSTEM = """أنت محرر تفاعل في جريدة إلكترونية عربية. اصنع استطلاع رأي يومياً واحداً مرتبطاً بموضوع بارز من العناوين المقدمة.
- سؤال واحد واضح ومحايد لا يوحي بإجابة، ولا يتهم أحداً، ولا يمس المقدسات أو الأديان، ولا يسخر من ضحايا.
- من 3 إلى 4 خيارات قصيرة (حتى 6 كلمات لكل خيار) بينها خيار محايد مثل «لا رأي لي» أو «أحتاج إلى مزيد من المعلومات».
- أعد JSON فقط: {"question": "...", "options": ["...", "..."]}"""

IMG_STYLE = {
    "ar_local": "documentary photography, authentic everyday Moroccan scene",
    "ar_cities": "investigative photojournalism, Moroccan street at night, police tape and city lights in the background, tense atmosphere",
    "ar_world": "photojournalism, wide dramatic news photograph",
    "ar_economy": "business photojournalism, markets, ports, factories or city skyline",
    "ar_tech": "modern technology editorial photograph, clean futuristic atmosphere",
    "ar_sports": "dynamic sports photography, stadium energy, motion",
    "ar_arts": "cultural editorial photography, rich color and atmosphere",
}
ANGLES = ["wide establishing shot", "low-angle shot", "aerial drone view", "intimate close-up of a telling object", "shot from behind a silhouette",
          "symmetrical centered composition", "telephoto compressed perspective", "shallow depth of field detail shot",
          "over-the-shoulder framing", "high-angle view from a balcony"]
PALETTES = ["muted teal and amber", "cool blue-grey with one warm accent", "desaturated earth tones", "deep shadows with sodium-orange highlights",
            "soft pastel dawn colours", "high-contrast black and sandy beige"]
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


def read_feed(name, url, allow_moroccan=False):
    """RSS or Atom -> list of stories. Cached per run. Moroccan outlets are dropped unless allow_moroccan."""
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
        if not (title and link) or (not allow_moroccan and build_site.is_moroccan(link, name)):
            continue
        desc = re.sub(r"<[^>]+>", " ", (d.text or "") if d is not None else "")
        out.append({"publisher": name, "title": title, "url": link, "desc": re.sub(r"\s+", " ", desc).strip()})
    print(f"feed ok: {name} ({len(out)})" if out else f"feed empty: {name}")
    STATE["feeds"][url] = out
    return out


def read_gn(label, url, allow_moroccan=False):
    """Google News RSS -> stories with the real publisher name (its <source> element).
    Google News links are discovery links; page_text() usually cannot read them, so the article is
    written from the headline + snippet (or from the national feed when allow_moroccan is used)."""
    key = "gn:" + url
    if key in STATE["feeds"]:
        return STATE["feeds"][key]
    out = []
    try:
        root = ET.fromstring(request(url, timeout=30))
    except Exception as ex:
        print("google news feed failed", label, str(ex)[:100])
        STATE["feeds"][key] = out
        return out
    for it in root.iter("item"):
        t, lk, d = child(it, "title"), child(it, "link"), child(it, "description")
        src = child(it, "source")
        title = (t.text or "").strip() if t is not None else ""
        link = (lk.text or "").strip() if lk is not None else ""
        pub = (src.text or "").strip() if src is not None else label
        purl = (src.get("url") or "") if src is not None else ""
        if not (title and link):
            continue
        if not allow_moroccan and (build_site.is_moroccan(purl, pub) or build_site.is_moroccan(link, pub)):
            continue
        desc = re.sub(r"<[^>]+>", " ", (d.text or "") if d is not None else "")
        out.append({"publisher": pub, "title": title, "url": link, "desc": re.sub(r"\s+", " ", desc).strip()})
    print(f"google news ok: {label} ({len(out)})" if out else f"google news empty: {label}")
    STATE["feeds"][key] = out
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


def pick_city_story(used, arts):
    """Next Moroccan city + a real crime/security story about it.
    Discovery: national RSS (full text, attributed) then Google News; never invents a story.
    Returns ((name, slug, region), sources, key) or None."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    ordered = []
    for name, slug, region in cities.CITIES:
        ordered.append((name, slug, region))
    have = {}
    for a in arts.get("ar_cities", []):
        have[a.get("city")] = have.get(a.get("city"), 0) + 1
    ordered.sort(key=lambda c: (have.get(c[0], 0), cities.CITIES.index(c)))
    for name, slug, region in ordered[:8]:
        key = f"city:{name}:{day}"
        if key in used:
            continue
        pool = []
        for pub, url in cities.NATIONAL_FEEDS:
            for it in read_feed(pub, url, allow_moroccan=True):
                if it["url"] in used:
                    continue
                text = it["title"] + " " + it["desc"]
                if cities.mentions(text, name) and cities.is_crime(text):
                    pool.append(it)
        chosen = pool[:2]
        if len(chosen) < 2:     # complete with Google News coverage of the same city
            for url in cities.city_urls(name):
                for it in read_gn("Google News", url, allow_moroccan=True):
                    if it["url"] not in used and all(it["url"] != c["url"] for c in chosen):
                        chosen.append(it)
                    if len(chosen) >= 2:
                        break
                if len(chosen) >= 2:
                    break
        if chosen:
            return (name, slug, region), chosen, key
        used.add(key)
        print("city skipped (no fresh story):", name)
    return None


def page_text(url):
    if "news.google." in url:      # Google News discovery links do not expose the article body
        return ""
    try:
        raw = request(url, timeout=30).decode("utf-8", "ignore")
    except Exception:
        return ""
    raw = re.sub(r"(?is)<(script|style|nav|footer|header|aside).*?</\1>", " ", raw)
    paras = [re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", raw)]
    return " ".join(p for p in paras if len(p) > 60)[:8000]


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


def write_article(cat_name, sources, trend=None, system=None, city=None, lo=None, hi=None):
    lo = lo or ((MIN_WORDS_TREND, MAX_WORDS_TREND) if trend else (MIN_WORDS, MAX_WORDS))[0]
    hi = hi or ((MIN_WORDS_TREND, MAX_WORDS_TREND) if trend else (MIN_WORDS, MAX_WORDS))[1]
    system = (system or SYSTEM).replace("{LO}", str(lo)).replace("{HI}", str(hi))
    material = "\n\n".join(f"[{s['publisher']}] {s['title']}\n{s['text'] or s['desc']}" for s in sources)
    user = f"القسم: {cat_name}\n"
    if city:
        user += f"المدينة المعنية: {city}\nاجعل اسم المدينة واضحاً في العنوان وفي أول فقرة.\n"
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
    return any(bin(h ^ o).count("1") <= DUP_DIST for k, o in known_hashes().items()
               if k != skip and not (skip and k.startswith(skip + "-")))


def build_prompt(prompt, art_id, cat, attempt):
    """Wrap the scene prompt into a full photographic brief: style, framing, lens, light, palette, mood and strict negatives.
    The seed depends on the article id, so two articles never receive the same framing, and regenerating is reproducible."""
    r = random.Random(f"{art_id}-{attempt}")
    lens = r.choice(["24mm wide lens", "35mm documentary lens", "50mm natural perspective", "85mm short telephoto"])
    palette = r.choice(PALETTES)
    return ("Editorial news photograph for the front page of an international newspaper, photorealistic, shot on a full-frame camera with a "
            + lens + ", " + r.choice(ANGLES) + ", " + r.choice(LIGHTS) + ", " + palette + " colour grade, natural skin texture, "
            "sharp focus on the subject, subtle film grain, high dynamic range. " + IMG_STYLE.get(cat, "") + ". "
            "Scene: " + prompt + ". "
            "MANDATORY NEGATIVES: no text, no letters, no numbers, no logos, no watermark, no signature, no brand names, no trademarks, "
            "no identifiable real people or celebrities, no posed portrait, no fashion model, no glamour or beauty shot, no graphic violence, no blood, no dead bodies, no sexual content, no religious desecration.")


def image_prompt_for_article(title, paragraphs, cat, art_id):
    """Build the image prompt FROM THE HEADLINE + THE FIRST THREE PARAGRAPHS, exactly as the editor asked.
    Falls back to the article's own English prompt, then to a category scene. Returns a clean 40-90 word English prompt."""
    first3 = [p.strip() for p in paragraphs if p.strip() and not p.strip().startswith("## ")][:3]
    material = f"HEADLINE: {title}\n\nFIRST THREE PARAGRAPHS:\n" + "\n".join(f"- {p}" for p in first3)
    try:
        res = parse_json(generate_text(PROMPT_SYSTEM, material))
        p = re.sub(r"\s+", " ", str(res.get("image_prompt", ""))).strip().strip('"')
        if 25 <= len(p.split()) <= 130:
            print("image prompt built from title + first 3 paragraphs")
            return p
    except Exception as ex:
        print("image prompt from title failed:", str(ex)[:120])
    return ""


def sharpness(img):
    """Edge-detail score used to reject blurry or upscaled images."""
    try:
        from PIL import ImageFilter, ImageStat
        g = img.convert("L")
        g.thumbnail((640, 640))
        return ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]
    except Exception:
        return 999


SHARP_MIN = 30          # below this the picture is nearly blank / heavily upscaled -> regenerate (dark night shots stay above it)
MIN_W, MIN_H = 900, 500


def image_ok(img):
    if img.width < MIN_W or img.height < MIN_H:
        print(f"image too small ({img.width}x{img.height}) -> regenerating")
        return False
    s = sharpness(img)
    if s < SHARP_MIN:
        print(f"image looks blurry (sharpness {s:.0f}) -> regenerating")
        return False
    return True


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


def image_openai(prompt, seed):
    """ChatGPT images through the OpenAI API (gpt-image-1 by default). Needs OPENAI_API_KEY (paid; the organization may need verification)."""
    model = os.getenv("OPENAI_IMAGE_MODEL", "").strip() or "gpt-image-1"
    payload = {"model": model, "prompt": prompt[:3800], "size": "1536x1024", "n": 1}
    if model.startswith("gpt-image"):
        payload["quality"] = os.getenv("OPENAI_IMAGE_QUALITY", "").strip() or "medium"
    res = call_json("https://api.openai.com/v1/images/generations", payload, {"Authorization": f"Bearer {OPENAI_KEY}"}, "openai", tries=2)
    item = (res.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"]), False
    if item.get("url"):
        return request(item["url"], timeout=120), False
    raise ApiError(0, "no image in the OpenAI response", "openai")


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
    """Returns (relative image path, credit dict or None). A credit ({"source": "picsum"}) exists only for stock photographs."""
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
            if prov in STATE["dead_image"] or (prov in ("gemini", "genai") and not GEMINI_KEY) or (prov == "openai" and not OPENAI_KEY):
                continue
            chosen, chosen_h = None, None
            for attempt in range(4):  # new seed + new angle/light each time until the picture is not a look-alike
                seed = int(hashlib.md5(f"{art_id}-{attempt}".encode()).hexdigest()[:6], 16)
                full = build_prompt(prompt, art_id, cat, attempt)
                try:
                    if prov == "gemini":
                        raw, crop = image_gemini(full)
                    elif prov == "genai":
                        raw, crop = image_genai(full, seed)
                    elif prov == "openai":
                        raw, crop = image_openai(full, seed)
                    else:
                        raise ApiError(0, f"unknown image provider: {prov}", prov)
                    img = Image.open(io.BytesIO(raw)).convert("RGB")
                except Exception as ex:
                    print(f"image provider '{prov}' failed:", str(ex)[:160])
                    if prov in ("genai", "openai") and re.search(r"limit: 0|free.?tier|not.?found|permission|forbidden|api key|cannot find|ERR_MODULE|billing|insufficient_quota|invalid_api_key|must be verified|HTTP 40[13]", str(ex), re.I):
                        print(f"{prov} cannot be used with this key/setup -> skipping it for this run, using the next provider")
                        STATE["dead_image"].add(prov)
                    elif prov in ("pollinations", "genai", "openai", "picsum"):
                        STATE["poll_fail"] += 1
                        if STATE["poll_fail"] >= 3:
                            STATE["dead_image"].add(prov)
                    else:
                        STATE["dead_image"].add(prov)
                    break
                if prov in ("pollinations", "genai", "openai", "picsum"):
                    STATE["poll_fail"] = 0
                if crop:  # anonymous Pollinations images carry a logo strip at the bottom
                    img = img.crop((0, 0, img.width, int(img.height * 0.925)))
                if not image_ok(img):
                    continue
                h = dhash(img)
                if not is_duplicate(h, skip=art_id):
                    chosen, chosen_h = img, h
                    break
                print(f"image looks like an existing one, regenerating (attempt {attempt + 1})")
            if chosen is not None:
                chosen.thumbnail((1280, 1280))   # keep the full 1280px wide illustration, less compression = sharper
                path = out / f"{stem}.webp"
                chosen.save(path, "WEBP", quality=86, method=6)
                STATE["hashes"][stem] = chosen_h
                return f"images/{path.name}", ({"source": "picsum"} if prov == "picsum" else None)
    svg = out / f"{stem}.svg"
    svg.write_text(fallback_svg(stem, cat), encoding="utf-8")
    return f"images/{svg.name}", None


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
    if REGEN == "none" or not (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY or OPENAI_KEY or IMAGE_PROVIDERS):
        return
    # placeholders + old random stock photos (picsum) are healed automatically, a few per run
    todo = [(k, a) for k, v in arts.items() for a in v
            if REGEN == "all"
            or a["image"].endswith(".svg")
            or (a.get("image_credit") or {}).get("source") == "picsum"]
    limit = len(todo) if REGEN in ("all", "svgall") else 8
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M")
    for k, a in todo[:limit]:
        old = a["image"]
        prompt = "" if REGEN == "all" else (a.get("image_prompt_editor") or "")
        if not prompt:   # build it from the headline + the first three paragraphs (the editor's rule)
            paras = [p for p in a.get("content", "").split("\n\n") if p.strip() and not p.strip().startswith("## ")]
            prompt = (image_prompt_for_article(a["title"], paras, k, a["id"])
                      or a.get("image_prompt") or a["title"])
            a["image_prompt_editor"] = prompt
            a["image_prompt"] = prompt
        new, credit = make_image(prompt, a["id"], k, file_stem=f"{a['id']}-{stamp}")
        if new.endswith(".svg"):
            (ROOT / new).unlink(missing_ok=True)
            continue
        a["image"], a["regen"] = new, True
        if credit:
            a["image_credit"] = credit
        else:
            a.pop("image_credit", None)
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
    heads = [a["title"] for k in ("ar_world", "ar_cities", "ar_economy", "ar_tech", "ar_sports", "ar_arts", "ar_local")
             for a in arts.get(k, [])[:2]]
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

    # remove duplicated stories and put every article in its right section (once per article)
    removed, moved = curate.run(arts, build_site.CATEGORIES, llm=generate_text if (GEMINI_KEY or GROQ_KEY or OPENROUTER_KEY) else None)
    for a in removed:
        (ROOT / a["image"]).unlink(missing_ok=True)
        print("duplicate article removed:", a["title"][:70])
    print(f"archive cleaned: {len(removed)} duplicates removed, {moved} articles moved to their right section")

    # guard: Moroccan outlets may only be cited in «أخبار المدن»; any other article citing one is dropped here
    dropped = 0
    for k in list(arts):
        if k in build_site.MOROCCAN_OK_CATS:
            continue
        keep = []
        for a in arts[k]:
            if any(build_site.is_moroccan(s.get("url", ""), s.get("publisher", "")) for s in a.get("sources", [])):
                (ROOT / a["image"]).unlink(missing_ok=True)
                dropped += 1
                print("article removed (Moroccan source outside city news):", a["id"])
            else:
                keep.append(a)
        arts[k] = keep
    if dropped:
        print(f"archive cleaned: {dropped} articles citing a Moroccan outlet removed")

    heal_images(arts)

    made, stuck, errors = 0, set(), []
    while made < MAX_PER_RUN and len(stuck) < len(arts) and len(errors) < 2:
        # neediest category first; once all have >= MIN_PER_CAT, rotate to the one with the oldest latest article
        cat = min((k for k in arts if k not in stuck),
                  key=lambda k: (len(arts[k]) >= MIN_PER_CAT, len(arts[k]), arts[k][0]["date"] if arts[k] else ""))
        trend, tkey, city_meta, system = None, None, None, None
        if cat == "ar_local":
            pick = pick_trend(used)
            if not pick:
                print("no usable Moroccan trend right now")
                stuck.add(cat)
                continue
            trend, chosen, tkey = pick
        elif cat == "ar_cities":
            pick = pick_city_story(used, arts)
            if not pick:
                print("no usable city story right now")
                stuck.add(cat)
                continue
            city_meta, chosen, tkey = pick
            system = CITY_SYSTEM
        else:
            lists = [[i for i in read_feed(n, u) if i["url"] not in used] for n, u in FEEDS.get(cat, [])]
            lists += [[i for i in read_gn(n, u) if i["url"] not in used] for n, u in TOPIC_FEEDS.get(cat, [])]
            pool = interleave([x for x in lists if x])
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
            art = write_article(build_site.CATEGORIES[cat], chosen, trend, system=system,
                                city=city_meta[0] if city_meta else None)
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
        if curate.is_duplicate_of_any({"title": art["title"], "content": "\n\n".join(art["body"])}, arts):
            print("article rejected: it duplicates one that is already published:", art["title"][:70])
            continue
        aid = f"{cat}-{datetime.now(timezone.utc):%Y%m%d%H%M}-{hashlib.md5(chosen[0]['url'].encode()).hexdigest()[:6]}"
        body = [p.strip() for p in art["body"]]
        # image prompt is rebuilt from the headline + the first three paragraphs (the editor's rule)
        ip = (image_prompt_for_article(art["title"], body, cat, aid)
              or str(art.get("image_prompt", "")).strip()
              or f"a telling scene from this news story: {art['title']}")
        mi = make_image(ip, aid, cat)
        entry = {
            "id": aid, "title": art["title"].strip(), "summary": art["summary"].strip(),
            "content": "\n\n".join(body),
            "image": mi[0], "image_credit": mi[1],
            "cdn": cloudinary_upload(ROOT / mi[0], "nexus/" + Path(mi[0]).stem), "image_alt": art["title"].strip(),
            "image_prompt": ip, "image_prompt_editor": ip, "cat_ok": True,
            "date": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "sources": [{"publisher": s["publisher"], "url": s["url"]} for s in chosen]}
        if city_meta:
            entry.update({"city": city_meta[0], "city_slug": city_meta[1], "city_region": city_meta[2]})
        arts[cat].insert(0, entry)
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
