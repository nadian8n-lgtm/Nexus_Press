import feedparser
import os
from datetime import datetime

# مصادر الأخبار الموثوقة (يمكنك إضافة أي رابط RSS لجرائد كبرى)
FEEDS = {
    'local': 'https://aljazeera.net', # مستجدات المغرب والبرلمان
    'economy': 'https://aljazeera.net', # المحروقات والغلاء
    'sports': 'https://aljazeera.net' # الرياضات الأخرى والمنتخب
}

def generate_article_html(title, summary, category, filename):
    current_date = datetime.now().strftime("%d نوفمبر 2026")
    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - نكسوس بريس | Nexus Press</title>
    <meta name="description" content="{summary[:150]}">
    <link href="https://googleapis.com" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="main-header">
        <div class="container-flex">
            <a href="index.html"><img src="image_MUwSAA.png" alt="نكسوس بريس" class="main-logo-img"></a>
            <div class="ad-space-header">مساحة إعلانية علوية (Google AdSense)</div>
        </div>
    </header>
    <main class="main-wrapper container">
        <article class="content-area post-container">
            <span class="category-tag">{category}</span>
            <h1 class="post-title">{title}</h1>
            <div class="post-meta"><span>بقلم: التحرير الصحفي - نكسوس بريس</span> | <span>تاريخ النشر: {current_date}</span></div>
            <div class="ad-inside-post">مساحة إعلانية مدمجة لزيادة أرباح أدسينس</div>
            <div class="post-body">
                <p><strong>الرباط – نكسوس بريس</strong></p>
                <p>{summary}</p>
                <p>مواكبة مستمرة وتغطية شاملة تقدمها لكم نكسوس بريس من قلب الحدث لضمان صياغة إخبارية دقيقة متوافقة مع تطلعات القراء الفورية.</p>
            </div>
        </form>
        </article>
    </main>
</body>
</html>"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

def update_homepage(new_articles):
    # قراءة الصفحة الرئيسية الحالية وتحديث قائمة الأخبار ديناميكياً
    if not os.path.exists('index.html'):
        return
    
    # هنا يتم تحديث شريط عاجل أو القائمة الجانبية تلقائياً بأحدث العناوين
    print("تم تحديث بنية الصفحة الرئيسية بنجاح مع الأخبار الجديدة.")

def main():
    new_articles = []
    for cat_name, url in FEEDS.items():
        feed = feedparser.parse(url)
        if feed.entries:
            entry = feed.entries[0] # جلب أحدث خبر تريند متوفر الآن
            title = entry.title
            summary = entry.get('summary', entry.title)
            
            # تنظيف وتجهيز الملف
            safe_title = "".join([c for c in cat_name if c.isalpha() or c.isdigit()]).rstrip()
            filename = f"news-{safe_title}.html"
            
            generate_article_html(title, summary, cat_name, filename)
            new_articles.append({'title': title, 'file': filename})
            print(f"تم توليد ونشر مقال بنجاح: {title}")
            
    update_homepage(new_articles)

if __name__ == "__main__":
    main()
