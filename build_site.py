"""Builds the whole static site from articles.json.

Outputs: index.html, category-<key>.html, articles/<id>.html,
about.html, contact.html, privacy-policy.html, sitemap.xml
"""
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
REPO = os.getenv("GITHUB_REPOSITORY", "")  # e.g. user/Nexus_Press (set automatically in Actions)
SITE_URL = os.getenv("SITE_URL") or (
    f"https://{REPO.split('/')[0]}.github.io/{REPO.split('/')[1]}" if "/" in REPO else "")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "contact@nexuspress.example")
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")  # ca-pub-XXXXXXXXXXXXXXXX after approval

CATEGORIES = {
    "ar_local": "أخبار وطنية",
    "ar_world": "الأخبار الدولية",
    "ar_economy": "اقتصاد",
    "ar_tech": "تكنولوجيا",
    "ar_sports": "رياضة",
    "ar_arts": "فن وثقافة",
}
e = html.escape


def ad(pos, extra=""):
    """Ad unit. Real AdSense unit when ADSENSE_CLIENT (+ slot) is set, otherwise a visible placeholder."""
    slot = os.getenv(f"ADSENSE_SLOT_{pos.upper()}") or os.getenv("ADSENSE_SLOT", "")
    if ADSENSE_CLIENT:
        if not slot:
            return ""
        return (f'<div class="ad-wrap notranslate {extra}"><ins class="adsbygoogle" style="display:block" data-ad-client="{e(ADSENSE_CLIENT)}" '
                f'data-ad-slot="{e(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
                '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')
    return f'<div class="ad-wrap ad-ph {extra}"><span>مساحة إعلانية</span></div>'


def load():
    p = ROOT / "articles.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    arts = data.get("articles", {})
    return {k: sorted(arts.get(k, []), key=lambda a: a["date"], reverse=True) for k in CATEGORIES}


def head(title, desc, pre, canonical="", image=""):
    ads = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>'
           if ADSENSE_CLIENT else "")
    og = f'<meta property="og:image" content="{e(image)}">' if image else ""
    can = f'<link rel="canonical" href="{e(canonical)}">' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website">{og}{can}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{pre}style.css">
{ads}
</head>"""


def header(pre, data, active):
    ticker = "  •  ".join(a["title"] for k in CATEGORIES for a in data[k][:2]) or "نكسوس بريس — أخبار العالم على مدار الساعة"
    items = [("index.html", "الرئيسية", "home")] + [(f"category-{k}.html", v, k) for k, v in CATEGORIES.items()]
    nav = "".join(f'<li><a href="{pre}{u}"{" class=active" if active == key else ""}>{e(n)}</a></li>' for u, n, key in items)
    return f"""<body>
<div class="top-bar notranslate"><div class="container flex">
<span>🔴 تحديث مستمر على مدار الساعة</span>
<div class="lang-box" translate="no"><span>🌐</span>
<button class="lang-btn" data-l="ar">العربية</button>|<button class="lang-btn" data-l="fr">Français</button>|<button class="lang-btn" data-l="en">English</button></div>
</div></div>
<header class="main-header"><div class="container flex">
<a href="{pre}index.html" class="notranslate"><img src="{pre}image_MUwSAA.png" alt="Nexus Press"></a>
<div class="header-tag">أخبار العالم لحظة بلحظة</div></div></header>
<nav class="main-nav"><div class="container"><ul class="nav-menu">{nav}</ul></div></nav>
<div class="breaking"><b>عاجل</b><div><span class="ticker">{e(ticker)}</span></div></div>"""


def footer(pre):
    return f"""<footer class="footer"><div class="container footer-grid">
<div><h4>نكسوس بريس | Nexus Press</h4><p>جريدة إلكترونية تتابع أبرز أحداث العالم في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة.</p></div>
<div><h4>الأقسام</h4><ul>{"".join(f'<li><a href="{pre}category-{k}.html">{e(v)}</a></li>' for k, v in CATEGORIES.items())}</ul></div>
<div><h4>معلومات</h4><ul><li><a href="{pre}about.html">من نحن</a></li><li><a href="{pre}contact.html">اتصل بنا</a></li><li><a href="{pre}privacy-policy.html">سياسة الخصوصية</a></li></ul></div>
</div><div class="footer-bottom">© {datetime.now().year} نكسوس بريس. جميع الحقوق محفوظة.</div></footer>
<div id="google_translate_element" style="display:none"></div>
<script src="{pre}site.js"></script>
<script src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
</body></html>"""


def card(a, pre, cat):
    return (f'<a class="card" href="{pre}articles/{a["id"]}.html"><img loading="lazy" src="{pre}{e(a["image"])}" alt="{e(a.get("image_alt", a["title"]))}">'
            f'<div class="info"><span class="badge">{e(CATEGORIES[cat])}</span><h3>{e(a["title"])}</h3><p>{e(a["date"][:10])}</p></div></a>')


def sidebar(pre, data):
    latest = sorted((a for k in CATEGORIES for a in data[k]), key=lambda a: a["date"], reverse=True)[:8]
    lis = "".join(f'<li><span class="rank">{i}</span><a href="{pre}articles/{a["id"]}.html">{e(a["title"])}</a></li>' for i, a in enumerate(latest, 1))
    return (f'<aside>{ad("side1")}<div class="widget"><h4>🔥 عناوين الساعة</h4><ul>{lis or "<li>قريباً</li>"}</ul></div>'
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


def comments_block():
    if not REPO:
        return '<div class="comments"><h3>💬 التعليقات</h3><p>سيظهر مربع التعليقات بعد رفع الموقع على GitHub.</p></div>'
    return f"""<div class="comments notranslate"><h3>💬 شاركنا رأيك</h3>
<script src="https://utteranc.es/client.js" repo="{e(REPO)}" issue-term="pathname" label="comment" theme="github-light" crossorigin="anonymous" async></script></div>"""


def build():
    data = load()
    base = SITE_URL
    urls = ["index.html"] + [f"category-{k}.html" for k in CATEGORIES] + ["about.html", "contact.html", "privacy-policy.html"]
    (ROOT / "articles").mkdir(exist_ok=True)
    for old in (ROOT / "articles").glob("*.html"):
        old.unlink()

    # home
    allart = sorted(((k, a) for k in CATEGORIES for a in data[k]), key=lambda t: t[1]["date"], reverse=True)
    top = allart[:5]
    if top:
        slides = "".join(
            f'<a class="slide{" active" if i == 0 else ""}" href="articles/{a["id"]}.html"><img src="{e(a["image"])}" alt="{e(a["title"])}">'
            f'<div class="cap"><span class="hot">🔥 رائج</span><span class="badge">{e(CATEGORIES[k])}</span><h2>{e(a["title"])}</h2></div></a>'
            for i, (k, a) in enumerate(top))
        dots = "".join(f'<span class="dot{" on" if i == 0 else ""}"></span>' for i in range(len(top)))
        hero = f'<div class="slider">{slides}<button class="nav" id="sl-prev" aria-label="السابق">›</button><button class="nav" id="sl-next" aria-label="التالي">‹</button><div class="dots">{dots}</div></div>'
    else:
        hero = '<div class="slider"><div class="hero-fallback">جاري تجهيز أحدث الأخبار…</div></div>'
    sections, shown = "", 0
    for k, name in CATEGORIES.items():
        if data[k]:
            sections += (f'<h2 class="block-title" style="margin-top:30px">{e(name)}</h2><div class="grid">'
                         + "".join(card(a, "", k) for a in data[k][:6]) + "</div>"
                         + f'<p style="margin-top:12px"><a class="badge"
