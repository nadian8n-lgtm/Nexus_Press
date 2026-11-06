import os
from datetime import datetime

CATEGORIES_CONFIG = {
    'ar_local': {"name": "أخبار وطنية", "keyword": "morocco,rabat"},
    'ar_world': {"name": "الأخبار الدولية", "keyword": "global,politics"},
    'ar_economy': {"name": "اقتصاد", "keyword": "economy,finance"},
    'ar_tech': {"name": "تكنولوجيا", "keyword": "cyber,technology"},
    'ar_sports': {"name": "رياضة", "keyword": "soccer,stadium"},
    'ar_arts': {"name": "فن وثقافة", "keyword": "painting,culture"}
}

ARTICLES_DATA = {
    'ar_local': [
        {"title": "الداخلية ترفع سقف اعتمادات الجماعات المحلية بالمملكة لدعم التنمية واللوجستيك", "content": "أعلنت وزارة الداخلية رسمياً عن حزمة قرارات مالية تهدف إلى الرفع من اعتمادات الميزانيات الموجهة للجماعات الترابية والمحلية في مختلف جهات المملكة، وذلك رغبة في تسريع وتيرة إنعاش المشاريع التنموية الحيوية المتوقفة وبناء البنيات اللوجستية الأساسية بالمنطقة تماشياً مع متطلبات المرحلة الجارية."},
        {"title": "عصيد ينتقد انصراف النقاشات إلى التفاصيل الهامشية بدل القضايا الأساسية والتعليم", "content": "أثار المفكر والناشط الحقوقي أحمد عصيد نقاشاً واسعاً بتصريحاته الأخيرة التي انتقد فيها بشدة انشغال الفاعلين بالجزئيات والهوامش التحريرية والسياسية، معتبراً أن المرحلة الحالية تتطلب التركيز التام على القضايا الهيكلية المباشرة كدعم التعليم والصحة والإصلاح الإداري الشامل بالمملكة."}
    ],
    'ar_world': [
        {"title": "آخر الأخبار الدولية ومستجدات الحراك السياسي وملفات الأمن بمنطقة الشرق الأوسط", "content": "تشهد عواصم منطقة الشرق الأوسط حراكاً دبلوماسياً مكثفاً ولقاءات رفيعة المستوى لبناء تفاهمات مشتركة تسعى كلياً لخفض التصعيد العسكري وتأمين المعابر الحيوية وتثبيت دعائم السلم والاستقرار الاقتصادي والسياسي وحماية الملاحة الدولية الحرة."}
    ]
}

def generate_article_html(title, content, cat_name, category_key, index):
    filename = f"news-{category_key}-{index}.html"
    next_index = (index + 1) % 2 if category_key == 'ar_local' else 0
    next_filename = f"news-{category_key}-{next_index}.html"
    image_url = f"https://unsplash.com?{CATEGORIES_CONFIG[category_key]['keyword']}&sig={index}"
    current_date = datetime.now().strftime("%d/%m/2026")
    
    # تنسيق نص المقال إلى فقرات معزولة بأسطر فارغة واضحة تمنع الالتصاق كلياً
    paragraphs = content.split('\n\n')
    body_p_html = ""
    for p in paragraphs:
        if p.strip():
            body_p_html += f"<p class='post-p'>{p.strip()}</p>\n\n"

    # بناء الكود النصي المقفل سطر بسطر لمنع انقطاع الأقواس والكسور نهائياً
    h = '<!DOCTYPE html>\n<html lang="ar" dir="rtl">\n<head>\n'
    h += '    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    h += f'    <title>{title} - نكسوس بريس</title>\n    <link rel="stylesheet" href="./style.css">\n</head>\n<body>\n'
    h += '    <div class="top-bar">\n        <div class="container-flex">\n'
    h += '            <span class="live-ticker-date">تحديث مستمر على مدار الساعة</span>\n'
    h += '            <div class="global-lang-wrapper">\n'
    h += '                <span class="lang-btn" onclick="translateTo(\'ar\')">العربية</span> | \n'
    h += '                <span class="lang-btn" onclick="translateTo(\'fr\')">Français</span> | \n'
    h += '                <span class="lang-btn" onclick="translateTo(\'en\')">English</span>\n'
    h += '            </div>\n        </div>\n    </div>\n'
    h += '    <header class="main-header">\n        <div class="container-flex">\n'
    h += '            <div class="logo-area"><a href="index.html"><img src="image_MUwSAA.png" alt="Portal" class="main-logo-img"></a></div>\n'
    h += '            <div class="nav-links-header-top"><a href="index.html">الرئيسية</a> | <a href="about.html">من نحن</a> | <a href="contact.html">اتصل بنا</a></div>\n'
    h += '            <div class="ad-space-header">Google AdSense Space</div>\n        </div>\n    </header>\n'
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
    h += '                <h3 style="margin-bottom: 20px; font-weight: 700;">شاركونا بتعليقاتكم وآرائكم</h3>\n'
    h += '                <div id="disqus_thread"></div>\n            </div>\n        </article>\n'
    h += '        <aside class="sidebar-area"><div class="widget-ad-box"><span>AdSense 300x600</span></div></aside>\n'
    h += '    </main>\n'
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
    h += '</body>\n</html>'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(h)

def main():
    for key, config in CATEGORIES_CONFIG.items():
        if key in ARTICLES_DATA:
            for i, art in enumerate(ARTICLES_DATA[key]):
                generate_article_html(art['title'], art['content'], config['name'], key, i)
    print("Compilation terminee avec succes.")

if __name__ == "__main__":
    main()
