import feedparser
import os
from datetime import datetime

# مصادر الأخبار الرسمية الموثوقة لتغذية موقع نكسوس بريس بالكامل
FEEDS = {
    'ar_local': {'url': 'https://hespress.com', 'cat': 'أخبار وطنية', 'topic': 'الشأن المحلي والبرلمان المغربي ومستجدات أسعار المواد الأساسية والمعيشية والمحروقات بالمملكة'},
    'ar_world': {'url': 'https://aljazeera.net', 'cat': 'سياسة دولية', 'topic': 'العلاقات الدبلوماسية والتحركات السياسية الراهنة والتوترات الجيوسياسية في المنطقة والعالم'},
    'ar_economy': {'url': 'https://aljazeera.net', 'cat': 'اقتصاد', 'topic': 'أسواق المال العالمية، أسعار الطاقة والمحروقات، ومعدلات التضخم وتأثيرها المباشر على القدرة الشرائية'},
    'ar_sports': {'url': 'https://aljazeera.net', 'cat': 'رياضة', 'topic': 'المنتخبات الوطنية المغربية والبطولات العالمية في مختلف الرياضات الفردية والجماعية خارج كرة القدم'}
}

IMAGES_POOL = {
    'أخبار وطنية': 'https://unsplash.com',
    'سياسة دولية': 'https://unsplash.com',
    'اقتصاد': 'https://unsplash.com',
    'رياضة': 'https://unsplash.com'
}

def generate_deep_journalistic_content(title, summary, topic):
    """ تمديد وتوسيع محتوى الخبر تلقائياً ليتراوح بين 800 إلى 1500 كلمة لضمان جودة السيو """
    paragraphs = [
        f"<strong>الرباط – تغطية خاصة وحصرية لـ نكسوس بريس |</strong> تشهد الساحة الراهنة حراكاً متسارعاً وتطورات لافتة ترتبط ارتباطاً وثيقاً بـ {topic}، حيث أثارت المستجدات الأخيرة اهتماماً واسعاً على الصعيدين الشعبي والمؤسساتي، نظراً لأبعادها الاستراتيجية وتأثيراتها المباشرة على المعيش اليومي والمنظومة العامة الموجهة للقطاع.",
        f"وفي تفاصيل هذا المشهد، يتضح أن الخلفيات المحيطة بالقضية تعود إلى تراكمات سابقة وملفات لطالما شكلت محور نقاش ساخن بين مختلف الفاعلين. إن العنوان الأبرز اليوم المتجلي في '{title}' يضعنا أمام قراءة موضوعية تستلزم تفكيك المعطيات الميدانية والوقوف على الإحصائيات الرسمية الصادرة عن الجهات الوصية تماشياً مع المتغيرات الاقتصادية والسياسية التي تعيشها المملكة وباقي دول العالم.",
        f"ويرى خبراء ومحللون في تصريحات متفرقة تتابعها 'نكسوس بريس' أن التدابير المتخذة حتى الآن تظل في حاجة إلى تعزيز بآليات رقابية أكثر مرونة، خصوصاً فيما يتعلق بالملفات الحارقة كالمحروقات والغلاء وتقلبات الأسواق الدولية، والتي تلقي بظلالها مباشرة على القوة الشرائية للمواطنين، وتفرض على المؤسسة التشريعية والبرلمان المغربي فتح قنوات حوار جادة لبلورة حلول مستدامة قادرة على الصمود أمام الأزمات الجيوسياسية المتلاحقة.",
        f"وعلى صعيد متصل، تبرز الأرقام الواردة في التقارير الأخيرة حاجة القطاعات الحيوية إلى استراتيجيات تجديدية تعتمد على التكنولوجيا والتحول الرقمي الشامل، وهو ما يعكس الطموح الوطني بجعل المنظومة المحلية قطباً رائداً يتجاوز التحديات التقليدية. هذا التوجه النخبوي يستدعي بالضرورة تكثيف الاستثمارات الوطنية وتأهيل العنصر البشري ليكون قادراً على مواكبة هذه الطفرة بكفاءة ومهنية عالية تضمن تكافؤ الفرص والعدالة الاجتماعية المرجوة.",
        f"أما في الجانب المرتبط بالتأثيرات الدولية، فإن التقاطعات الاقتصادية والسياسية بين المغرب ومحيطه الإقليمي تفرض نوعاً من اليقظة الدبلوماسية والاقتصادية. إن التقلبات المستمرة في أسعار الطاقة والشحن الدولي لا تقتصر تبعاتها على دولة دون أخرى، بل تمتد لتشكل سلاسل ضغط متصلة تؤثر على سلاسل الإمداد العالمية، مما يجعل إصلاح القطاعات الداخلية صمام أمان حقيقي لمواجهة أي هزات خارجية غير متوقعة في المستقبل القريب.",
        f"وفي ختام هذا التحليل الإخباري المعمق، يتبين أن المرحلة الراهنة تتطلب تظافر جهود جميع المكونات، من حكومة ومعارضة ومجتمع مدني، لصياغة رؤية وطنية موحدة تتوافق مع التحديات وتستشرف الفرص الواعدة. وستظل 'نكسوس بريس' مواكبة لكافة المستجدات والتطورات أولاً بأول، لتضع القارئ في قلب الحدث بصياغة بشرية مهنية رصينة تحترم دقة المعلومة وتبتعد عن النقل الأعمى، حماية للملكية الفكرية وتعزيزاً للصحافة الرقمية المستقلة."
    ]
    
    content_html = ""
    for p in paragraphs:
        content_html += f"<p>{p}</p>\n<p>وفي إطار التدقيق الميداني الذي يقوده الطاقم التحريري لنكسوس بريس، تشير القراءات إلى أن التوازن بين العرض والطلب في هذا القطاع الحيوي يستلزم مراجعة شاملة للاتفاقيات والقوانين المؤطرة بما يخدم الصالح العام ويضمن استقرار المؤشرات التنموية على المدى الطويل.</p>\n"
    return content_html

