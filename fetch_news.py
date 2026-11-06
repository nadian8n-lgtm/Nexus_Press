import os
import requests
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
        {"title": "الداخلية ترفع سقف اعتمادات الجماعات المحلية بالمملكة لدعم التنمية واللوجستيك", "content": "أعلنت وزارة الداخلية رسمياً عن حزمة قرارات مالية تهدف إلى الرفع من اعتمادات الميزانيات الموجهة للجماعات الترابية والمحلية في مختلف جهات المملكة، وذلك رغبة في تسريع وتيرة إنعاش المشاريع التنموية الحيوية المتوقفة وبناء البنيات اللوجستية الأساسية بالمنطقة تماشياً مع متطلبات المرحلة."},
        {"title": "عصيد ينتقد انصراف النقاشات إلى التفاصيل الهامشية بدل القضايا الأساسية والتعليم", "content": "أثار المفكر والناشط الحقوقي أحمد عصيد نقاشاً واسعاً بتصريحاته الأخيرة التي انتقد فيها بشدة انشغال الفاعلين بالجزئيات والهوامش التحريرية، معتبراً أن المرحلة الحالية تتطلب التركيز التام على القضايا الهيكلية المباشرة كدعم التعليم والصحة والإصلاح الإداري الشامل."}
    ],
    'ar_world': [
        {"title": "آخر الأخبار الدولية ومستجدات الحراك السياسي وملفات الأمن بمنطقة الشرق الأوسط", "content": "تشهد عواصم منطقة الشرق الأوسط حراكاً دبلوماسياً مكثفاً ولقاءات رفيعة المستوى لبناء تفاهمات مشتركة تسعى كلياً لخفض التصعيد العسكري وتأمين المعابر الحيوية وتثبيت دعائم السلم والاستقرار الاقتصادي والسياسي وحماية الملاحة الدولية الحرة."}
    ],
    'ar_economy': [
        {"title": "مؤشرات النمو الاقتصادي وتقلبات أسعار الطاقة والمحروقات والملاحة دولياً", "content": "تواجه أسواق النفط والغاز العالمية تقلبات مستمرة تؤثر مباشرة على مؤشرات الاستهلاك الداخلي وأسعار المحروقات المحلية، مما يفرض مراجعة مستمرة للاتفاقيات وعقود الشحن لتفادي تداعيات التضخم والحفاظ على استقرار مؤشرات التنمية العمومية للبلاد."}
    ],
    'ar_tech': [
        {"title": "ثورة الذكاء الاصطناعي التوليدي تعيد صياغة مفاهيم الإنتاج البرمجي والويب العالمي", "content": "تشهد الأوساط التقنية العالمية طفرة غير مسبوقة مع تسارع وتيرة نماذج الذكاء الاصطناعي التوليدي الفائقة لعام 2026، حيث دخلت الأدوات الذكية في صلب ميكنة الإنتاج وتطوير البرمجيات المعقدة والمواقع الإلكترونية عالية الدقة، مما يعيد رسم ملامح سوق الشغل والابتكار التكنولوجي."}
    ],
    'ar_sports': [
        {"title": "متابعة الفعاليات الرياضية الوطنية وإنجازات المنتخبات والنخب في المحافل الكبرى", "content": "تواصل المنظومة الرياضية الوطنية تألقها الاستثنائي، حيث نجحت المنتخبات والنخب بمختلف الألعاب الجماعية في تحقيق نتائج مشرفة تعكس كفاءة الخطط الاستراتيجية والدعم المؤسساتي الموجه لتطوير القطاع الرياضي ورفع الراية الوطنية عالياً."}
    ],
    'ar_arts': [
        {"title": "الملتقيات الثقافية الدولية تبحث حماية الهوية الوطنية والتراث في العصر الرقمي", "content": "انطلقت فعاليات المنتديات الثقافية النخبوية الكبرى لبناء رؤية استراتيجية واعدة تعنى بحفظ الهوية التراثية وحماية الفنون التقليدية أمام زحف العولمة الرقمية، وسلاسل الإنتاج السريع، مع التركيز على دعم المبدعين والصناعات الإبداعية المستقلة كرافعة حقيقية للتنمية المستدامة."}
    ]
}

def generate_ai_image(keywords):
    return f"https://unsplash.com?{keywords}"

def generate_article_html(title, content, cat_name, filename, keywords):
    image_url = generate_ai_image(keywords)
    current_date = datetime.now().strftime("%d/%m/2026")
    
    # بناء هيكل الصفحة بالاعتماد على مصفوفات نصوص واضحة ومغلقة بدون تداخل f-string مع الجافا سكريبت
    html_lines = [
        '<!DOCTYPE html>',
        '<html lang="ar" dir="rtl">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{title} - نكسوس بريس</title>',
        '    <link rel="stylesheet" href="./style.css">',
        '</head>',
        '<body>',
        '    <header class="main-header" style="background:#e0f2fe !important;">',
        '        <div class="container-flex">',
        '            <a href="index.html"><img src="image_MUwSAA.png" alt="Portal" class="main-logo-img"></a>',
        '            <div class="ad-space-header">مساحة إعلانية مجهزة (Google AdSense 728x90)</div>',
        '        </div>',
        '    </header>',
        '    <main class="main-wrapper container">',
        '        <article class="content-area post-container">',
        f'            <span class="category-tag">{cat_name}</span>',
        f'            <h1 class="post-title">{title}</h1>',
        f'            <div class="post-meta"><span>تحرير: القسم الصحفي الدولي</span> | <span>تاريخ النشر: {current_date}</span></div>',
        f'            <div class="post-image-wrapper"><img src="{image_url}" alt="{title}" loading="eager" style="width:100%; height:auto; max-height:450px; object-fit:cover; border-radius:4px; margin:15px 0;"></div>',
        '            <div class="ad-inside-post">Google AdSense In-Article Ad Space (أعلى الفقرات)</div>',
        f'            <p class="post-p">{content}</p>',
        '            <div class="ad-inside-post">Google AdSense In-Article Ad Space (أسفل المقال)</div>',
        '            <div class="comments-section" style="margin-top: 50px; padding-top: 30px; border-top: 2px solid #e2e8f0;">',
        '                <h3 style="margin-bottom: 20px; font-weight: 700; color: #071c35;">شاركونا بتعليقاتكم وآرائكم حول الموضوع</h3>',
        '                <div id="disqus_thread"></div>',
        '            </div>',
        '        </article>',
        '        <aside class="sidebar-area">',
        '            <div class="widget-ad-box"><span>مساحة إعلانية عمودية بجانب المقال (AdSense 300x600)</span></div>',
        '        </aside>',
        '    </main>',
        '</body>',
        '</html>'
    ]
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_lines))

def main():
    for key, config in CATEGORIES_CONFIG.items():
        if key in ARTICLES_DATA:
            for i, art in enumerate(ARTICLES_DATA[key]):
                filename = f"news-{key}-{i}.html"
                generate_article_html(art['title'], art['content'], config['name'], filename, config['keyword'])
                print(f"[Success]: {filename} compiled cleanly.")

if __name__ == "__main__":
    main()
