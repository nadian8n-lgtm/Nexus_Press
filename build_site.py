"""Builds the whole static site from articles.json.

Outputs: index.html, category-<key>.html, articles/<id>.html, about/contact/privacy-policy,
weather.html, search.html, search.json, feed.xml, sitemap.xml, robots.txt, manifest.webmanifest, sw.js
"""
import html
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import legal

ROOT = Path(__file__).parent
REPO = os.getenv("GITHUB_REPOSITORY", "")  # e.g. user/Nexus_Press (set automatically in Actions)
SITE_URL = os.getenv("SITE_URL") or (
    f"https://{REPO.split('/')[0]}.github.io/{REPO.split('/')[1]}" if "/" in REPO else "")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "nadia.bouizgarne1@gmail.com"
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")  # ca-pub-XXXXXXXXXXXXXXXX after approval
# Newsletter: leave empty -> subscribers are e-mailed to CONTACT_EMAIL through FormSubmit.
# Or set NEWSLETTER_BUTTONDOWN=<your buttondown username> to use Buttondown (it can e-mail feed.xml daily).
NEWSLETTER_BUTTONDOWN = os.getenv("NEWSLETTER_BUTTONDOWN", "")
# Google Apps Script web-app URL (Code.gs): comments + contact form + newsletter. Set it as GitHub variable NP_API.
NP_API = os.getenv("NP_API", "").strip()
POLL_NS = "np-" + (re.sub(r"[^a-z0-9]+", "-", REPO.lower()).strip("-") if REPO else "nexus-press")

CATEGORIES = {
    "ar_local": "أخبار المغرب",
    "ar_world": "الأخبار الدولية",
    "ar_economy": "اقتصاد",
    "ar_tech": "تكنولوجيا",
    "ar_sports": "رياضة",
    "ar_arts": "فن وثقافة",
}
# Moroccan outlets are not used as sources any more (Morocco is covered through Google Trends).
MOROCCAN_HOSTS = ("hespress", "le360", "hibapress", "alyaoum24", "medias24", "2m.ma", "snrt", "map.ma", "mapexpress",
                  "barlamane", "goud.ma", "chouftv", "yabiladi", "lakome", "akhbarona", "assahifa", "almaghribtoday",
                  "h24info", "lematin", "leconomiste", "telquel", "aujourdhui.ma", "bladi", "febrayer", "anfaspress",
                  "kech24", "moroccoworldnews", "moroccotomorrow", "hespress", "lopinion.ma", "maroc.ma", "alaoual",
                  "almassaa", "assabah", "rue20", "lesiteinfo", "challenge.ma", "ledesk", "elbotola", "arryadia",
                  "hibapress", "tanja24", "bayanealyaoume", "sahraa", "alakhbar")
e = html.escape

