"""Keeps the article archive clean:
 1) removes duplicated / near-duplicated articles (same title, near-identical title, or heavily overlapping text),
 2) puts every article in the section it belongs to (LLM classification when a text provider exists, keyword scoring otherwise).
Every article is classified only once (flag cat_ok) so no tokens are wasted on later runs."""
import json
import re

POLITICS = ("حرب", "رئيس", "حكومة", "انتخابات", "قصف", "وزير", "جيش", "سلام", "هدنة", "برلمان", "عقوبات", "اتفاق", "قمة", "أمن", "لجوء",
            "احتجاجات", "مفاوضات", "سفير", "دبلوماسي", "حزب", "تصويت", "نزاع", "غزة", "أوكرانيا", "ترامب", "الأمم المتحدة", "حدود", "عسكري")
HINTS = {
    "ar_sports": ("كرة", "مباراة", "الدوري", "لاعب", "منتخب", "بطولة", "كأس", "هدف", "فريق", "تنس", "ملعب", "رياضة", "أولمبي", "مدرب", "تصفيات",
                  "نهائي", "بطل", "سباق", "سلة", "ميدالية"),
    "ar_economy": ("اقتصاد", "أسعار", "بورصة", "أسهم", "تضخم", "بنك", "ميزانية", "استثمار", "شركة", "نفط", "تجارة", "ضرائب", "عملة", "دولار",
                   "أرباح", "سوق", "صادرات", "واردات", "فائدة", "ديون", "نمو", "أجور", "رسوم", "الأعمال"),
    "ar_tech": ("تكنولوجيا", "ذكاء اصطناعي", "تطبيق", "هاتف", "شريحة", "برمجيات", "سيبراني", "إنترنت", "روبوت", "آبل", "غوغل", "ميتا", "مايكروسوفت",
                "أمازون", "رقمي", "خوارزمية", "بيانات", "حاسوب", "فضاء", "قمر صناعي", "تقنية", "منصة", "قرصنة", "ابتكار"),
    "ar_arts": ("فيلم", "مسلسل", "مهرجان", "فنان", "موسيقى", "أغنية", "معرض", "رواية", "كتاب", "سينما", "ثقافة", "جائزة", "متحف", "مسرح", "ممثل",
                "مخرج", "ألبوم", "أدب", "شاعر", "فنية", "تراث", "أوسكار", "كان"),
    "ar_local": ("المغرب", "مغربي", "المغاربة", "الرباط", "الدار البيضاء", "مراكش", "طنجة", "فاس", "أكادير", "المملكة المغربية", "مكناس", "وجدة", "تطوان"),
    "ar_world": POLITICS,
}
TOPICAL = ("ar_sports", "ar_economy", "ar_tech", "ar_arts")


def _ar(t):
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", str(t or "").lower())
    t = re.sub("[أإآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[^\w\s]", " ", t)


def _words(t):
    return [w for w in _ar(t).split() if len(w) > 2]


def _grams(text, n=4):
    w = _words(text)
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def duplicates(a, b):
    ta, tb = set(_words(a["title"])), set(_words(b["title"]))
    if ta and tb and (ta == tb or len(ta & tb) / len(ta | tb) >= 0.75):
        return True
    ga, gb = _grams(a.get("content", "")), _grams(b.get("content", ""))
    return bool(ga and gb and len(ga & gb) / min(len(ga), len(gb)) >= 0.40)


def dedupe(arts):
    """Keeps the newest copy of every story. Returns the list of removed articles (the caller deletes their images)."""
    flat = sorted(((k, a) for k, v in arts.items() for a in v), key=lambda t: t[1]["date"], reverse=True)
    kept, removed = [], []
    for k, a in flat:
        if any(duplicates(a, b) for _, b in kept):
            removed.append(a)
        else:
            kept.append((k, a))
    keep_ids = {a["id"] for _, a in kept}
    for k in arts:
        arts[k] = [a for a in arts[k] if a["id"] in keep_ids]
    return removed


