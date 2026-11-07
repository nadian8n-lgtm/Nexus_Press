import os
from datetime import datetime

CATEGORIES_CONFIG = {
    'ar_local': {"name": "أخبار وطنية", "keyword": "morocco,rabat,casablanca"},
    'ar_world': {"name": "الأخبار الدولية", "keyword": "global,politics,diplomacy"},
    'ar_arab': {"name": "أخبار الشرق الأوسط", "keyword": "dubai,egypt,saudi"},
    'ar_economy': {"name": "اقتصاد", "keyword": "economy,finance,money"},
    'ar_tech': {"name": "تكنولوجيا", "keyword": "cyber,technology,ai"},
    'ar_sports': {"name": "رياضة", "keyword": "soccer,stadium,football"}
}

# Génération de la base de données des 36 longs articles (6 par catégorie)
# Chaque article contient un contenu riche structuré pour le saut de ligne autonome
ARTICLES_DATA = {}
for cat, config in CATEGORIES_CONFIG.items():
    ARTICLES_DATA[cat] = []
    for i in range(6):
        ARTICLES_DATA[cat].append({
            "title": f"تقرير تحليلي معمق: مستجدات ورهانات الـ {config['name']} - الملف {i+1}",
            "content": f"تسعى القراءة التحريرية الحصرية لجريدة نكسوس بريس إلى تسليط ضوء مكثف ورصين على هذه القضية الساخنة التي تصدرت واجهة الأحداث الراهنة بشكل فوري.\n\nوفي تفاصيل هذا المشهد الصحفي المعقد، يتبين لنا أن الأبعاد الاستراتيجية والتقاطعات الميدانية تعود بالأساس إلى تراكمات هيكلية حاسمة تفرض على كافة الفاعلين في الساحة تبني سياسات مرنة ومستدامة قادرة على الصمود أمام التقلبات الدولية والوطنية المستمرة.\n\nإن التحليل الدقيق والمعطيات الميدانية التي واكبتها المنصة تشير بوضوح إلى نمو ملحوظ في الاهتمام الشعبي والمؤسساتي، نظراً لتأثيرات هذا الملف المباشرة على المعيش اليومي وقدرة الأسواق الاستهلاكية على التكيف مع التضخم العالمي وغلاء الأسعار.\n\nويرى خبراء ومحللون في تصريحات خاصة تتابعها المنصة أولاً بأول أن الحلول المطروحة حالياً تتطلب تظافر الجهود وصياغة رؤية استراتيجية تجديدية تعتمد كلياً على التحول الرقمي الشامل وتأهيل العنصر البشري ليكون قادراً على مواكبة هذه الطفرة بكفاءة عالية ونزاهة تامة تضمن تكافؤ الفرص للجميع.\n\nوفي الختام، يظهر جلياً أن المرحلة الراهنة تفتح آفاقاً تنموية واعدة تستوجب اليقظة المستمرة ومتابعة الأنباء من مصادرها الرسمية الموثوقة. وستظل شبكة نكسوس بريس الإخبارية في قلب الحدث لتضع الجمهور العريض أمام الحقيقة بأسلوب سلس ومنظم الأفكار يبتعد كلياً عن النقل التقليدي."
        })

