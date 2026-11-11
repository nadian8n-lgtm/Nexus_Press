"""The learning section ("أكاديمية الذكاء الاصطناعي"): free Python-for-AI and Generative-AI courses + a learning assistant.
Links come from the open lists https://github.com/CelaDaniel/free-ai-resources-x (MIT) and https://github.com/12britz/awesome-free-models (CC0);
descriptions below are written for Nexus Press. The page style is inline so style.css does not need to change."""
import html

e = html.escape

TITLE = "أكاديمية الذكاء الاصطناعي | نكسوس بريس"
DESC = "كورسات مجانية لتعلّم بايثون للذكاء الاصطناعي والذكاء الاصطناعي التوليدي، مرتبة من الصفر، مع مساعد تعليمي."

# (title, url, description, level, note)
PYTHON = [
    ("الدليل الرسمي لبايثون", "https://docs.python.org/3/tutorial/", "البداية الأوثق: شرح رسمي متدرج للغة من موقعها الأصلي.", "مبتدئ", ""),
    ("دورة Google لبايثون", "https://developers.google.com/edu/python", "دروس وتمارين عملية من Google لتعلّم أساسيات اللغة بسرعة.", "مبتدئ", ""),
    ("مسار Microsoft لمبتدئي بايثون", "https://learn.microsoft.com/en-us/training/paths/beginner-python/", "مسار تعليمي مجاني مقسّم إلى وحدات قصيرة مع تطبيقات.", "مبتدئ", ""),
    ("دورة Kaggle لبايثون", "https://www.kaggle.com/learn/python", "دروس قصيرة تُنفَّذ داخل المتصفح مباشرة بدون تثبيت أي برنامج.", "مبتدئ", ""),
    ("Automate the Boring Stuff", "https://automatetheboringstuff.com/", "كتاب مجاني يعلّمك بايثون بمشاريع يومية مفيدة.", "مبتدئ", ""),
    ("Think Python", "https://greenteapress.com/thinkpython2/", "كتاب مجاني يعلّمك طريقة التفكير البرمجي عبر بايثون.", "مبتدئ", ""),
    ("NumPy", "https://numpy.org/learn/", "مكتبة الحسابات الرقمية، الأساس الذي تقوم عليه أدوات الذكاء الاصطناعي.", "مبتدئ", ""),
    ("Pandas", "https://pandas.pydata.org/docs/getting_started/index.html", "تعلّم تنظيف البيانات وتحليلها بالمكتبة الأشهر في هذا المجال.", "مبتدئ", ""),
    ("Python Data Science Handbook", "https://jakevdp.github.io/PythonDataScienceHandbook/", "كتاب مجاني يغطي حزمة علم البيانات كاملة بأمثلة تطبيقية.", "متوسط", ""),
    ("Google Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course", "الخطوة التالية بعد بايثون: أساسيات تعلّم الآلة بتمارين وفيديوهات.", "متوسط", ""),
]
GENAI = [
    ("Generative AI for Beginners (Microsoft)", "https://github.com/microsoft/generative-ai-for-beginners", "دورة من 18 درسًا لبناء تطبيقات الذكاء الاصطناعي التوليدي مع شيفرات جاهزة.", "مبتدئ", ""),
    ("Generative AI for Everyone", "https://www.coursera.org/learn/generative-ai-for-everyone", "دورة أندرو نغ لفهم ما يستطيعه الذكاء الاصطناعي التوليدي وما لا يستطيعه.", "مبتدئ", "على Coursera: خيار المتابعة المجانية قد يختلف، وقد تكون الشهادة مدفوعة."),
    ("مسار Google Cloud للذكاء الاصطناعي التوليدي", "https://www.cloudskillsboost.google/paths/118", "مسار تعليمي من Google يمر بالمفاهيم ثم الأدوات.", "مبتدئ", "قد يتطلب إنشاء حساب."),
    ("Learn Prompting", "https://learnprompting.org/", "دليل مفتوح لكتابة الأوامر (Prompts) بطريقة تعطي نتائج أفضل.", "مبتدئ", ""),
    ("The Illustrated GPT-2", "https://jalammar.github.io/illustrated-gpt2/", "شرح مصوّر بديع لكيفية عمل نماذج GPT من الداخل.", "مبتدئ", "بالإنجليزية."),
    ("Hugging Face: دورة NLP", "https://huggingface.co/learn/nlp-course/chapter1/1", "دورة عملية لمعالجة اللغة والنماذج اللغوية باستخدام مكتبة Transformers.", "متوسط", "بالإنجليزية."),
    ("Hugging Face: دورة Diffusion", "https://huggingface.co/learn/diffusion-course/unit0/1", "كيف تعمل نماذج توليد الصور وكيف تبني نموذجًا بنفسك.", "متوسط", "بالإنجليزية."),
    ("Stanford CS25: Transformers United", "https://web.stanford.edu/class/cs25/", "محاضرات جامعية في آخر أبحاث نماذج Transformer وتطبيقاتها.", "متوسط", "بالإنجليزية."),
    ("Ollama", "https://ollama.com/", "شغّل نماذج مفتوحة المصدر على حاسوبك بخطوات بسيطة وللتجربة.", "كل المستويات", "بالإنجليزية."),
]
MORE = [
    ("free-ai-resources-x", "https://github.com/CelaDaniel/free-ai-resources-x", "أكثر من 400 مورد مجاني في 30 تخصصًا، مرتبة حسب المستوى."),
    ("awesome-free-models", "https://github.com/12britz/awesome-free-models", "قائمة منسّقة لنماذج وأدوات الذكاء الاصطناعي المجانية ومفتوحة المصدر."),
]

