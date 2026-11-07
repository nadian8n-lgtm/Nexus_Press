import os
from datetime import datetime

CATEGORIES_CONFIG = {
    'ar_local': {"name": "أخبار وطنية", "keyword": "morocco,rabat,casablanca"},
    'ar_world': {"name": "الأخبار الدولية", "keyword": "global,politics,diplomacy"},
    'ar_economy': {"name": "اقتصاد", "keyword": "economy,finance,stocks"},
    'ar_tech': {"name": "تكنولوجيا", "keyword": "cyber,technology,ai"},
    'ar_sports': {"name": "رياضة", "keyword": "soccer,stadium,maroc"},
    'ar_arts': {"name": "فن وثقافة", "keyword": "painting,culture,library"}
}

ARTICLES_DATA = {
    'ar_local': [
        {"title": "الداخلية ترفع سقف اعتمادات الجماعات المحلية بالمملكة لدعم التنمية واللوجستيك", "content": "أعلنت وزارة الداخلية رسمياً عن حزمة قرارات مالية تهدف إلى الرفع من اعتمادات الميزانيات الموجهة للجماعات الترابية والمحلية في مختلف جهات المملكة، وذلك رغبة في تسريع وتيرة إنعاش المشاريع التنموية الحيوية المتوقفة وبناء البنيات اللوجستية الأساسية بالمنطقة تماشياً مع متطلبات المرحلة الجارية.\n\nوتسعى هذه الخطوة الاستراتيجية إلى تمكين المجالس المنتخبة من الوسائل المادية الكفيلة بإنجاز البرامج التنموية المسطرة، خاصة تلك المتعلقة بالبنية التحتية والربط بشبكات الماء الشروب والكهرباء، فضلا عن تأهيل المراكز الصاعدة وتوفير فرص الشغل للشباب.\n\nوقد أكد المسؤولون أن الصرف الفعلي لهذه الاعتمادات سيخضع لآليات رقابية صارمة لضمان الحكامة الجيدة والشفافية المطلقة في تدبير المال العام، مع ترتيب المسؤوليات في حال تسجيل أي خروقات إدارية أو مالية قد تعيق السير العادي للمشاريع."},
        {"title": "عصيد ينتقد انصراف النقاشات إلى التفاصيل الهامشية بدل القضايا الأساسية والتعليم", "content": "أثار المفكر والناشط الحقوقي أحمد عصيد نقاشاً واسعاً بتصريحاته الأخيرة التي انتقد فيها بشدة انشغال الفاعلين بالجزئيات والهوامش التحريرية والسياسية، معتبراً أن المرحلة الحالية تتطلب التركيز التام على القضايا الهيكلية المباشرة كدعم التعليم والصحة والإصلاح الإداري الشامل بالمملكة.\n\nوأشار عصيد إلى أن هدر الزمن السياسي في نقاشات عقيمة لا تخدم المصلحة العليا للوطن يساهم في إحباط الفاعلين الاقتصاديين والاجتماعيين، ويوجه الرأي العام نحو مسارات ثانوية بعيدة كل البعد عن الرهانات الحقيقية المتعلقة بالتنمية والعدالة الاجتماعية.\n\nودعا المتحدث إلى ضرورة فتح حوار وطني جاد ومسؤول يجمع كافة الحساسيات الفكرية والسياسية لصياغة تعاقد مجتمعي جديد يضع منظومة التربية والتكوين في صدارة الأولويات، كركيزة أساسية لبناء مجتمع المعرفة والحداثة."}
    ],
    'ar_world': [
        {"title": "آخر الأخبار الدولية ومستجدات الحراك السياسي وملفات الأمن بمنطقة الشرق الأوسط", "content": "تشهد عواصم منطقة الشرق الأوسط حراكاً دبلوماسياً مكثفاً ولقاءات رفيعة المستوى لبناء تفاهمات مشتركة تسعى كلياً لخفض التصعيد العسكري وتأمين المعابر الحيوية وتثبيت دعائم السلم والاستقرار الاقتصادي والسياسي وحماية الملاحة الدولية الحرة.\n\nوتأتي هذه التحركات في ظل تحديات أمنية متزايدة تفرض على القوى الإقليمية والدولية تنسيق الجهود لتفادي انزلاق المنطقة نحو مواجهات واسعة قد تعصف بأمن الطاقة العالمي وتؤثر سلباً على مسارات التجارة العابرة للقارات.\n\nوقد دعت الأطراف المجتمعة إلى ضرورة الالتزام بالمواثيق الدولية والقرارات الأممية، وفتح قنوات حوار مباشرة لمعالجة الأسباب الجذرية للنزاعات، بعيداً عن سياسات فرض الأمر الواقع التحريرية."}
    ]
}