def is_duplicate_of_any(new, arts):
    return any(duplicates(new, b) for v in arts.values() for b in v)


def _stem(w):
    return re.sub(r"^(وال|بال|لل|ال|و)", "", w) if len(w) > 4 else w


def _score(text, words):
    toks = [_stem(t) for t in _ar(text).split()]
    joined = " ".join(toks)
    n = 0
    for w in words:
        k = _ar(w).strip()
        if " " in k:
            n += joined.count(_stem(k.split()[0]) + " " + k.split()[1])
        else:
            ks = _stem(k)
            n += sum(1 for t in toks if t == ks or (len(ks) >= 4 and t.startswith(ks)))
    return n


def heuristic(a, current):
    """Conservative fallback (used only when no language model is available): moves an article only when the evidence is clear."""
    title, body = a["title"], a.get("summary", "") + " " + a.get("content", "")[:500]
    score = {c: 3 * _score(title, w) + _score(body, w) for c, w in HINTS.items()}
    cur = score.get(current, 0)
    best_topic = max(TOPICAL, key=lambda c: score[c])
    if score[best_topic] >= 4 and score[best_topic] >= cur + 2:
        return best_topic
    if score["ar_local"] >= 4 and score["ar_local"] >= cur + 2:
        return "ar_local"
    if current in TOPICAL + ("ar_local",) and score["ar_world"] >= 4 and score[current] <= 1:
        return "ar_world"             # political news never stays in tech / sports / arts / economy (or in Morocco news with no Morocco in it)
    return current


def classify_llm(items, llm, categories):
    names = "\n".join(f"- {k}: {v}" for k, v in categories.items())
    system = ("أنت رئيس تحرير. صنّف كل مقال في قسم واحد فقط من الأقسام التالية:\n" + names +
              "\nالقواعد: ar_local = كل خبر موضوعه الأساسي المغرب أو المغاربة (سياسة واجتماع وشأن داخلي). ar_world = السياسة والأحداث الدولية والعربية والحروب "
              "والعلاقات بين الدول. ar_economy = الاقتصاد والمال والأسواق والشركات. ar_tech = التكنولوجيا والعلوم الرقمية. ar_sports = الرياضة فقط. "
              "ar_arts = الفن والثقافة والسينما والأدب. الخبر السياسي لا يوضع أبداً في التكنولوجيا أو الرياضة أو الفن. "
              'أعد JSON فقط بالشكل {"id": "رمز_القسم", ...} لكل المقالات.')
    user = "\n".join(f"[{a['id']}] {a['title']} — {a.get('summary', '')[:220]}" for a in items)
    raw = llm(system, user)
    a, b = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[a:b + 1])
    return {k: v for k, v in data.items() if v in categories}


def run(arts, categories, llm=None, limit=30, log=print):
    """Returns (removed_articles, moved_count). Mutates `arts` in place."""
    removed = dedupe(arts)
    todo = [(k, a) for k, v in arts.items() for a in v if not a.get("cat_ok")][:limit]
    verdict = {}
    if llm and todo:
        for i in range(0, len(todo), 10):
            chunk = [a for _, a in todo[i:i + 10]]
            try:
                verdict.update(classify_llm(chunk, llm, categories))
            except Exception as ex:
                log("classification by the model failed, using keyword scoring:", str(ex)[:120])
                break
    moves = []
    for k, a in todo:
        new = verdict.get(a["id"]) or heuristic(a, k)
        a["cat_ok"] = True
        if new != k:
            moves.append((k, new, a))
    for old, new, a in moves:
        arts[old] = [x for x in arts[old] if x["id"] != a["id"]]
        arts[new].append(a)
        log(f"moved to the right section: {a['id']}  {old} -> {new}  | {a['title'][:60]}")
    for k in arts:
        arts[k].sort(key=lambda x: x["date"], reverse=True)
    return removed, len(moves)
