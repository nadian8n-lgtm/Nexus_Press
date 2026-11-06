import html
import os
from datetime import datetime

import requests


# موضوعات المقالات المنشورة تلقائياً لكل قسم.
CATEGORIES_CONFIG = {
    "ar_local": {
        "name": "أخبار وطنية",
        "keyword": "morocco,rabat,casablanca",
        "topics": [
            "الداخلية ترفع سقف اعتمادات الجماعات المحلية بالمملكة لدعم التنمية واللوجستيك",
            "عصيد ينتقد انصراف النقاشات إلى التفاصيل الهامشية بدل القضايا الأساسية والتعليم",
            "مشاريع البنية التحتية الكبرى بالمملكة تدخل مراحل التنفيذ الميداني الفعلي",
            "قرارات تشريعية جديدة لتبسيط المساطر الإدارية وتسهيل الاستثمار الوطني",
            "إشادة دولية واسعة بجهود المغرب في قطاع الطاقات المتجددة والنظيفة",
            "خطة وطنية موسعة لتحديث منظومة النقل اللوجستيكي والربط السككي بين المدن",
        ],
    },
    "ar_world": {
        "name": "الأخبار الدولية",
        "keyword": "global,politics,diplomacy",
        "topics": [
            "آخر الأخبار الدولية ومستجدات الحراك السياسي وملفات الأمن بمنطقة الشرق الأوسط",
            "آخر الأخبار الدولية والتحولات الاقتصادية والسياسية الراهنة في القارة الأوروبية",
            "آخر الأخبار الدولية والتوجهات الاستراتيجية والتجارية الجديدة في أمريكا والبيت الأبيض",
            "آخر الأخبار الدولية والفرص التنموية والاقتصادية الواعدة في القارة الإفريقية",
            "آخر الأخبار الدولية وتقاطعات الدبلوماسية وأسواق الإمداد والشحن العالمية",
            "آخر الأخبار الدولية واستشراف التوازنات الاستراتيجية المقبلة في المنطقة والعالم",
        ],
    },
    "ar_economy": {
        "name": "اقتصاد",
        "keyword": "economy,finance,oil",
        "topics": [
            "مؤشرات النمو الاقتصادي وتقلبات أسعار الطاقة والمحروقات والملاحة دولياً",
            "مستجدات أسعار المواد الاستهلاكية والتدابير الحمائية الحكومية للقدرة الشرائية للأسر",
            "تحليلات أسواق المال وأداء الأسهم والبورصات العالمية تحت المجهر هذا الأسبوع",
            "السياسات النقدية والمصرفية المرتقبة للبنوك المركزية للحد من تداعيات التضخم",
            "أزمة الشحن البحري وتأثيرها المباشر على تدفق السلع الأساسية والمواد الأولية",
            "رهانات الأمن الغذائي والاكتفاء الذاتي الزراعي في ظل تقلبات المناخ الدولية",
        ],
    },
    "ar_tech": {
        "name": "تكنولوجيا",
        "keyword": "technology,artificial-intelligence,computing",
        "topics": [
            "ثورة الذكاء الاصطناعي التوليدي تعيد صياغة مفاهيم الإنتاج البرمجي والويب العالمي",
            "الأمن السيبراني وحماية البيانات الحيوية في ظل التهديدات الرقمية وحرب الحوسبة",
            "الجيل القادم من الهواتف الذكية والأجهزة القابلة للارتداء والرقاقات الذكية لعام 2026",
            "الحوسبة الكمومية والآفاق المستقبلية الواعدة لحل المعضلات الرياضية المعقدة في ثوانٍ",
            "استراتيجيات التحول الرقمي الشامل للمؤسسات والم��اولات الناشئة والمتوسطة بالمملكة",
            "تكنولوجيا الميتافيرس والواقع الممتد في مجالات التعليم الحديث والتكوين المهني",
        ],
    },
    "ar_sports": {
        "name": "رياضة",
        "keyword": "soccer,stadium,athlete",
        "topics": [
            "متابعة الفعاليات الرياضية الوطنية وإنجازات المنتخبات والنخب في المحافل الكبرى",
            "تألق لافت لمراكز التكوين الوطنية في إبراز واحتضان المواهب الرياضية الجديدة والناشئة",
            "استعدادات مكثفة للأبطال المغاربة لخوض غمار الاستحقاقات القارية والأولمبية المقبلة",
            "الأندية الوطنية تواصل هيمنتها الصارمة على المسابقات والبطولات الإفريقية الكبرى",
            "حصاد متميز من الميداليات الذهبية في الألعاب الفردية والفنون القتالية العالمية",
            "جاهزية تامة للبنيات التحتية والملاعب الرياضية لاستضافة كبرى التظاهرات المونديالية",
        ],
    },
    "ar_arts": {
        "name": "فن وثقافة",
        "keyword": "painting,culture,library",
        "topics": [
            "الملتقيات الثقافية الدولية تبحث حماية الهوية الوطنية والتراث في العصر الرقمي",
            "تطور الفنون التشكيلية والمعارض المعاصرة وصعود المدارس البصرية في العالم العربي",
            "السينما المستقلة والإنتاجات الوثائقية المبدعة تحصد جوائز التمييز في المهرجانات",
            "صون المخطوطات التاريخية والمعالم الأثرية عبر تقنيات المسح الضوئي ثلاثي الأبعاد",
            "المهرجانات الموسيقية التراثية تعزز قيم التسامح والتبادل والتعايش الثقافي بين الشعوب",
            "أدب الرحلات والرواية العربية المعاصرة في مواجهة التحولات الرقمية المتسارعة للجيل",
        ],
    },
}