def generate_article_html(title, content, cat_name, category_key, index):
    filename = f"news-{category_key}-{index}.html"
    next_index = (index + 1) % 2 if category_key == 'ar_local' else 0
    next_filename = f"news-{category_key}-{next_index}.html"
    
    # محرك جلب الصور التلقائي الذكي بناء على الكلمات المفتاحية ورقم المقال لمنع التكرار
    image_url = f"https://unsplash.com?{CATEGORIES_CONFIG[category_key]['keyword']}&sig={index}"
    current_date = datetime.now().strftime("%d/%m/2026")
    
    paragraphs = content.split('\n\n')
    body_p_html = ""
    for p in paragraphs:
        if p.strip():
            body_p_html += f"<p class='post-p'>{p.strip()}</p>\n\n"

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
    h += '            <div class="ad-space-header">Google AdSense Space</div>\n        </div>\n    </header>\n'
    h += '    <main class="main-wrapper container">\n        <article class="content-area post-container">\n'
    h += f'            <span class="category-tag">{cat_name}</span>\n            <h1 class="post-title">{title}</h1>\n'
    h += f'            <div class="post-meta"><span>تاريخ النشر: {current_date}</span></div>\n'
    
    # وسم الصورة مبرمج ومفعل في أعلى المقال الداخلي بنجاح
    h += f'            <div class="post-image-wrapper"><img src="{image_url}" alt="{title}" loading="eager" class="article-main-img"></div>\n'
    
    h += '            <div class="ad-inside-post">Google AdSense In-Article Ad Space</div>\n'
    h += f'            <div class="post-body-text">\n{body_p_html}</div>\n'
    h += '            <div class="ad-inside-post">Google AdSense In-Article Bottom</div>\n'
    h += '            <div class="navigation-arrows">\n'
    h += f'                <a href="./{next_filename}" class="nav-arrow-btn">المقال الموالي ➡</a>\n'
    h += '            </div>\n'
    h += '            <div class="comments-section">\n'
    h += '                <h3 style="margin-bottom: 20px; font-weight: 700;">شاركونا بتعليقاتكم وآرائكم</h3>\n'
    h += '                <div id="disqus_thread"></div>\n            </div>\n        </article>\n'
    h += '        <aside class="sidebar-area"><div class="widget-ad-box"><span>AdSense 300x600</span></div></aside>\n'
    h += '    </main>\n'
    h += '    <footer class="main-footer">\n'
    h += '        <div class="container grid-footer">\n'
    h += '            <div class="footer-about"><h3>نكسوس بريس | Nexus Press</h3><p>منصة إعلامية دولية مستقلة ومصادق عليها تقدم قراءات تحليلية وتغطية موسعة للأحداث الراهنة.</p></div>\n'
    h += '            <div class="footer-legal-links"><ul><li><a href="privacy-policy.html">سياسة الخصوصية</a></li><li><a href="about.html">من نحن</a></li><li><a href="contact.html">اتصل بنا</a></li></ul></div>\n'
    h += '        </div>\n'
    h += '        <div class="footer-bottom-bar"><p>&copy; 2026 نكسوس بريس. جميع الحقوق التحريرية محفوظة.</p></div>\n'
    h += '    </footer>\n'
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