POLL_BANK = [
    ("ما أكثر مجال إخباري تحرص على متابعته يوميًا؟", ["السياسة", "الاقتصاد", "التكنولوجيا", "الرياضة", "الفن والثقافة"]),
    ("ما وسيلتك المفضلة لتلقي الأخبار؟", ["المواقع الإخبارية", "وسائل التواصل الاجتماعي", "التلفاز", "النشرات البريدية"]),
    ("هل تثق في الأخبار المنتشرة على وسائل التواصل الاجتماعي؟", ["نعم غالبًا", "أحيانًا فقط", "نادرًا", "لا أثق بها"]),
    ("ما رأيك في استخدام الذكاء الاصطناعي في إعداد الأخبار؟", ["أؤيده مع مراجعة بشرية", "أؤيده بالكامل", "أعارضه", "لا رأي لي"]),
    ("كم من الوقت تقضيه يوميًا في متابعة الأخبار؟", ["أقل من 15 دقيقة", "من 15 إلى 30 دقيقة", "من 30 دقيقة إلى ساعة", "أكثر من ساعة"]),
    ("ما الوقت الذي تفضّله لقراءة الأخبار؟", ["الصباح الباكر", "خلال النهار", "المساء", "قبل النوم"]),
    ("أي أسلوب تفضّل في المقالات الإخبارية؟", ["الخبر المختصر", "المقال المعمّق", "التحليل مع الخلفية", "التقارير المصوّرة"]),
    ("ما الرياضة التي تتابعها أكثر؟", ["كرة القدم", "كرة السلة", "التنس", "رياضات أخرى"]),
    ("هل تتابع أخبار الاقتصاد وأسواق المال بانتظام؟", ["نعم يوميًا", "أسبوعيًا", "نادرًا", "لا أتابعها"]),
    ("ما المحتوى الذي تودّ أن نزيد منه في نكسوس بريس؟", ["الأخبار العاجلة", "التحليلات", "التحقيقات", "الفن والثقافة"]),
    ("كيف تقيّم موقع نكسوس بريس؟", ["ممتاز", "جيد", "مقبول", "يحتاج إلى تحسين"]),
    ("ما أكثر قضية تشغل العالم اليوم برأيك؟", ["الغلاء والاقتصاد", "المناخ والبيئة", "الذكاء الاصطناعي", "الأمن والسلام"]),
    ("هل تفضّل قراءة الأخبار بالوضع الليلي؟", ["نعم دائمًا", "أحيانًا", "لا، أفضّل الوضع العادي"]),
    ("أين تقرأ الأخبار غالبًا؟", ["على الهاتف", "على الحاسوب", "على الجهاز اللوحي", "حسب الظرف"]),
]


SW_JS = """/* Nexus Press service worker: instant repeat visits + offline fallback */
const V = 'np-__VERSION__';
const CORE = ['./', 'style.css', 'site.js', 'tools.js', 'logo.webp'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(V).then(c => Promise.allSettled(CORE.map(u => c.add(u)))));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;
  if (r.mode === 'navigate') {            // pages: network first, cache when offline
    e.respondWith(fetch(r).then(res => { const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); return res; })
      .catch(() => caches.match(r).then(m => m || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(r).then(m => {   // assets & images: cache first, refresh in background
    const net = fetch(r).then(res => { if (res.ok) { const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); } return res; }).catch(() => m);
    return m || net;
  }));
});
"""


