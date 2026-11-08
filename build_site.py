"""Builds the whole static site from articles.json.

Outputs: index.html, category-<key>.html, articles/<id>.html,
about.html, contact.html, privacy-policy.html, sitemap.xml, robots.txt
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
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "nadia.bouizgarne1@gmail.com"
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
    """Ad unit. Renders NOTHING until ADSENSE_CLIENT and a slot id are set (so the site stays clean before approval)."""
    slot = os.getenv(f"ADSENSE_SLOT_{pos.upper()}") or os.getenv("ADSENSE_SLOT", "")
    if not (ADSENSE_CLIENT and slot):
        return ""
    return (f'<div class="ad-wrap notranslate {extra}"><ins class="adsbygoogle" style="display:block" data-ad-client="{e(ADSENSE_CLIENT)}" '
            f'data-ad-slot="{e(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


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
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap"></noscript>
<meta name="theme-color" content="#0b3c7a">
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
<script src="{pre}site.js" defer></script>
</body></html>"""


def card(a, pre, cat):
    return (f'<a class="card" href="{pre}articles/{a["id"]}.html"><img loading="lazy" decoding="async" src="{pre}{e(a["image"])}" alt="{e(a.get("image_alt", a["title"]))}">'
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
    return f'<div class="comments notranslate" data-repo="{e(REPO)}"><h3>💬 شاركنا رأيك</h3></div>'


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
        slides = ""
        for i, (k, a) in enumerate(top):
            active = " active" if i == 0 else ""
            img_attr = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
            slides += (f'<a class="slide{active}" href="articles/{a["id"]}.html">'
                       f'<img src="{e(a["image"])}" alt="{e(a["title"])}"{img_attr}>'
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
        more_link = '<p style="margin-top:12px"><a class="badge" href="category-' + k + '.html">كل مقالات ' + e(name) + ' ←</a></p>'
        sections += '<h2 class="block-title" style="margin-top:30px">' + e(name) + '</h2>'
        sections += '<div class="grid">' + cards_html + '</div>' + more_link
        shown += 1
        if shown % 2 == 0:
            sections += ad("middle")
    if not sections:
        sections = '<div class="empty">لا توجد مقالات منشورة بعد.</div>'
    page = (head("نكسوس بريس | Nexus Press - أخبار العالم على مدار الساعة", "جريدة نكسوس بريس: تغطية موسعة وتحليلات لأبرز الأخبار العالمية والعربية في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة.", "", base + "/" if base else "")
            + header("", data, "home")
            + f'<div class="container">{ad("top")}{hero}{ad("under_slider")}<div class="layout"><main>{sections}</main>{sidebar("", data)}</div>{ad("bottom")}</div>'
            + footer(""))
    (ROOT / "index.html").write_text(page, encoding="utf-8")

    # categories + articles
    for k, name in CATEGORIES.items():
        cards = "".join(card(a, "", k) for a in data[k]) or '<div class="empty">لا توجد مقالات في هذا القسم بعد.</div>'
        page = (head(f"{name} | نكسوس بريس", f"آخر مقالات قسم {name} في جريدة نكسوس بريس.", "", f"{base}/category-{k}.html" if base else "")
                + header("", data, k)
                + f'<div class="container">{ad("top")}<div class="layout"><main><h1 class="block-title">{e(name)}</h1><div class="grid">{cards}</div>{ad("middle")}</main>{sidebar("", data)}</div>{ad("bottom")}</div>'
                + footer(""))
        (ROOT / f"category-{k}.html").write_text(page, encoding="utf-8")

        for a in data[k]:
            src = "".join(f'<li><a href="{e(s["url"])}" rel="nofollow noopener" target="_blank">{e(s.get("publisher", s["url"]))}</a></li>' for s in a.get("sources", []))
            src_html = f'<div class="sources"><b>المصادر والمراجع:</b><ul>{src}</ul></div>' if src else ""
            related = "".join(card(r, "../", k) for r in [x for x in data[k] if x["id"] != a["id"]][:3])
            url = f"{base}/articles/{a['id']}.html" if base else ""
            ld = json.dumps({"@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"], "datePublished": a["date"],
                             "image": [f"{base}/{a['image']}" if base else a["image"]], "publisher": {"@type": "Organization", "name": "نكسوس بريس"},
                             "author": {"@type": "Organization", "name": "هيئة تحرير نكسوس بريس"}}, ensure_ascii=False)
            page = (head(f'{a["title"]} | نكسوس بريس', a.get("summary", a["title"]), "../", url, f"{base}/{a['image']}" if base else "")
                    + f'<script type="application/ld+json">{ld}</script>'
                    + header("../", data, k)
                    + f"""<div class="container">{ad("top")}<div class="layout"><main><article class="article">
<span class="badge">{e(name)}</span><h1>{e(a["title"])}</h1>
<div class="meta">هيئة تحرير نكسوس بريس · {e(a["date"][:10])}</div>
{ad("article_top")}
<img class="hero" src="../{e(a["image"])}" alt="{e(a.get("image_alt", a["title"]))}">
<div class="article-body">

{render_body(a["content"])}

</div>{ad("article_bottom")}{src_html}{comments_block()}</article>
<section class="related"><h2 class="block-title">مقالات ذات صلة</h2><div class="grid">{related}</div></section></main>{sidebar("../", data)}</div>{ad("bottom")}</div>"""
                    + footer("../"))
            (ROOT / "articles" / f"{a['id']}.html").write_text(page, encoding="utf-8")
            urls.append(f"articles/{a['id']}.html")

    # legal pages
    cats_li = "".join(f"<li>{e(v)}</li>" for v in CATEGORIES.values())
    today = datetime.now().strftime("%Y-%m-%d")
    legal = {
        "about.html": ("من نحن", f"""<p>مرحباً بك في <b>نكسوس بريس</b>، جريدة إلكترونية عربية تُعنى بتغطية أبرز أحداث العالم على مدار الساعة، وتقديمها للقارئ بلغة واضحة وسياق كافٍ يساعده على فهم ما وراء الخبر، وليس مجرد قراءة عنوانه.</p>
<h2>رسالتنا</h2><p>أن نقدّم للقارئ العربي خبراً مفهوماً وموثوقاً، يُعرض بدقة وبصياغة أصيلة، بعيداً عن الإثارة والتضليل.</p>
<h2>ماذا نغطي؟</h2><ul>{cats_li}</ul>
<h2>كيف نعمل؟</h2><p>نتابع كبرى وكالات الأنباء والصحف والمؤسسات الإعلامية المعروفة، ونستخلص منها الوقائع المؤكدة، ثم نعيد عرضها بصياغتنا الخاصة مع إضافة الخلفية والسياق اللازمين. ونستعين بأدوات تقنية حديثة في إعداد المحتوى وتنظيمه ونشره. ونشير في أسفل كل مقال إلى المصادر التي اعتمدنا عليها، ولا ننسخ نصوص الآخرين.</p>
<h2>معاييرنا التحريرية</h2><ul>
<li><b>الدقة:</b> نعتمد على مصادر معروفة ولا ننشر معلومة لا سند لها.</li>
<li><b>الوضوح:</b> نفصل بين الخبر والتحليل، ونكتب بلغة سليمة ومباشرة.</li>
<li><b>الشفافية:</b> نذكر مصادرنا ونعلن عن أي تصحيح.</li>
<li><b>احترام الملكية الفكرية:</b> نعيد الصياغة ولا ننقل، ونستخدم صوراً توضيحية مولّدة خصيصاً للموقع.</li></ul>
<h2>التصحيحات</h2><p>إذا لاحظت خطأً في أي مقال فراسلنا عبر صفحة <a href="contact.html">اتصل بنا</a>، وسنراجع الملاحظة ونصحح الخطأ بأسرع وقت.</p>
<h2>الإعلانات والتمويل</h2><p>قد يعرض الموقع إعلانات (مثل Google AdSense) للمساعدة في تغطية تكاليف التشغيل، ولا تؤثر الإعلانات على محتوانا التحريري. راجع <a href="privacy-policy.html">سياسة الخصوصية</a> لمعرفة كيفية التعامل مع البيانات.</p>
<h2>إخلاء المسؤولية</h2><p>المحتوى المنشور مخصص للإعلام والمعرفة العامة، ولا يُعد نصيحة قانونية أو مالية أو استثمارية أو طبية. نوصي بالرجوع إلى مختص قبل اتخاذ أي قرار بناءً على ما يرد في الموقع.</p>"""),

        "contact.html": ("اتصل بنا", f"""<p>يسعدنا تواصلك معنا. للاستفسارات والاقتراحات وطلبات التصحيح والتعاون الإعلاني، راسلنا مباشرة على البريد الإلكتروني:</p>
<p style="font-size:20px"><a href="mailto:{e(CONTACT_EMAIL)}"><b dir="ltr">{e(CONTACT_EMAIL)}</b></a></p>
<h2>متى نرد؟</h2><p>نحرص على الرد خلال أيام عمل قليلة. وإذا كانت رسالتك تخص تصحيح معلومة في مقال، فنرجو ذكر عنوان المقال ورابطه لنتمكن من المراجعة بسرعة.</p>
<h2>أرسل رسالة</h2><p>عند الضغط على «إرسال» سيُفتح برنامج البريد لديك بالرسالة جاهزة للإرسال.</p>
<form id="contact-form" action="mailto:{e(CONTACT_EMAIL)}" method="post" enctype="text/plain">
<input name="الاسم" placeholder="الاسم الكامل" required>
<input name="البريد" type="email" placeholder="بريدك الإلكتروني" required>
<input name="الموضوع" placeholder="موضوع الرسالة" required>
<textarea name="الرسالة" rows="6" placeholder="نص الرسالة" required></textarea>
<button class="btn" type="submit">إرسال</button></form>"""),

        "privacy-policy.html": ("سياسة الخصوصية", f"""<p>آخر تحديث: {today}</p>
<p>نحترم خصوصيتك في <b>نكسوس بريس</b>. توضح هذه الصفحة أي معلومات قد تُجمع عند زيارتك للموقع، وكيف نستخدمها، وما هي خياراتك.</p>
<h2>1. المعلومات التي قد نجمعها</h2>
<ul><li><b>بيانات تقنية تلقائية:</b> مثل عنوان IP ونوع المتصفح ونظام التشغيل والصفحات التي تزورها ووقت الزيارة، وتُسجَّل عادةً لدى مزودي الاستضافة والخدمات الخارجية الموضحة أدناه.</li>
<li><b>رسائل البريد:</b> إذا راسلتنا فسنحصل على اسمك وبريدك ومحتوى رسالتك، ونستخدمها للرد عليك فقط.</li>
<li><b>التعليقات:</b> التعليقات على المقالات تُنشر عبر حساب GitHub الخاص بك، وهي عامة وتخضع لسياسة GitHub.</li></ul>
<h2>2. كيف نستخدم المعلومات</h2><p>نستخدمها لتشغيل الموقع وتحسين أدائه وتجربة القراءة، وللرد على رسائلك، ولعرض الإعلانات، ولحماية الموقع من إساءة الاستخدام. نحن لا نبيع بياناتك الشخصية.</p>
<h2>3. ملفات تعريف الارتباط (Cookies)</h2><p>قد يستخدم الموقع وشركاؤه ملفات تعريف الارتباط لحفظ تفضيلاتك (مثل لغة العرض) ولأغراض الإعلانات والتحليلات. يمكنك حذفها أو منعها من إعدادات متصفحك، وقد لا تعمل بعض الميزات كما ينبغي إذا عطّلتها.</p>
<h2>4. الإعلانات وGoogle AdSense</h2>
<p>قد نستخدم خدمة Google AdSense لعرض الإعلانات. تستخدم Google وشركاؤها ملفات تعريف الارتباط (ومنها ملف DoubleClick) لعرض إعلانات استناداً إلى زياراتك السابقة لهذا الموقع أو لمواقع أخرى. وبفضل استخدام ملفات تعريف الارتباط الإعلانية تستطيع Google وشركاؤها عرض إعلانات مناسبة لك.</p>
<ul><li>يمكنك إلغاء الإعلانات المخصصة من <a href="https://adssettings.google.com" rel="noopener" target="_blank">إعدادات إعلانات Google</a>.</li>
<li>يمكنك أيضاً إلغاء استخدام ملفات تعريف الارتباط لدى بعض الجهات الإعلانية عبر <a href="https://www.aboutads.info" rel="noopener" target="_blank">aboutads.info</a>.</li>
<li>لمعرفة كيف تستخدم Google البيانات: <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">سياسة Google للمواقع الشريكة</a>.</li></ul>
<p>إذا كنت في المنطقة الاقتصادية الأوروبية أو المملكة المتحدة أو سويسرا فقد تُعرض عليك أداة لإدارة الموافقة على ملفات تعريف الارتباط الإعلانية، ولك أن تقبل أو ترفض.</p>
<h2>5. خدمات الأطراف الثالثة</h2>
<ul><li><b>GitHub Pages:</b> استضافة الموقع، وقد تسجّل بيانات الزيارة التقنية.</li>
<li><b>Utterances (GitHub):</b> نظام التعليقات على المقالات.</li>
<li><b>Google Translate:</b> ترجمة الصفحات عند اختيارك الفرنسية أو الإنجليزية، ويُحمَّل فقط عند طلبك ذلك.</li>
<li><b>Google Fonts:</b> تحميل خط الموقع.</li>
<li><b>روابط خارجية:</b> قد نشير إلى مصادر الأخبار؛ ولا نتحمل مسؤولية سياسات الخصوصية في تلك المواقع.</li></ul>
<h2>6. مدة الاحتفاظ بالبيانات</h2><p>نحتفظ بالرسائل البريدية مدة لازمة للرد والمتابعة، ثم نحذفها عند عدم الحاجة إليها. أما بيانات الخدمات الخارجية فتخضع لسياساتها.</p>
<h2>7. حقوقك</h2><p>يحق لك طلب الاطلاع على بياناتك الشخصية التي بحوزتنا أو تصحيحها أو حذفها، والاعتراض على معالجتها وفق القوانين المعمول بها، ومنها القانون المغربي رقم 09-08 المتعلق بحماية الأشخاص الذاتيين تجاه معالجة المعطيات ذات الطابع الشخصي، ولوائح حماية البيانات الأوروبية إن كانت تنطبق عليك. لممارسة هذه الحقوق راسلنا عبر <a href="contact.html">صفحة الاتصال</a>.</p>
<h2>8. حماية الأطفال</h2><p>الموقع غير موجه للأطفال دون 13 سنة، ولا نجمع بيانات عنهم عن قصد. إذا علمت أن طفلاً قدّم لنا بيانات فراسلنا لنحذفها.</p>
<h2>9. الأمان</h2><p>نتخذ إجراءات معقولة لحماية المعلومات، ومع ذلك لا توجد وسيلة نقل أو تخزين إلكتروني آمنة بنسبة 100%.</p>
<h2>10. تعديل هذه السياسة</h2><p>قد نحدّث هذه السياسة من وقت لآخر، وسيظهر تاريخ آخر تحديث في أعلى الصفحة. استمرارك في استخدام الموقع يعني موافقتك على النسخة المحدّثة.</p>
<h2>11. اتصل بنا</h2><p>لأي استفسار عن هذه السياسة راسلنا على: <a href="mailto:{e(CONTACT_EMAIL)}" dir="ltr">{e(CONTACT_EMAIL)}</a></p>"""),
    }
    for fname, (title, body) in legal.items():
        page = (head(f"{title} | نكسوس بريس", f"{title} - نكسوس بريس", "", f"{base}/{fname}" if base else "")
                + header("", data, "") + f'<div class="container"><div class="page"><h1>{title}</h1>{body}</div></div>' + footer(""))
        (ROOT / fname).write_text(page, encoding="utf-8")

    if base:
        (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
        sm = "".join(f"<url><loc>{base}/{u}</loc></url>" for u in urls)
        (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    print(f"site built: {sum(len(v) for v in data.values())} articles")


if __name__ == "__main__":
    build()
