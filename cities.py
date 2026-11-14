"""قسم «أخبار المدن»: لائحة المدن المغربية + بناء روابط Google News لكل مدينة.

المنهج:
  1) Google News RSS (hl=ar&gl=MA) هو مصدر الاكتشاف: يجلب ما تتداوله الصحف الوطنية عن المدينة.
  2) نقرأ أيضاً خلاصات الصحف الوطنية مباشرةً (NATIONAL_FEEDS أدناه) للحصول على نص كافٍ
     لكتابة مقال أصلي بدل الاعتماد على عنوان فقط.
  3) كل مقال يذكر مصدره باسم الصحيفة ورابطها (انظر build_site.py).
"""
import re
import urllib.parse
from datetime import datetime, timezone

# (الاسم العربي، slug للملفات، الجهة)
CITIES = [
    ("الرباط", "rabat", "الرباط-سلا-القنيطرة"),
    ("الدار البيضاء", "casablanca", "الدار البيضاء-سطات"),
    ("مراكش", "marrakech", "مراكش-آسفي"),
    ("فاس", "fes", "فاس-مكناس"),
    ("طنجة", "tanger", "طنجة-تطوان-الحسيمة"),
    ("أكادير", "agadir", "سوس-ماسة"),
    ("مكناس", "meknes", "فاس-مكناس"),
    ("وجدة", "oujda", "الشرق"),
    ("تطوان", "tetouan", "طنجة-تطوان-الحسيمة"),
    ("القنيطرة", "kenitra", "الرباط-سلا-القنيطرة"),
    ("سلا", "sale", "الرباط-سلا-القنيطرة"),
    ("آسفي", "safi", "مراكش-آسفي"),
    ("الجديدة", "eljadida", "الدار البيضاء-سطات"),
    ("بني ملال", "benimellal", "بني ملال-خنيفرة"),
    ("خريبكة", "khouribga", "بني ملال-خنيفرة"),
    ("الناظور", "nador", "الشرق"),
    ("الحسيمة", "alhoceima", "طنجة-تطوان-الحسيمة"),
    ("العيون", "laayoune", "العيون-الساقية الحمراء"),
    ("الداخلة", "dakhla", "الداخلة-وادي الذهب"),
    ("ورزازات", "ouarzazate", "درعة-تافيلالت"),
    ("الصويرة", "essaouira", "مراكش-آسفي"),
    ("تارودانت", "taroudant", "سوس-ماسة"),
    ("سطات", "settat", "الدار البيضاء-سطات"),
    ("برشيد", "berrechid", "الدار البيضاء-سطات"),
    ("المحمدية", "mohammedia", "الدار البيضاء-سطات"),
    ("الخميسات", "khemisset", "الرباط-سلا-القنيطرة"),
    ("خنيفرة", "khenifra", "بني ملال-خنيفرة"),
    ("الرشيدية", "errachidia", "درعة-تافيلالت"),
    ("ميدلت", "midelt", "درعة-تافيلالت"),
    ("أزرو", "azrou", "فاس-مكناس"),
    ("إفران", "ifrane", "فاس-مكناس"),
    ("شفشاون", "chefchaouen", "طنجة-تطوان-الحسيمة"),
    ("العرائش", "larache", "طنجة-تطوان-الحسيمة"),
    ("سيدي سليمان", "sidi-slimane", "الرباط-سلا-القنيطرة"),
    ("سيدي قاسم", "sidi-kacem", "الرباط-سلا-القنيطرة"),
    ("تمارة", "temara", "الرباط-سلا-القنيطرة"),
    ("بنجرير", "benguerir", "مراكش-آسفي"),
    ("اليوسفية", "youssoufia", "مراكش-آسفي"),
    ("سيدي بنور", "sidi-bennour", "الدار البيضاء-سطات"),
    ("تيزنيت", "tiznit", "سوس-ماسة"),
    ("كلميم", "guelmim", "كلميم-واد نون"),
    ("طانطان", "tan-tan", "كلميم-واد نون"),
    ("السمارة", "smara", "العيون-الساقية الحمراء"),
    ("بوجدور", "boujdour", "العيون-الساقية الحمراء"),
    ("جرسيف", "guercif", "الشرق"),
    ("تاوريرت", "taourirt", "الشرق"),
    ("بركان", "berkane", "الشرق"),
    ("الفنيدق", "fnideq", "طنجة-تطوان-الحسيمة"),
    ("المضيق", "mdiq", "طنجة-تطوان-الحسيمة"),
    ("أصيلة", "asilah", "طنجة-تطوان-الحسيمة"),
    ("زاكورة", "zagora", "درعة-تافيلالت"),
    ("تنغير", "tinghir", "درعة-تافيلالت"),
    ("فكيك", "figuig", "الشرق"),
    ("جرادة", "jerada", "الشرق"),
    ("سيدي إفني", "sidi-ifni", "كلميم-واد نون"),
]

