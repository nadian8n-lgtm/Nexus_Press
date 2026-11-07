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
<script>
(function(){{
  var m=document.cookie.match(/googtrans=\\/ar\\/(\\w+)/),cur=m?m[1]:'ar';
  if(cur!=='ar'){{document.documentElement.dir='ltr';document.documentElement.lang=cur;}}
  document.querySelectorAll('.lang-btn').forEach(function(b){{
    if(b.dataset.l===cur)b.classList.add('on');
    b.onclick=function(){{
      var l=b.dataset.l,h=location.hostname,past='expires=Thu, 01 Jan 1970 00:00:00 GMT';
      if(l==='ar'){{document.cookie='googtrans=;path=/;'+past;document.cookie='googtrans=;path=/;domain='+h+';'+past;}}
      else{{document.cookie='googtrans=/ar/'+l+';path=/';document.cookie='googtrans=/ar/'+l+';path=/;domain='+h;}}
      location.reload();
    }};
  }});
  var s=document.querySelectorAll('.slide'),i=0;
  if(s.length>1)setInterval(function(){{s[i].classList.remove('active');i=(i+1)%s.length;s[i].classList.add('active');}},5000);
}})();
function googleTranslateElementInit(){{new google.translate.TranslateElement({{pageLanguage:'ar',includedLanguages:'ar,fr,en',autoDisplay:false}},'google_translate_element');}}
</script>
<script src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
</body></html>"""


def card(a, pre, cat):
    return (f'<a class="card" href="{pre}articles/{a["id"]}.html"><img loading="lazy" src="{pre}{e(a["image"])}" alt="{e(a.get("image_alt", a["title"]))}">'
            f'<div class="info"><span class="badge">{e(CATEGORIES[cat])}</span><h3>{e(a["title"])}</h3><p>{e(a["date"][:10])}</p></div></a>')


def sidebar(pre, data):
    latest = sorted((a for k in CATEGORIES for a in data[k]), key=lambda a: a["date"], reverse=True)[:6]
    lis = "".join(f'<li><a href="{pre}articles/{a["id"]}.html">{e(a["title"])}</a></li>' for a in latest)
    return f'<aside><div class="widget"><h4>الأحدث</h4><ul>{lis or "<li>قريباً</li>"}</ul></div></aside>'


def render_body(content):
    out = []
    for block in re.split(r"\n\s*\n", content.strip()):
        block = block.strip()
        if block.startswith("## "):
            out.append(f"<h2>{e(block[3:].strip())}</h2>")
        elif block:
            out.append(f"<p>{e(block)}</p>")
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
    slides = "".join(
        f'<a class="slide{" active" if i == 0 else ""}" href="articles/{a["id"]}.html"><img src="{e(a["image"])}" alt="{e(a["title"])}"><div class="cap"><span class="badge">{e(CATEGORIES[k])}</span><h2>{e(a["title"])}</h2></div></a>'
        for i, (k, a) in enumerate(allart[:3]))
    sections = ""
    for k, name in CATEGORIES.items():
        if data[k]:
            sections += (f'<h2 class="block-title" style="margin-top:30px">{e(name)}</h2><div class="grid">'
                         + "".join(card(a, "", k) for a in data[k][:6]) + "</div>"
                         + f'<p style="margin-top:12px"><a class="badge" href="category-{k}.html">كل مقالات {e(name)} ←</a></p>')
    if not sections:
        sections = '<div class="empty">لا توجد مقالات منشورة بعد.</div>'
    page = (head("نكسوس بريس | Nexus Press - أخبار العالم على مدار الساعة", "جريدة نكسوس بريس: تغطية موسعة وتحليلات لأبرز الأخبار العالمية والعربية في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة.", "", base + "/" if base else "")
            + header("", data, "home")
            + f'<div class="container">{"<div class=slider>" + slides + "</div>" if slides else ""}<div class="layout"><main>{sections}</main>{sidebar("", data)}</div></div>'
            + footer(""))
    (ROOT / "index.html").write_text(page, encoding="utf-8")

    # categories + articles
    for k, name in CATEGORIES.items():
        cards = "".join(card(a, "", k) for a in data[k]) or '<div class="empty">لا توجد مقالات في هذا القسم بعد.</div>'
        page = (head(f"{name} | نكسوس بريس", f"آخر مقالات قسم {name} في جريدة نكسوس بريس.", "", f"{base}/category-{k}.html" if base else "")
                + header("", data, k)
                + f'<div class="container"><div class="layout"><main><h1 class="block-title">{e(name)}</h1><div class="grid">{cards}</div></main>{sidebar("", data)}</div></div>'
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
                    + f"""<div class="container"><div class="layout"><main><article class="article">
<span class="badge">{e(name)}</span><h1>{e(a["title"])}</h1>
<div class="meta">هيئة تحرير نكسوس بريس · {e(a["date"][:10])}</div>
<img class="hero" src="../{e(a["image"])}" alt="{e(a.get("image_alt", a["title"]))}">
<div class="article-body">

{render_body(a["content"])}