def ad(pos, extra=""):
    """Ad unit. Renders NOTHING until ADSENSE_CLIENT and a slot id are set (so the site stays clean before approval)."""
    slot = os.getenv(f"ADSENSE_SLOT_{pos.upper()}") or os.getenv("ADSENSE_SLOT", "")
    if not (ADSENSE_CLIENT and slot):
        return ""
    return (f'<div class="ad-wrap notranslate {extra}"><ins class="adsbygoogle" style="display:block" data-ad-client="{e(ADSENSE_CLIENT)}" '
            f'data-ad-slot="{e(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


def is_moroccan(url="", publisher=""):
    host = urllib.parse.urlparse(url).netloc.lower()
    name = publisher.lower()
    return host.endswith(".ma") or any(h in host or h in name.replace(" ", "") for h in MOROCCAN_HOSTS)


def load():
    p = ROOT / "articles.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    arts = data.get("articles", {})
    return {k: sorted(arts.get(k, []), key=lambda a: a["date"], reverse=True) for k in CATEGORIES}


def today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_poll():
    """Today's poll: poll.json if it is today's, else a rotating question from the built-in bank (so it always changes daily)."""
    t = today_utc()
    p = ROOT / "poll.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if d.get("id") == t and d.get("question") and 2 <= len(d.get("options", [])) <= 5:
            return {"id": t, "q": d["question"], "o": d["options"]}
    except Exception:
        pass
    q, o = POLL_BANK[datetime.now(timezone.utc).toordinal() % len(POLL_BANK)]
    return {"id": t, "q": q, "o": o}


# ----------------------------------------------------------------------------- images
def cdn(a, w, h=0):
    """Cloudinary delivery url (auto format/quality, resized) when the article image was uploaded, else ''."""
    u = a.get("cdn", "")
    if "/upload/" not in u:
        return ""
    t = f"f_auto,q_auto,w_{w},c_limit" if not h else f"f_auto,q_auto,w_{w},h_{h},c_fill"
    return u.replace("/upload/", f"/upload/{t}/", 1)


def img_src(a, pre, w):
    """(src, onerror-fallback) : CDN first, local file as safety net."""
    local = pre + (thumb(a["image"]) if w <= 600 else a["image"])
    c = cdn(a, w)
    return (c, f' onerror="this.onerror=null;this.src=\'{e(local)}\'"') if c else (local, "")


def thumb(rel):
    """Small 480px WebP for cards (much lighter than the 1000px hero). Falls back to the original."""
    p = ROOT / rel
    if not p.exists() or p.suffix == ".svg":
        return rel
    t = ROOT / "images" / "t" / (p.stem + ".webp")
    if not t.exists():
        try:
            from PIL import Image
            t.parent.mkdir(exist_ok=True)
            im = Image.open(p).convert("RGB")
            im.thumbnail((480, 480))
            im.save(t, "WEBP", quality=70, method=6)
        except Exception:
            return rel
    return f"images/t/{t.name}"


def clean_thumbs(data):
    keep = {Path(a["image"]).stem for k in CATEGORIES for a in data[k]}
    for t in (ROOT / "images" / "t").glob("*.webp"):
        if t.stem not in keep:
            t.unlink()


# ----------------------------------------------------------------------------- layout pieces
def head(title, desc, pre, canonical="", image="", extra=""):
    ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>'
           if ADSENSE_CLIENT else "")
    og = f'<meta property="og:image" content="{e(image)}"><meta name="twitter:image" content="{e(image)}">' if image else ""
    can = f'<link rel="canonical" href="{e(canonical)}">' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website"><meta property="og:site_name" content="نكسوس بريس"><meta name="twitter:card" content="summary_large_image">{og}{can}