def generate_article_html(title, summary, category, filename):
    current_date = datetime.now().strftime("%d/%m/2026")
    image_url = IMAGES_POOL.get(category, 'https://unsplash.com')
    long_content = generate_deep_journalistic_content(title, summary, category)
    
    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - نكسوس بريس | Nexus Press</title>
    <meta name="description" content="{summary[:150]}">
    <meta name="robots" content="index, follow">
    <link href="https://googleapis.com" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="main-header">
        <div class="container-flex">
            <a href="index.html"><img src="image_MUwSAA.png" alt="Nexus Press" class="main-logo-img"></a>
            <div class="ad-space-header">Google AdSense Space</div>
        </div>
    </header>
    <main class="main-wrapper container">
        <article class="content-area post-container">
            <span class="category-tag">{category}</span>
            <h1 class="post-title">{title}</h1>
            <div class="post-meta"><span>تحرير: الطاقم الصحفي - نكسوس بريس</span> | <span>تاريخ النشر: {current_date}</span></div>
            <div class="post-image-wrapper"><img src="{image_url}" alt="{title}" loading="eager"></div>
            <div class="ad-inside-post">Google AdSense In-Article</div>
            <div class="post-body">{long_content}</div>
        </article>
    </main>
    <script type="text/javascript">
        function googleTranslateElementInit() {{
            new google.translate.TranslateElement({{pageLanguage: 'ar', includedLanguages: 'ar,en,fr', layout: google.translate.TranslateElement.InlineLayout.SIMPLE}}, 'google_translate_element');
        }}
    </script>
    <script type="text/javascript" src="//://google.com"></script>
</body>
</html>"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    new_articles = []
    for key, info in FEEDS.items():
        feed = feedparser.parse(info['url'])
        if feed.entries:
            for i in range(min(1, len(feed.entries))):
                entry = feed.entries[i]
                title = entry.title
                summary = entry.get('summary', entry.title)
                filename = f"news-{key}-{i}.html"
                generate_article_html(title, summary, info['cat'], filename)
                print(f"[تم توليد مقال طويل بنجاح بقسم {info['cat']}]: {title}")

if __name__ == "__main__":
    main()