</div>{src_html}{comments_block()}</article>
<section class="related"><h2 class="block-title">مقالات ذات صلة</h2><div class="grid">{related}</div></section></main>{sidebar("../", data)}</div></div>"""
                    + footer("../"))
            (ROOT / "articles" / f"{a['id']}.html").write_text(page, encoding="utf-8")
            urls.append(f"articles/{a['id']}.html")

    # legal pages
    legal = {
        "about.html": ("من نحن", """<p>نكسوس بريس جريدة إلكترونية عربية تتابع أبرز أحداث العالم في السياسة والاقتصاد والتكنولوجيا والرياضة والثقافة، وتقدمها للقارئ بلغة واضحة وسياق كافٍ لفهم الخبر وليس مجرد نقله.</p>
<h2>كيف نعمل</h2><p>نعتمد على وكالات الأنباء والصحف والمؤسسات الإعلامية المعروفة مصادرَ للمعلومة، ونعيد تقديم الخبر بصياغتنا الخاصة مع الإشارة إلى مصادره في أسفل كل مقال. تمر المواد عبر مراجعة تحريرية قبل النشر.</p>
<h2>التزاماتنا</h2><ul><li>الدقة والتحقق من المعلومة قبل نشرها.</li><li>الفصل بين الخبر والرأي.</li><li>تصحيح الأخطاء بسرعة وشفافية عند اكتشافها.</li><li>احترام حقوق الملكية الفكرية وعدم نسخ محتوى الآخرين.</li></ul>
<h2>تصحيح الأخطاء</h2><p>إذا لاحظت خطأً في أي مقال فراسلنا عبر صفحة <a href="contact.html">اتصل بنا</a> وسنراجعه فوراً.</p>"""),
        "contact.html": ("اتصل بنا", f"""<p>للاستفسارات والاقتراحات وطلبات التصحيح والتعاون الإعلاني، راسلنا على البريد: <a href="mailto:{e(CONTACT_EMAIL)}"><b dir="ltr">{e(CONTACT_EMAIL)}</b></a></p>
<form action="mailto:{e(CONTACT_EMAIL)}" method="post" enctype="text/plain">
<input name="name" placeholder="الاسم الكامل" required><input name="email" type="email" placeholder="البريد الإلكتروني" required>
<input name="subject" placeholder="موضوع الرسالة" required><textarea name="message" rows="6" placeholder="نص الرسالة" required></textarea>
<button class="btn" type="submit">إرسال</button></form>"""),
        "privacy-policy.html": ("سياسة الخصوصية", f"""<p>آخر تحديث: {datetime.now().strftime('%Y-%m-%d')}. توضح هذه السياسة كيف يتعامل موقع نكسوس بريس مع بيانات الزوار.</p>
<h2>1. البيانات التي نجمعها</h2><p>قد تُجمع بيانات تقنية مجهولة مثل نوع المتصفح والجهاز والصفحات التي تمت زيارتها وعنوان IP، لتحليل الأداء وتحسين الموقع. لا نطلب منك بيانات شخصية لتصفح الموقع.</p>
<h2>2. ملفات تعريف الارتباط (Cookies)</h2><p>نستخدم ملفات تعريف الارتباط لحفظ تفضيلاتك مثل لغة العرض، ولأغراض الإعلانات والتحليلات كما هو موضح أدناه. يمكنك تعطيلها من إعدادات متصفحك.</p>
<h2>3. الإعلانات وجوجل أدسنس</h2><p>قد نعرض إعلانات عبر Google AdSense. تستخدم Google وشركاؤها ملفات تعريف الارتباط لعرض إعلانات بناءً على زياراتك السابقة لهذا الموقع أو لمواقع أخرى. يمكنك إلغاء الإعلانات المخصصة من <a href="https://adssettings.google.com" rel="noopener" target="_blank">إعدادات إعلانات Google</a> أو زيارة <a href="https://www.aboutads.info" rel="noopener" target="_blank">aboutads.info</a>. للمزيد: <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">كيف تستخدم Google البيانات</a>.</p>
<h2>4. الخدمات الخارجية</h2><p>يستخدم الموقع خدمة Google Translate لترجمة الصفحات، وخدمة Utterances (GitHub) للتعليقات، وخطوط Google. لهذه الجهات سياساتها الخاصة في الخصوصية. التعليقات المنشورة عبر GitHub تكون عامة وتخضع لسياسة GitHub.</p>
<h2>5. حماية الأطفال</h2><p>الموقع غير موجه للأطفال دون 13 سنة ولا نجمع عنهم بيانات عن قصد.</p>
<h2>6. حقوقك</h2><p>يمكنك طلب الاطلاع على بياناتك أو حذفها بمراسلتنا عبر <a href="contact.html">صفحة الاتصال</a>.</p>
<h2>7. تعديل السياسة</h2><p>قد نحدّث هذه السياسة من وقت لآخر، وسيظهر تاريخ آخر تحديث أعلاها.</p>"""),
    }
    for fname, (title, body) in legal.items():
        page = (head(f"{title} | نكسوس بريس", f"{title} - نكسوس بريس", "", f"{base}/{fname}" if base else "")
                + header("", data, "") + f'<div class="container"><div class="page"><h1>{title}</h1>{body}</div></div>' + footer(""))
        (ROOT / fname).write_text(page, encoding="utf-8")

    if base:
        sm = "".join(f"<url><loc>{base}/{u}</loc></url>" for u in urls)
        (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    print(f"site built: {sum(len(v) for v in data.values())} articles")


if __name__ == "__main__":
    build()