<script>try{{var t=localStorage.getItem('np-theme');if(t)document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap"></noscript>
<meta name="theme-color" content="#0b3c7a">
<link rel="manifest" href="{pre}manifest.webmanifest"><link rel="icon" type="image/png" href="{pre}icon-192.png"><link rel="apple-touch-icon" href="{pre}icon-192.png">
<link rel="alternate" type="application/rss+xml" title="نكسوس بريس" href="{pre}feed.xml">
<link rel="stylesheet" href="{pre}style.css">
{extra}{ads}
</head>"""


def HAS_DEALS():
    """The Amazon deals pages are linked only when deals/index.html exists (created by amazon_products.js)."""
    return (ROOT / "deals" / "index.html").exists()


def header(pre, data, active):
    ticker = "  •  ".join(a["title"] for k in CATEGORIES for a in data[k][:2]) or "نكسوس بريس — أخبار العالم على مدار الساعة"
    items = ([("index.html", "الرئيسية", "home")] + [(f"category-{k}.html", v, k) for k, v in CATEGORIES.items()]
             + [("weather.html", "🌦️ الطقس والصلاة", "weather")]
             + ([("deals/index.html", "🛒 عروض أمازون", "deals")] if HAS_DEALS() else []))
    nav = "".join(f'<li><a href="{pre}{u}"{" class=active" if active == key else ""}>{e(n)}</a></li>' for u, n, key in items)
    return f"""<body data-pre="{pre}" data-api="{e(NP_API)}">
<div class="progress" id="progress"></div>
<div class="top-bar notranslate"><div class="container flex">
<span class="today"><span class="live">●</span> <span id="today">تحديث مستمر على مدار الساعة</span></span>
<div class="top-tools"><button class="icon-btn" id="theme-btn" type="button" aria-label="الوضع الليلي" title="الوضع الليلي">🌓</button>
<div class="lang-box" translate="no"><span>🌐</span>
<button class="lang-btn" data-l="ar">العربية</button>|<button class="lang-btn" data-l="fr">Français</button>|<button class="lang-btn" data-l="en">English</button></div></div>
</div></div>
<header class="main-header"><div class="container flex">
<a href="{pre}index.html" class="notranslate logo"><img src="{pre}logo.webp" width="165" height="90" alt="Nexus Press"></a>
<div class="header-tag">أخبار العالم لحظة بلحظة</div>
<form class="hsearch" action="{pre}search.html" role="search"><input name="q" type="search" placeholder="ابحث في نكسوس بريس…" aria-label="بحث"><button type="submit" aria-label="بحث">🔍</button></form></div></header>
<nav class="main-nav"><div class="container"><ul class="nav-menu">{nav}</ul></div></nav>
<div class="breaking"><b>عاجل</b><div><span class="ticker">{e(ticker)}</span></div></div>"""


def footer(pre):
    return f"""<footer class="footer"><div class="container footer-grid">
<div><h4>نكسوس بريس | Nexus Press</h4><p>جريدة إلكترونية تتابع أبرز أحداث العالم في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة.</p></div>
<div><h4>الأقسام</h4><ul>{"".join(f'<li><a href="{pre}category-{k}.html">{e(v)}</a></li>' for k, v in CATEGORIES.items())}</ul></div>
<div><h4>معلومات</h4><ul><li><a href="{pre}weather.html">الطقس ومواقيت الصلاة</a></li>{f'<li><a href="{pre}deals/index.html">عروض أمازون</a></li>' if HAS_DEALS() else ''}<li><a href="{pre}about.html">من نحن</a></li><li><a href="{pre}contact.html">اتصل بنا</a></li><li><a href="{pre}privacy-policy.html">سياسة الخصوصية</a></li><li><a href="{pre}feed.xml">RSS</a></li></ul></div>
</div><div class="footer-bottom">© {datetime.now().year} نكسوس بريس. جميع الحقوق محفوظة.</div></footer>
<button class="to-top" id="to-top" type="button" aria-label="أعلى الصفحة">↑</button>
<div id="google_translate_element" style="display:none"></div>
<script src="{pre}site.js" defer></script>
</body></html>"""


def card(a, pre, cat, eager=False):
    src, fb = img_src(a, pre, 480)
    return (f'<a class="card" href="{pre}articles/{a["id"]}.html"><img loading="{"eager" if eager else "lazy"}" decoding="async" width="480" height="270" '
            f'src="{e(src)}"{fb} alt="{e(a.get("image_alt", a["title"]))}">'
            f'<div class="info"><span class="badge">{e(CATEGORIES[cat])}</span><h3>{e(a["title"])}</h3><p>{e(a["date"][:10])}</p></div></a>')


def newsletter(kind="box"):
    if NEWSLETTER_BUTTONDOWN:
        prov, target = "buttondown", NEWSLETTER_BUTTONDOWN
    else:
        prov, target = "formsubmit", CONTACT_EMAIL
    form = (f'<form class="nl-form" data-provider="{prov}" data-target="{e(target)}" novalidate>'
            '<input type="email" name="email" placeholder="بريدك الإلكتروني" required autocomplete="email" aria-label="البريد الإلكتروني">'
            '<input type="text" name="_honey" tabindex="-1" autocomplete="off" style="display:none">'
            '<button class="btn" type="submit">اشترك الآن</button></form><p class="form-msg nl-msg" role="status"></p>')
    txt = "اشترك الآن في النشرة البريدية لجريدة نكسوس بريس، لتصلك آخر الأخبار يوميًا"
    if kind == "band":
        return f'<section class="nl-band"><div><h3>📬 النشرة البريدية</h3><p>{txt}.</p></div>{form}</section>'
    return f'<div class="widget nl-box"><h4>📬 النشرة البريدية</h4><p>{txt}.</p>{form}</div>'


def wx_mini():
    return ('<div class="widget wx-mini notranslate" aria-live="polite"><h4>🌦️ الطقس ومواقيت الصلاة</h4>'
            '<div class="wx-mini-out"><p class="muted">اكتب اسم مدينتك لتظهر لك حالة الطقس ومواقيت الصلاة.</p></div>'
            '<div class="wx-box"><input class="wx-mini-q" type="search" placeholder="اكتب اسم المدينة…" autocomplete="off" aria-label="المدينة">'
            '<button class="wx-geo" type="button" title="استخدم موقعي" aria-label="موقعي">📍</button><ul class="wx-sug"></ul></div></div>')


def poll_widget(poll):
    payload = e(json.dumps(poll, ensure_ascii=False), quote=True)
    return (f'<div class="widget poll" data-poll="{payload}" data-ns="{e(POLL_NS)}"><h4>📊 استطلاع اليوم</h4>'
            f'<div class="poll-body"><p class="poll-q">{e(poll["q"])}</p></div></div>')


def sidebar(pre, data, poll):
    latest = sorted((a for k in CATEGORIES for a in data[k]), key=lambda a: a["date"], reverse=True)[:8]
    lis = "".join(f'<li><span class="rank">{i}</span><a href="{pre}articles/{a["id"]}.html">{e(a["title"])}</a></li>' for i, a in enumerate(latest, 1))
    return (f'<aside>{ad("side1")}{wx_mini()}{poll_widget(poll)}{newsletter()}'
            f'<div class="widget"><h4>🔥 عناوين الساعة</h4><ul>{lis or "<li>قريباً</li>"}</ul></div>'
            f'{ad("side2", "sticky")}</aside>')


def render_body(content):
    out, n = [], 0
    for block in re.split(r"\n\s*\n", content.strip()):
        block = block.strip()
        if block.startswith("## "):
            out.append(f"<h2>{e(block[3:].strip())}</h2>")
        elif block:
            out.append(f"<p>{e(block)}</p>")
            n += 1
            if n in (3, 7, 11):
                out.append(ad("inline"))
    return "\n\n".join(out)


COMMENT_RULES = """<div class="c-rules" role="note"><b>⚠️ شروط النشر في التعليقات</b>
<p>من شروط النشر بالتعليقات: عدم الإساءة للكاتب أو للأشخاص أو للمقدسات أو مهاجمة الأديان أو الذات الإلهية، والابتعاد عن التحريض العنصري والشتائم.</p>
<p>الآراء الواردة في التعليقات تعبر عن آراء أصحابها وليس عن رأي <span dir="ltr">Nexus Press</span>.</p></div>"""


def comments_block(aid):
    return f"""<section class="comments" id="comments" data-article="{e(aid)}"><h3>💬 التعليقات <span class="cm-count" id="cm-count"></span></h3>{COMMENT_RULES}
<form class="cm-form notranslate" novalidate>
<div class="cm-row"><input name="name" maxlength="40" placeholder="الاسم (يظهر مع تعليقك) *" required autocomplete="nickname">
<input name="email" type="email" maxlength="80" placeholder="البريد الإلكتروني (اختياري، لا يُنشر)" autocomplete="email"></div>
<textarea name="text" rows="4" maxlength="1000" placeholder="اكتب تعليقك هنا…" required></textarea>
<input type="text" name="hp" tabindex="-1" autocomplete="off" style="display:none">
<label class="cm-agree"><input type="checkbox" name="agree"> أوافق على شروط النشر أعلاه</label>
<div class="cm-foot"><span class="cm-left" id="cm-left">1000</span><button class="btn" type="submit">أضف تعليقك</button></div>
<p class="form-msg" id="cm-msg" role="status"></p></form>
<div class="cm-list" id="cm-list"><p class="muted">جارٍ تحميل التعليقات…</p></div></section>"""


def share_bar():
    return ('<div class="share notranslate"><span>شارك المقال:</span>'
            '<button type="button" data-net="whatsapp" class="s-wa">واتساب</button>'
            '<button type="button" data-net="facebook" class="s-fb">فيسبوك</button>'
            '<button type="button" data-net="x" class="s-x">X</button>'
            '<button type="button" data-net="telegram" class="s-tg">تيليغرام</button>'
            '<button type="button" data-net="copy" class="s-cp">نسخ الرابط</button></div>')


def reading_time(text):
    return max(1, round(len(re.findall(r"\S+", text)) / 190))


def shell(title, desc, pre, canonical, data, active, inner, poll, extra_head="", image=""):
    return (head(title, desc, pre, canonical, image, extra_head) + header(pre, data, active)
            + f'<div class="container">{ad("top")}{inner}{ad("bottom")}</div>' + footer(pre))


# ----------------------------------------------------------------------------- build
def build():
    data = load()
    poll = load_poll()
    base = SITE_URL
    (ROOT / "articles").mkdir(exist_ok=True)
    for old in (ROOT / "articles").glob("*.html"):
        old.unlink()
    urls = (["index.html"] + [f"category-{k}.html" for k in CATEGORIES]
            + ["weather.html", "search.html", "about.html", "contact.html", "privacy-policy.html"])
    allart = sorted(((k, a) for k in CATEGORIES for a in data[k]), key=lambda t: t[1]["date"], reverse=True)
    for k, a in allart:  # never show Moroccan outlets as a source
        a["sources"] = [s for s in a.get("sources", []) if not is_moroccan(s.get("url", ""), s.get("publisher", ""))]
    clean_thumbs(data)

    # ---- home
    top = allart[:5]
    if top:
        slides = ""
        for i, (k, a) in enumerate(top):
            active = " active" if i == 0 else ""
            img_attr = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
            slides += (f'<a class="slide{active}" href="articles/{a["id"]}.html">'
                       f'<img src="{e(img_src(a, "", 1000)[0])}"{img_src(a, "", 1000)[1]} width="1000" height="520" alt="{e(a.get("image_alt", a["title"]))}"{img_attr}>'
                       f'<div class="cap"><span class="hot">🔥 رائج</span><span class="badge">{e(CATEGORIES[k])}</span><h2>{e(a["title"])}</h2></div></a>')
        dots = "".join(f'<span class="dot{" on" if i == 0 else ""}"></span>' for i in range(len(top)))
        hero = f'<div class="slider">{slides}<button class="nav" id="sl-prev" aria-label="السابق">›</button><button class="nav" id="sl-next" aria-label="التالي">‹</button><div class="dots">{dots}</div></div>'
    else:
        hero = '<div class="slider"><div class="hero-fallback">جاري تجهيز أحدث الأخبار…</div></div>'
    sections, shown = "", 0
    for k, name in CATEGORIES.items():
        if not data[k]:
            continue
        cards_html = "".join(card(a, "", k) for a in data[k][:6])
        more_link = f'<p class="more"><a class="badge" href="category-{k}.html">كل مقالات {e(name)} ←</a></p>'
        sections += f'<section class="sect"><h2 class="block-title">{e(name)}</h2><div class="grid">{cards_html}</div>{more_link}</section>'
        shown += 1
        if shown == 2:
            sections += newsletter("band")
        if shown % 2 == 0:
            sections += ad("middle")
    if not sections:
        sections = '<div class="empty">لا توجد مقالات منشورة بعد.</div>'
    inner = f'{hero}{ad("under_slider")}<div class="layout"><main>{sections}</main>{sidebar("", data, poll)}</div>'
    (ROOT / "index.html").write_text(shell(
        "نكسوس بريس | Nexus Press - أخبار العالم على مدار الساعة",
        "جريدة نكسوس بريس: تغطية موسعة وتحليلات لأبرز الأخبار العالمية والعربية في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة.",
        "", base + "/" if base else "", data, "home", inner, poll), encoding="utf-8")

    # ---- categories + articles
    for k, name in CATEGORIES.items():
        cards = "".join(card(a, "", k) for a in data[k]) or '<div class="empty">لا توجد مقالات في هذا القسم بعد.</div>'
        inner = (f'<div class="layout"><main><h1 class="block-title">{e(name)}</h1><div class="grid">{cards}</div>{ad("middle")}</main>'
                 f'{sidebar("", data, poll)}</div>')
        (ROOT / f"category-{k}.html").write_text(shell(f"{name} | نكسوس بريس", f"آخر مقالات قسم {name} في جريدة نكسوس بريس.", "",
                                                      f"{base}/category-{k}.html" if base else "", data, k, inner, poll), encoding="utf-8")
        for a in data[k]:
            src = "".join(f'<li><a href="{e(s["url"])}" rel="nofollow noopener" target="_blank">{e(s.get("publisher", s["url"]))}</a></li>' for s in a["sources"])
            src_html = f'<div class="sources"><b>المصادر والمراجع:</b><ul>{src}</ul></div>' if src else ""
            related = "".join(card(r, "../", k) for r in [x for x in data[k] if x["id"] != a["id"]][:3])
            url = f"{base}/articles/{a['id']}.html" if base else ""
            img_abs = cdn(a, 1200) or (f"{base}/{a['image']}" if base else a["image"])
            ld = json.dumps({"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "datePublished": a["date"],
                             "image": [img_abs], "publisher": {"@type": "Organization", "name": "نكسوس بريس"},
                             "author": {"@type": "Organization", "name": "هيئة تحرير نكسوس بريس"}}, ensure_ascii=False)
            rt = reading_time(a["content"])
            inner = f"""<div class="layout"><main><article class="article">
<nav class="crumbs" aria-label="مسار التصفح"><a href="../index.html">الرئيسية</a> › <a href="../category-{k}.html">{e(name)}</a></nav>
<span class="badge">{e(name)}</span><h1>{e(a["title"])}</h1>
<div class="meta">هيئة تحرير نكسوس بريس · {e(a["date"][:10])} · ⏱ {rt} د للقراءة</div>
{share_bar()}
{ad("article_top")}
<img class="hero" width="1000" height="520" fetchpriority="high" src="{e(img_src(a, "../", 1000)[0])}"{img_src(a, "../", 1000)[1]} alt="{e(a.get("image_alt", a["title"]))}">
<div class="article-body">

{render_body(a["content"])}

</div>{ad("article_bottom")}{share_bar()}{src_html}{newsletter("band")}{comments_block(a["id"])}</article>
<section class="related"><h2 class="block-title">مقالات ذات صلة</h2><div class="grid">{related}</div></section></main>{sidebar("../", data, poll)}</div>"""
            (ROOT / "articles" / f"{a['id']}.html").write_text(shell(
                f'{a["title"]} | نكسوس بريس', a.get("summary", a["title"]), "../", url, data, k, inner, poll,
                f'<script type="application/ld+json">{ld}</script>', img_abs), encoding="utf-8")
            urls.append(f"articles/{a['id']}.html")

    # ---- weather & prayer page, search page
    wx = """<div class="page wx-page notranslate"><h1>🌦️ الطقس ومواقيت الصلاة</h1>
<p class="lead">اكتب اسم أي مدينة في العالم لتظهر لك حالة الطقس وتوقعات الأيام القادمة ومواقيت الصلاة بتوقيت المدينة نفسها.</p>
<div id="wx-app"><div class="wx-box"><input id="wx-q" type="search" placeholder="مثال: الرباط، مكة المكرمة، باريس، New York" autocomplete="off" aria-label="المدينة">
<button class="wx-geo" id="wx-geo" type="button" title="استخدم موقعي">📍 موقعي</button><ul class="wx-sug" id="wx-sug"></ul></div>
<div class="wx-chips" id="wx-chips"></div><div id="wx-out" aria-live="polite"></div></div></div>"""
    (ROOT / "weather.html").write_text(shell(
        "الطقس ومواقيت الصلاة حول العالم | نكسوس بريس", "حالة الطقس وتوقعات الأيام ومواقيت الصلاة لأي مدينة في العالم.",
        "", f"{base}/weather.html" if base else "", data, "weather",
        f'<div class="layout"><main>{wx}</main>{sidebar("", data, poll).replace(wx_mini(), "")}</div>', poll), encoding="utf-8")
    sr = ('<div class="page"><h1>🔍 البحث</h1><form class="search-big" action="search.html"><input id="sq" name="q" type="search" '
          'placeholder="ابحث عن خبر أو موضوع…" autofocus aria-label="بحث"><button class="btn" type="submit">بحث</button></form>'
          '<div id="search-app"><div id="search-out" class="grid"></div></div></div>')
    (ROOT / "search.html").write_text(shell(
        "البحث | نكسوس بريس", "ابحث في أخبار نكسوس بريس.", "", f"{base}/search.html" if base else "", data, "",
        f'<div class="layout"><main>{sr}</main>{sidebar("", data, poll)}</div>', poll,
        '<meta name="robots" content="noindex,follow">'), encoding="utf-8")
    index = [{"i": a["id"], "t": a["title"], "s": a.get("summary", ""), "c": CATEGORIES[k], "d": a["date"][:10], "m": cdn(a, 480) or thumb(a["image"])}
             for k, a in allart]
    (ROOT / "search.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- legal pages
    today = datetime.now().strftime("%Y-%m-%d")
    for fname, (title, body, cls) in legal.pages(CONTACT_EMAIL, today, CATEGORIES, newsletter("band")).items():
        page = shell(f"{title} | نكسوس بريس", f"{title} - نكسوس بريس", "", f"{base}/{fname}" if base else "", data, "",
                     f'<div class="page {cls}"><h1>{title}</h1>{body}</div>', poll)
        (ROOT / fname).write_text(page, encoding="utf-8")

    # ---- feed, sitemap, robots, PWA files
    def absu(rel):
        return f"{base}/{rel}" if base else rel
    items = "".join(
        f"<item><title>{e(a['title'])}</title><link>{e(absu('articles/' + a['id'] + '.html'))}</link><guid isPermaLink=\"false\">{e(a['id'])}</guid>"
        f"<pubDate>{datetime.fromisoformat(a['date']).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><category>{e(CATEGORIES[k])}</category>"
        f"<description>{e(a.get('summary', ''))}</description></item>" for k, a in allart[:30])
    (ROOT / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>نكسوس بريس</title>'
        f'<link>{e(base or "/")}</link><description>أخبار العالم على مدار الساعة</description><language>ar</language>{items}</channel></rss>', encoding="utf-8")
    (ROOT / "manifest.webmanifest").write_text(json.dumps({
        "name": "نكسوس بريس", "short_name": "نكسوس", "lang": "ar", "dir": "rtl", "start_url": "./", "scope": "./",
        "display": "standalone", "background_color": "#f5f8fb", "theme_color": "#0b3c7a",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]},
        ensure_ascii=False), encoding="utf-8")
    ver = (allart[0][1]["date"] if allart else "0").replace(":", "").replace("-", "")[:12] + str(len(allart))
    (ROOT / "sw.js").write_text(SW_JS.replace("__VERSION__", ver), encoding="utf-8")
    if base:
        (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
        sm = "".join(f"<url><loc>{base}/{u}</loc></url>" for u in urls if u != "search.html")
        (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    print(f"site built: {sum(len(v) for v in data.values())} articles")


if __name__ == "__main__":
    build()
