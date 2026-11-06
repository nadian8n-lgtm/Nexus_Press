import os
import requests
from datetime import datetime

# الأقسام الـ 7 المطلوبة للموقع بالكامل مع الكلمات المفتاحية لمهندس أوامر الصور الذكي
CATEGORIES_CONFIG = {
    'ar_local': {"name": "أخبار وطنية", "keyword": "morocco,rabat,casablanca", "topics": [
        "الداخلية ترفع سقف اعتمادات الجماعات المحلية بالمملكة لدعم التنمية واللوجستيك",
        "عصيد ينتقد انصراف النقاشات إلى التفاصيل الهامشية بدل القضايا الأساسية والتعليم",
        "مشاريع البنية التحتية الكبرى بالمملكة تدخل مراحل التنفيذ الميداني الفعلي",
        "قرارات تشريعية جديدة لتبسيط المساطر الإدارية وتسهيل الاستثمار الوطني",
        "إشادة دولية واسعة بجهود المغرب في قطاع الطاقات المتجددة والنظيفة",
        "خطة وطنية موسعة لتحديث منظومة النقل اللوجستيكي والربط السككي بين المدن"
    ]},
    'ar_world': {"name": "الأخبار الدولية", "keyword": "global,politics,diplomacy", "topics": [
        "آخر الأخبار الدولية ومستجدات الحراك السياسي وملفات الأمن بمنطقة الشرق الأوسط",
        "آخر الأخبار الدولية والتحولات الاقتصادية والسياسية الراهنة في القارة الأوروبية",
        "آخر الأخبار الدولية والتوجهات الاستراتيجية والتجارية الجديدة في أمريكا والبيت الأبيض",
        "آخر الأخبار الدولية والفرص التنموية والاقتصادية الواعدة في القارة الإفريقية",
        "آخر الأخبار الدولية وتقاطعات الدبلوماسية وأسواق الإمداد والشحن العالمية",
        "آخر الأخبار الدولية واستشراف التوازنات الاستراتيجية المقبلة في المنطقة والعالم"
    ]},
    'ar_economy': {"name": "اقتصاد", "keyword": "economy,finance,oil", "topics": [
        "مؤشرات النمو الاقتصادي وتقلبات أسعار الطاقة والمحروقات والملاحة دولياً",
        "مستجدات أسعار المواد الاستهلاكية والتدابير الحمائية الحكومية للقدرة الشرائية للأسر",
        "تحليلات أسواق المال وأداء الأسهم والبورصات العالمية تحت المجهر هذا الأسبوع",
        "السياسات النقدية والمصرفية المرتقبة للبنوك المركزية للحد من تداعيات التضخم",
        "أزمة الشحن البحري وتأثيرها المباشر على تدفق السلع الأساسية والمواد الأولية",
        "رهانات الأمن الغذائي والاكتفاء الذاتي الزراعي في ظل تقلبات المناخ الدولية"
    ]},
    'ar_tech': {"name": "تكنولوجيا", "keyword": "cyber,technology,ai", "topics": [
        "ثورة الذكاء الاصطناعي التوليدي تعيد صياغة مفاهيم الإنتاج البرمجي والويب العالمي",
        "الأمن السيبراني وحماية البيانات الحيوية في ظل التهديدات الرقمية وحرب الحوسبة",
        "الجيل القادم من الهواتف الذكية والأجهزة القابلة للارتداء والرقاقات الذكية لعام 2026",
        "الحوسبة الكمومية والآفاق المستقبلية الواعدة لحل المعضلات الرياضية المعقدة في ثوانٍ",
        "استراتيجيات التحول الرقمي الشامل للمؤسسات والمقاولات الناشئة والمتوسطة بالمملكة",
        "تكنولوجيا الميتافيرس والواقع الممتد في مجالات التعليم الحديث والتكوين المهني"
    ]},
    'ar_sports': {"name": "رياضة", "keyword": "soccer,stadium,athlete", "topics": [
        "متابعة الفعاليات الرياضية الوطنية وإنجازات المنتخبات والنخب في المحافل الكبرى",
        "تألق لافت لمراكز التكوين الوطنية في إبراز واحتضان المواهب الرياضية الجديدة والناشئة",
        "استعدادات مكثفة للأبطال المغاربة لخوض غمار الاستحقاقات القارية والأولمبية المقبلة",
        "الأندية الوطنية تواصل هيمنتها الصارمة على المسابقات والبطولات الإفريقية الكبرى",
        "حصاد متميز من الميداليات الذهبية في الألعاب الفردية والفنون القتالية العالمية",
        "جاهزية تامة للبنيات التحتية والملاعب الرياضية لاستضافة كبرى التظاهرات المونديالية"
    ]},
    'ar_arts': {"name": "فن وثقافة", "keyword": "painting,culture,library", "topics": [
        "الملتقيات الثقافية الدولية تبحث حماية الهوية الوطنية والتراث في العصر الرقمي",
        "تطور الفنون التشكيلية والمعارض المعاصرة وصعود المدارس البصرية في العالم العربي",
        "السينما المستقلة والإنتاجات الوثائقية المبدعة تحصد جوائز التمييز في المهرجانات",
        "صون المخطوطات التاريخية والمعالم الأثرية عبر تقنيات المسح الضوئي ثلاثي الأبعاد",
        "المهرجانات الموسيقية التراثية تعزز قيم التسامح والتبادل والتعايش الثقافي بين الشعوب",
        "أدب الرحلات والرواية العربية المعاصرة في مواجهة التحولات الرقمية المتسارعة للجيل"
    ]}
}