BY_SLUG = {slug: (name, slug, region) for name, slug, region in CITIES}
BY_NAME = {name: (name, slug, region) for name, slug, region in CITIES}

# كلمات الحوادث والأمن والقضاء (تُستخدم في استعلام Google News وفي مطابقة خلاصات الصحف).
# الكلمات القوية أولاً؛ «أمن/أمني» وحدها لا تكفي لأنها تظهر في أخبار دبلوماسية لا علاقة لها بالحوادث.
CRIME_WORDS = (
    "جريمة", "حادث", "حادثة", "اعتقال", "توقيف", "درك", "شرطة", "محكمة", "قضية", "تحقيق",
    "سرقة", "قتل", "اعتداء", "مخدرات", "تهريب", "احتيال", "نصب", "حريق", "جثة", "نيابة",
    "سجن", "اختطاف", "اغتصاب", "عنف", "تهديد", "رشوة", "فساد", "تبديد", "استغلال", "ابتزاز",
    "تحرش", "سطو", "جرح", "إصابة", "وفاة", "غرق", "انفجار", "أمن", "أمني",
)
WEAK_CRIME = ("أمن", "أمني")

# صحف وطنية تُقرأ مباشرةً للحصول على نص المقال (تُذكر كمصادر). كل الروابط أدناه مُختبَرة وتعيد RSS صالحاً.
# بقية المنابر تُغطّى عبر Google News (city_urls)، فلا حاجة لإضافة روابط معطوبة.
NATIONAL_FEEDS = [
    ("هسبريس", "https://www.hespress.com/feed"),
    ("اليوم 24", "https://alyaoum24.com/feed"),
    ("برلمان.كوم", "https://barlamane.com/feed/"),
    ("rue20", "https://rue20.com/feed"),
    ("kech24", "https://kech24.com/feed"),
    ("lesiteinfo", "https://www.lesiteinfo.com/feed"),
    ("شالنج", "https://www.challenge.ma/feed"),
    ("الصحيفة", "https://www.assahifa.com/feed"),
    ("LesEco", "https://www.leseco.ma/feed"),
    ("La Vie Éco", "https://www.lavieeco.com/feed"),
]

GN = "https://news.google.com/rss/search?q="


def news_url(query):
    """رابط Google News RSS لاستعلام عربي، موجّه للمغرب."""
    return GN + urllib.parse.quote(query) + "&hl=ar&gl=MA&ceid=MA:ar"


def city_urls(name):
    """استعلامان: واحد مركّز على الحوادث، وآخر عام عن المدينة."""
    crime = ('"' + name + '" (' + " OR ".join(CRIME_WORDS[:18]) + ")")
    general = '"' + name + '" المغرب'
    return [news_url(crime), news_url(general)]


def all_urls():
    """خلاصة عامة لأخبار المدن (حوادث وقضايا في المغرب)."""
    q = "المغرب (جريمة OR حادث OR اعتقال OR أمن OR محكمة OR قضية OR تحقيق OR سرقة OR اعتداء OR مخدرات OR حريق)"
    return [news_url(q)]


def norm(text):
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", str(text or "").lower())
    t = re.sub("[أإآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[^\w\s]", " ", t)


def is_crime(text):
    """A story is a city story only when it contains a STRONG crime/accident/court word.
    «أمن/أمني» alone is not enough (it also appears in diplomacy and official-communication news)."""
    t = norm(text)
    return any(w in t for w in (norm(x) for x in CRIME_WORDS if x not in WEAK_CRIME))


def mentions(text, name):
    """Whole-word match, so «فاس» never matches «فاسدة» and «سلا» never matches «سلام»."""
    return f" {norm(name)} " in f" {norm(text)} "


def choose_city(arts):
    """المدينة الأقل تغطيةً اليوم، مع دوران يومي ثابت حتى لا تتكرر مدينة واحدة."""
    have = {}
    for a in arts.get("ar_cities", []):
        c = a.get("city")
        if c:
            have[c] = have.get(c, 0) + 1
    day = datetime.now(timezone.utc).timetuple().tm_yday
    start = day % len(CITIES)
    order = CITIES[start:] + CITIES[:start]
    return min(enumerate(order), key=lambda t: (have.get(t[1][0], 0), t[0]))[1]


def slug(name):
    return BY_NAME.get(name, (name, "", ""))[1]


def region(name):
    return BY_NAME.get(name, (name, "", ""))[2]
