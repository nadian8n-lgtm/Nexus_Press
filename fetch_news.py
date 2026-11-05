import feedparser
import os
from datetime import datetime

# مصادر الأخبار الرسمية الموثوقة بعد إضافة هسبريس للأخبار الوطنية
FEEDS = {
    # الأخبار العربية الوطنية والدولية
    'ar_local': {'url': 'https://www.hespress.com/feed', 'lang': 'ar', 'dir': 'rtl', 'cat': 'أخبار وطنية'}, # هسبريس الرسمية
    'ar_world': {'url': 'https://aljazeera.net', 'lang': 'ar', 'dir': 'rtl', 'cat': 'سياسة دولية'},
    'ar_economy': {'url': 'https://aljazeera.net', 'lang': 'ar', 'dir': 'rtl', 'cat': 'اقتصاد'},
    'ar_sports': {'url': 'https://aljazeera.net', 'lang': 'ar', 'dir': 'rtl', 'cat': 'رياضة'},
    
    # الأخبار الإنجليزية
    'en_world': {'url': 'https://bbci.co.uk', 'lang': 'en', 'dir': 'ltr', 'cat': 'World News'},
    
    # الأخبار الفرنسية
    'fr_world': {'url': 'https://france24.com', 'lang': 'fr', 'dir': 'ltr', 'cat': 'Actualités Internationales'}
}

def generate_article_html(title, summary, category, lang, direction, filename):
    current_date = datetime.now().strftime("%d/%m/2026")
    brand_text = "نكسوس بريس | Nexus Press"
    
    # تخصيص لغة المحتوى الصحفي لتبدو بشرية 100% وقانونية
    meta_text = "تحرير: الطاقم الصحفي" if lang == 'ar' else "By: Editorial Staff" if lang == 'en' else "Par: L'équipe éditoriale"
    update_text = "الرباط – متابعة حصرية لـ نكسوس بريس" if lang == 'ar' else "Rabat – Exclusive Coverage" if lang == 'en' else "Rabat – Couverture Exclusive"
    
    # فقرات إضافية ذكية تصيغ الأبعاد لكسر التكرار وحماية الفكرية
    closing_text = "وفي سياق متصل، تشير القراءات الميدانية الراهنة إلى أن هذه المستجدات ستلقي بظلالها على التوازنات الإقليمية، مما يتطلب متابعة دقيقة ومستمرة للملفات المطروحة." if lang == 'ar' else "In connection with these events, analysts predict significant shifts in the coming days." if lang == 'en' else "En relation avec ces développements, les observateurs prévoient des impacts à court terme."
    
    html_content = f"""<!DOCTYPE html>
<html lang="{lang}" dir="{direction}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {brand_text}</title>
    <meta name="description" content="{summary[:150]}">
    <meta name="robots" content="index, follow">
    <link rel="preconnect" href="https://googleapis.com">
    <link rel="preconnect" href="https://gstatic.com" crossorigin>
    <link href="https://googleapis.com/css2?family=Cairo:wght@400;700;900&family=Roboto:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
    <style>
        body {{ font-family: { "'Cairo', sans-serif" if lang == 'ar' else "'Roboto', sans-serif" }; }}
    </style>
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
            <div class="post-meta"><span>{meta_text}</span> | <span>{current_date}</span></div>
            <div class="ad-inside-post">Google AdSense In-Article</div>
            <div class="post-body">
                <p><strong>{update_text}</strong></p>
                <p>{summary}</p>
                <p>{closing_text}</p>
            </div>
        </article>
    </main>
</body>
</html>"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    new_articles = []
    for key, info in FEEDS.items():
        feed = feedparser.parse(info['url'])
        if feed.entries:
            entry = feed.entries[0]
            title = entry.title
            summary = entry.get('summary', entry.title)
            
            filename = f"news-{key}.html"
            generate_article_html(title, summary, info['cat'], info['lang'], info['dir'], filename)
            new_articles.append({'title': title, 'file': filename, 'lang': info['lang']})
            print(f"[{info['lang'].upper()}] تم صياغة مقال بنجاح من المصدر الموثوق: {title}")

if __name__ == "__main__":
    main()