def call_openai_for_journalism(title, cat_name):
    """ استدعاء ذكي لـ OpenAI API لصياغة مقال احترافي بشري موسع ومقاوم تماماً للبلاجياريزم """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return f"هذا تقرير صحفي تحليلي موسع ومكتوب بأسلوب تحريري رصين وخالٍ تماماً من الأخطاء الإملائية حول موضوع: {title}. يتناول هذا التقرير كافة الأبعاد الاستراتيجية والخلفيات الميدانية المرتبطة بالقطاع، تماشياً مع مستجدات الساحة الراهنة التي تتابعها منصة نكسوس بريس الإخبارية أولاً بأول لتضع الجمهور في قلب الحدث بكل موضوعية ونزاهة تحريرية مستدامة."

    try:
        url = "https://openai.com"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = f"اكتب تقريراً صحفياً تحليلياً موسعاً ومفصلاً جداً (بين 800 و1500 كلمة) باللغة العربية الفصحى وبأسلوب كبار الكتاب التحريريين، بدون أخطاء إملائية أو نحوية، وخالٍ تماماً من الانتحال والنسخ، بناءً على هذا العنوان الإخباري: {title}. القسم: {cat_name}. قسم النص إلى 6 فقرات واضحة ومطولة تفصلها ميزة الأسطر الفارغة المريحة للعين."
        data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data, timeout=50)
        if response.status_code == 200:
            return response.json()['choices']['message']['content']
    except Exception as e:
        print(f"تعذر الاتصال بالذكاء الاصطناعي، جاري ضخ البنية التحريرية البديلة: {e}")
    return f"تقرير صحفي موسع ومحترف حول {title}. يوضح كافة تفاصيل هذا الملف الساخن على الساحة الحالية."

def generate_ai_image(title, keywords):
    """ صياغة برومبت احترافي صحفي فوتوغرافي واقعي متجاوب مع السيو وسريع التحميل """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return f"https://unsplash.com?{keywords}"
    try:
        url = "https://openai.com"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = f"Professional editorial news photography, documentary hyper-realistic style, crisp commercial lighting, representing: {title}. HTML optimized."
        data = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "standard", "style": "natural"}
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()['data']['url']
    except Exception as e:
        print(f"جاري السحب التلقائي الآمن للصور: {e}")
    return f"https://unsplash.com?{keywords}"

def generate_article_html(title, cat_name, category_key, filename, keywords):
    journalistic_text = call_openai_for_journalism(title, cat_name)
    image_url = generate_ai_image(title, keywords)
    current_date = datetime.now().strftime("%d/%m/2026")
    
    # تحويل النصوص والفقرات المستلمة آلياً إلى وسوم فقرات برمجية معزولة بسطر كامل فارغ
    paragraphs = journalistic_text.split('\n')
    formatted_paragraphs = ""
    for idx, p in enumerate(paragraphs):
        if p.strip():
            formatted_paragraphs += f"<p class='post-p'>{p.strip()}</p>\n\n"
            if idx == 1:
                formatted_paragraphs += '<div class="ad-inside-post">Google AdSense In-Article Ad Space (أعلى الفقرات)</div>\n\n'
            elif idx == 3:
                formatted_paragraphs += '<div class="ad-inside-post">Google AdSense In-Article Ad Space (وسط الفقرات)</div>\n\n'

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - نكسوس بريس</title>
    <meta name="robots" content="index, follow">
    <link href="https://googleapis.com" rel="stylesheet">
    <link rel="stylesheet" href="./style.css">
</head>
<body>
    <header class="main-header" style="background:#e0f2fe !important;">
        <div class="container-flex">
            <a href="index.html"><img src="image_MUwSAA.png" alt="Portal" class="main-logo-img"></a>
            <div class="ad-space-header">مساحة إعلانية مجهزة (Google AdSense 728x90)</div>
        </div>
    </header>
    <main class="main-wrapper container">
        <article class="content-area post-container">
            <span class="category-tag">{cat_name}</span>
            <h1 class="post-title">{title}</h1>
            <div class="post-meta"><span>تحرير: القسم الصحفي الدولي</span> | <span>تاريخ النشر: {current_date}</span></div>
            <div class="post-image-wrapper"><img src="{image_url}" alt="{title}" loading="eager" style="width:100%; height:auto; max-height:450px; object-fit:cover; border-radius:4px; margin:15px 0;"></div>
            
            <div class="post-body">{formatted_paragraphs}</div>
            
            <div class="ad-inside-post">Google AdSense In-Article Ad Space (أسفل المقال)</div>
            
            <div class="comments-section" style="margin-top: 50px; padding-top: 30px; border-top: 2px solid #e2e8f0;">
                <h3 style="margin-bottom: 20px; font-weight: 700; color: #071c35;">شاركونا بتتعليقاتكم وآرائكم حول الموضوع</h3>
                <div id="disqus_thread"></div>
                <script>
                    var disqus_config = function () {{
                        this.page.url = window.location.href;
                        this.page.identifier = '{filename}';
                    }};
                    (function() {{
                        var d = document, s = d.createElement('script');
                        s.src = 'https://disqus.com';
                        s.setAttribute('data-timestamp', +new Date());
                        (d.head || d.body).appendChild(s);
                    }})();
                </script>
            </div>
        </article>
        <aside class="sidebar-area">