def generate_article_html(title, content, cat_name, category_key, index):
    filename = f"news-{category_key}-{index}.html"
    next_index = (index + 1) % 6
    next_filename = f"news-{category_key}-{next_index}.html"
    image_url = f"https://unsplash.com?{CATEGORIES_CONFIG[category_key]['keyword']}&sig={index}"
    current_date = datetime.now().strftime("%d/%m/2026")
    
    # Transformation des sauts de ligne textuels en paragraphes HTML distants
    paragraphs = content.split('\n\n')
    body_p_html = "".join([f"<p class='post-p'>{p.strip()}</p>\n\n" for p in paragraphs if p.strip()])

    h = '<!DOCTYPE html>\n<html lang="ar" dir="rtl">\n<head>\n'
    h += '    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    h += f'    <title>{title} - نكسوس بريس</title>\n    <link rel="stylesheet" href="./style.css">\n</head>\n<body>\n'
    h += '    <div class="top-bar">\n        <div class="container-flex">\n'
    h += '            <span class="live-ticker-date">تحديث مستمر على مدار الساعة</span>\n'
    h += '            <div class="global-lang-wrapper" id="lang-trigger">\n'
    h += '                <span class="world-icon">🌐</span>\n'
    h += '                <div class="lang-dropdown">\n'
    h += '                    <span onclick="translateTo(\'ar\')">العربية</span>\n'
    h += '                    <span onclick="translateTo(\'fr\')">Français</span>\n'
    h += '                    <span onclick="translateTo(\'en\')">English</span>\n'
    h += '                </div>\n            </div>\n        </div>\n    </div>\n'
    h += '    <header class="main-header">\n        <div class="container-flex">\n'
    h += '            <div class="logo-area"><a href="index.html"><img src="image_MUwSAA.png" alt="Portal" class="main-logo-img"></a></div>\n'
    h += '            <div class="ad-space-header">Google AdSense Space (728x90)</div>\n        </div>\n    </header>\n'
    h += '    <main class="main-wrapper container">\n        <article class="content-area post-container">\n'
    h += f'            <span class="category-tag">{cat_name}</span>\n            <h1 class="post-title">{title}</h1>\n'
    h += f'            <div class="post-meta"><span>تاريخ النشر: {current_date}</span></div>\n'
    h += f'            <div class="post-image-wrapper"><img src="{image_url}" alt="{title}" loading="eager" style="width:100%; height:auto; max-height:450px; object-fit:cover; border-radius:4px; margin:15px 0;"></div>\n'
    h += '            <div class="ad-inside-post">Google AdSense In-Article Ad Space</div>\n'
    h += f'            <div class="post-body-text">\n{body_p_html}</div>\n'
    h += '            <div class="ad-inside-post">Google AdSense In-Article Bottom</div>\n'
    h += '            <div class="navigation-arrows">\n'
    h += '                <a href="index.html" class="nav-arrow-btn">⬅ العودة للرئيسية</a>\n'
    h += f'                <a href="./{next_filename}" class="nav-arrow-btn">المقال الموالي ➡</a>\n'
    h += '            </div>\n'
    h += '            <div class="comments-section" style="margin-top: 50px; padding-top: 30px; border-top: 2px solid #e2e8f0;">\n'
    h += '                <h3 style="margin-bottom: 20px; font-weight: 700;">شاركونا بتعليقاتكم وآرائكم حول الموضوع</h3>\n'
    h += '                <div id="disqus_thread"></div>\n            </div>\n        </article>\n'
    h += '        <aside class="sidebar-area"><div class="widget-ad-box"><span>AdSense 300x600</span></div></aside>\n'
    h += '    </main>\n'
    h += '    <footer class="main-footer">\n        <div class="container grid-footer">\n'
    h += '            <div class="footer-about"><h3>نكسوس بريس | Nexus Press</h3><p>منصة إعلامية دولية متجددة تقدم قراءات تحليلية وتغطية موسعة للأحداث الراهنة.</p></div>\n'
    h += '            <div class="footer-legal-links"><h4>القسم القانوني والتواصل</h4><ul><li><a href="privacy-policy.html">سياسة الخصوصية</a></li><li><a href="about.html">من نحن</a></li><li><a href="contact.html">اتصل بنا</a></li></ul></div>\n'
    h += '        </div>\n    </footer>\n'
    h += '    <div id="google_translate_element" style="display:none;"></div>\n'
    h += '    <script type="text/javascript">\n'
    h += '        function googleTranslateElementInit() {\n'
    h += '            new google.translate.TranslateElement({pageLanguage: "ar", layout: google.translate.TranslateElement.InlineLayout.SIMPLE}, "google_translate_element");\n'
    h += '        }\n'
    h += '        function translateTo(lang) {\n'
    h += '            var select = document.querySelector(".goog-te-combo");\n'
    h += '            if (select) { select.value = lang; select.dispatchEvent(new Event("change")); }\n'
    h += '        }\n'
    h += '    </script>\n'
    h += '    <script type="text/javascript" src="https://google.com"></script>\n'
    h += '    <script type="text/javascript">\n'
    h += '        (function() {\n'
    h += '            var d = document, s = d.createElement("script");\n'
    h += '            s.src = "https://disqus.com";\n'
    h += '            s.setAttribute("data-timestamp", +new Date());\n'
    h += '            (d.head || d.body).appendChild(s);\n'
    h += '        })();\n'
    h += '    </script>\n'
    h += '</body>\n</html>'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(h)

def main():
    for key, config in CATEGORIES_CONFIG.items():
        if key in ARTICLES_DATA:
            for i, art in enumerate(ARTICLES_DATA[key]):
                generate_article_html(art['title'], art['content'], config['name'], key, i)
    print("Compilation terminée avec succès.")

if __name__ == "__main__":
    main()