OPENAI_API_BASE = "https://api.openai.com/v1"
FALLBACK_IMAGE_URL = (
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c"
    "?auto=format&fit=crop&w=1200&q=80"
)


def call_openai_for_journalism(title, cat_name):
    """إنشاء مسودة عربية عبر OpenAI، مع بديل عند غياب المفتاح أو تعطل الخدمة."""
    api_key = os.getenv("OPENAI_API_KEY")
    fallback = (
        f"يتناول هذا التقرير موضوع {title} ضمن قسم {cat_name}. "
        "ينبغي التحقق من الوقائع والأرقام والتصريحات من مصادر موثوقة قبل النشر."
    )
    if not api_key:
        return fallback

    try:
        response = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": (
                        "اكتب مسودة تقرير صحفي تحليلي باللغة العربية الفصحى عن الموضوع التالي. "
                        "لا تختلق وقائع أو أرقاماً حديثة، ونبّه إلى ضرورة التحقق المستقل. "
                        "اكتب فقرات واضحة.\n"
                        f"القسم: {cat_name}\nالموضوع: {title}"
                    ),
                }],
                "temperature": 0.7,
            },
            timeout=50,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        print(f"تعذر توليد المقال عبر OpenAI، سيتم استخدام النص الاحتياطي: {error}")
        return fallback


def generate_ai_image(title, keywords):
    """إنشاء رابط صورة أو استخدام صورة احتياطية صالحة."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return FALLBACK_IMAGE_URL

    try:
        response = requests.post(
            f"{OPENAI_API_BASE}/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "dall-e-3",
                "prompt": (
                    "Professional realistic editorial news photography, no text or logos. "
                    f"Subject: {title}."
                ),
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "style": "natural",
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["data"][0]["url"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as error:
        print(f"تعذر توليد الصورة، سيتم استخدام صورة احتياطية: {error}")
        return FALLBACK_IMAGE_URL


def generate_article_html(title, cat_name, category_key, filename, keywords):
    article_text = call_openai_for_journalism(title, cat_name)
    image_url = generate_ai_image(title, keywords)
    current_date = datetime.now().strftime("%d/%m/%Y")

    safe_title = html.escape(title)
    safe_category = html.escape(cat_name)
    safe_filename = html.escape(filename, quote=True)
    safe_image_url = html.escape(image_url, quote=True)

    paragraphs = [line.strip() for line in article_text.splitlines() if line.strip()]
    formatted_paragraphs = []
    for index, paragraph in enumerate(paragraphs):
        formatted_paragraphs.append(f'<p class="post-p">{html.escape(paragraph)}</p>')
        if index in (1, 3):
            formatted_paragraphs.append(
                '<div class="ad-inside-post">مساحة إعلانية داخل المقال</div>'
            )

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title} - نكسوس بريس</title>
    <meta name="robots" content="index, follow">
    <link rel="stylesheet" href="./style.css">
</head>
<body>
    <header class="main-header">
        <div class="container-flex">
            <a href="index.html"><img src="image_MUwSAA.png" alt="نكسوس بريس" class="main-logo-img"></a>
        </div>
    </header>
    <main class="main-wrapper container">
        <article class="content-area post-container">
            <span class="category-tag">{safe_category}</span>
            <h1 class="post-title">{safe_title}</h1>
            <div class="post-meta"><span>تحرير: القسم الصحفي</span> | <span>تاريخ النشر: {current_date}</span></div>
            <div class="post-image-wrapper">
                <img src="{safe_image_url}" alt="{safe_title}" loading="eager" style="width:100%;height:auto;max-height:450px;object-fit:cover;border-radius:4px;margin:15px 0;">
            </div>
            <div class="post-body">
                {''.join(formatted_paragraphs)}
            </div>
            <div class="ad-inside-post">مساحة إعلانية أسفل المقال</div>
            <section class="comments-section" style="margin-top:50px;padding-top:30px;border-top:2px solid #e2e8f0;">
                <h3>شاركونا تعليقاتكم وآراءكم حول الموضوع</h3>
                <div id="disqus_thread" data-article="{safe_filename}"></div>
            </section>
        </article>
        <aside class="sidebar-area"></aside>
    </main>
</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as output_file:
        output_file.write(html_content)
    print(f"تم إنشاء المقال: {filename}")


def main():
    for category_key, category in CATEGORIES_CONFIG.items():
        for index, title in enumerate(category["topics"], start=1):
            generate_article_html(
                title=title,
                cat_name=category["name"],
                category_key=category_key,
                filename=f"{category_key}_{index}.html",
                keywords=category["keyword"],
            )


if __name__ == "__main__":
    main()