CSS = """<style>
.ai-hero{background:linear-gradient(135deg,#0b3c7a,#0369a1);color:#fff;border-radius:14px;padding:22px 24px;margin-bottom:18px}
.ai-hero h1{color:#fff;margin:0 0 6px;font-size:26px}.ai-hero p{margin:0;opacity:.95;font-size:16px}
.ai-path{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 6px}.ai-path span{background:var(--soft);border:1px solid var(--line);border-radius:20px;padding:4px 14px;font-weight:700;font-size:14px}
.ai-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin:10px 0 6px}
.ai-card{display:flex;flex-direction:column;gap:6px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;transition:var(--tr)}
.ai-card:hover{border-color:var(--sky);transform:translateY(-3px)}.ai-card b{color:var(--ink);line-height:1.5}.ai-card p{margin:0;font-size:14.5px;line-height:1.8;color:var(--text)}
.ai-card small{color:var(--muted);font-size:12px}.ai-card .go{margin-top:auto;font-weight:800;color:var(--accent);font-size:14px}
.ai-lvl{align-self:flex-start;background:var(--badge-bg);color:var(--badge-fg);border-radius:20px;padding:0 10px;font-size:12px;font-weight:800}
.ai-chat{background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:18px;margin:22px 0}
.ai-msgs{max-height:340px;overflow:auto;display:flex;flex-direction:column;gap:8px;margin:10px 0}
.ai-m{padding:9px 13px;border-radius:12px;max-width:92%;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-size:15px}
.ai-m.u{align-self:flex-start;background:var(--navy);color:#fff}.ai-m.b{align-self:flex-end;background:var(--card);border:1px solid var(--line)}
.ai-form{display:flex;gap:8px}.ai-form textarea{resize:none}.ai-credit{font-size:13px;color:var(--muted);margin-top:18px}
@media(max-width:600px){.ai-form{flex-direction:column}.ai-hero h1{font-size:21px}}
</style>"""


def _cards(rows):
    out = []
    for t, u, d, lvl, note in rows:
        n = f"<small>{e(note)}</small>" if note else ""
        out.append(f'<a class="ai-card" href="{e(u)}" target="_blank" rel="noopener noreferrer"><span class="ai-lvl">{e(lvl)}</span>'
                   f'<b dir="auto">{e(t)}</b><p>{e(d)}</p>{n}<span class="go">افتح الدورة ←</span></a>')
    return '<div class="ai-grid">' + "".join(out) + "</div>"


def body(chat_src="chat.js"):
    more = "".join(f'<a class="ai-card" href="{e(u)}" target="_blank" rel="noopener noreferrer"><b dir="ltr">{e(t)}</b><p>{e(d)}</p><span class="go">افتح القائمة ←</span></a>'
                   for t, u, d in MORE)
    return f"""{CSS}
<div class="page ai-page"><div class="ai-hero"><h1>🎓 أكاديمية الذكاء الاصطناعي</h1>
<p>كورسات مجانية مختارة لتتعلّم بايثون ثم الذكاء الاصطناعي التوليدي، مرتبة من الصفر وبدون تكلفة.</p></div>
<p>لا تحتاج إلى خبرة سابقة. اتبع هذا الترتيب وستصل خطوة بخطوة:</p>
<div class="ai-path"><span>1) أساسيات بايثون</span><span>2) مكتبات البيانات</span><span>3) تعلّم الآلة</span><span>4) الذكاء الاصطناعي التوليدي</span></div>
<p>خصّص 30 إلى 45 دقيقة يوميًا، ونفّذ كل درس بنفسك على الحاسوب بدل المشاهدة فقط. وتذكّر أن بعض الدورات بالإنجليزية، ومتصفحك يستطيع ترجمة صفحاتها.</p>
<h2>🐍 Python for AI: بايثون للذكاء الاصطناعي</h2>{_cards(PYTHON)}
<h2>✨ Generative AI: الذكاء الاصطناعي التوليدي</h2>{_cards(GENAI)}
<h2>📚 المزيد من الموارد المجانية</h2><div class="ai-grid">{more}</div>
<section class="ai-chat" id="ai-chat" data-puter-model=""><h2 style="margin:0">💬 مساعد التعلّم</h2>
<p class="muted">اسأل عن أي درس أو مفهوم في بايثون أو الذكاء الاصطناعي. يعمل المساعد عبر خدمة Puter، وقد يطلب منك تسجيل الدخول بحساب Puter المجاني عند أول رسالة. إجاباته للتعلّم فقط وقد تحتوي أخطاء، فتحقق منها.</p>
<div class="ai-msgs" id="ai-msgs" aria-live="polite"></div>
<form class="ai-form" id="ai-form"><textarea id="ai-input" rows="2" maxlength="800" placeholder="اكتب سؤالك هنا…" aria-label="سؤالك"></textarea>
<button class="btn" type="submit">إرسال</button></form><p class="form-msg" id="ai-note" role="status"></p></section>
<p class="ai-credit">اختيار الروابط مبني على القوائم المفتوحة: free-ai-resources-x (رخصة MIT) وawesome-free-models (CC0). الدورات تعود لأصحابها، وقد تتغير شروط الوصول المجاني من وقت لآخر.</p></div>
<script src="{e(chat_src)}" defer></script>"""
