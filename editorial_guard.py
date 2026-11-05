"""Create a mandatory human-review checklist for unpublished news drafts.

This is a process guard, not legal advice, legal clearance, or a guarantee against claims.
It never publishes content and it never marks a review item as approved automatically.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_DIR = Path(os.getenv("DRAFT_OUTPUT_DIR", "/tmp/nexus-press-drafts"))
DRAFTS_PATH = OUTPUT_DIR / "drafts.json"
CHECKLIST_PATH = OUTPUT_DIR / "editorial-legal-review.json"

REQUIRED_REVIEW = [
    {
        "id": "primary_sources_opened",
        "label": "فتح المحرر المصادر الأصلية وقرأها، لا الاكتفاء بمقتطفات RSS.",
        "approved": False,
    },
    {
        "id": "facts_verified",
        "label": "التحقق المستقل من كل اسم ورقم وتاريخ ومكان وادعاء، والتمييز بين المؤكد وغير المؤكد.",
        "approved": False,
    },
    {
        "id": "source_independence_assessed",
        "label": "تقييم استقلال المصادر ومصدر المعلومة الأصلي؛ اختلاف النطاقات وحده لا يثبت الاستقلال.",
        "approved": False,
    },
    {
        "id": "originality_and_copyright_reviewed",
        "label": "مراجعة أصالة الصياغة وعدم نسخ/ترجمة النصوص المحمية؛ فحص التشابه الآلي ليس ضماناً.",
        "approved": False,
    },
    {
        "id": "quotes_checked",
        "label": "التحقق من الاقتباسات حرفياً ومن نسبتها وسياقها، أو حذفها إذا تعذر التحقق.",
        "approved": False,
    },
    {
        "id": "privacy_and_personality_reviewed",
        "label": "تقليل البيانات الشخصية والتحقق من مشروعية نشرها ومراعاة الخصوصية وحقوق الأشخاص.",
        "approved": False,
    },
    {
        "id": "right_of_reply_considered",
        "label": "عند نشر ادعاء قد يضر بسمعة شخص أو جهة، توثيق طلب الرد وإدراج الرد أو بيان تعذر الحصول عليه.",
        "approved": False,
    },
    {
        "id": "image_rights_cleared",
        "label": "التحقق من ترخيص الصورة ومصدرها وحقوق الأشخاص الظاهرين؛ الرسم التوضيحي ليس صورة توثيقية.",
        "approved": False,
    },
    {
        "id": "corrections_and_contact_ready",
        "label": "إتاحة وسيلة تواصل واضحة، وحفظ سجل المصادر والنسخة وتاريخ المراجعة، والاستعداد لتصحيح الأخطاء.",
        "approved": False,
    },
    {
        "id": "editor_approved",
        "label": "اعتماد محرر مسؤول بعد قراءة المقال كاملاً ومراجعة الأدلة.",
        "approved": False,
    },
    {
        "id": "legal_review_if_high_risk",
        "label": "إذا كان الموضوع حساساً أو يتضمن اتهامات/قاصرين/صحة/قضايا قضائية/خصوصية، الحصول على مراجعة قانونية مغربية قبل النشر.",
        "approved": False,
    },
]


def load_drafts():
    try:
        data = json.loads(DRAFTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read generated drafts at {DRAFTS_PATH}: {error}") from error
    if not isinstance(data, list):
        raise RuntimeError("drafts.json must contain a JSON array")
    return data


def validate_draft(draft):
    if not isinstance(draft, dict):
        raise ValueError("draft must be a JSON object")
    for key in ("draft_id", "title", "summary", "body", "category", "sources", "image"):
        if not draft.get(key):
            raise ValueError(f"missing required field: {key}")
    if not isinstance(draft["sources"], list) or not draft["sources"]:
        raise ValueError("draft has no source records")
    if not isinstance(draft["body"], list) or not draft["body"]:
        raise ValueError("draft has no article paragraphs")
    domains = set()
    for source in draft["sources"]:
        url = source.get("url", "") if isinstance(source, dict) else ""
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source URL must use HTTPS and include a hostname")
        domains.add(parsed.netloc.lower().removeprefix("www."))
    if len(domains) < 2:
        raise ValueError("draft must retain links from at least two distinct domains")
    image = Path(draft["image"])
    if image.name != draft["image"] or image.suffix.lower() != ".svg":
        raise ValueError("draft image must be a local SVG filename, not a remote source image")
    if not (OUTPUT_DIR / image.name).is_file():
        raise ValueError("draft SVG illustration is missing")


def main():
    drafts = load_drafts()
    reviews = []
    for draft in drafts:
        validate_draft(draft)
        review = {
            "draft_id": draft["draft_id"],
            "title": draft["title"],
            "category": draft["category"],
            "sources": draft["sources"],
            "draft_file": f"draft-{draft['category']}-{draft['draft_id']}.html",
            "publication_status": "blocked_pending_human_review",
            "legal_clearance": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "checklist": REQUIRED_REVIEW,
            "warning": "This checklist is not legal advice or legal clearance. Automated checks cannot guarantee truth, originality, rights clearance, or immunity from liability.",
        }
        reviews.append(review)
    CHECKLIST_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "publication_enabled": False,
            "reviews": reviews,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Validated {len(drafts)} draft(s); all remain blocked pending human editorial review.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Editorial review gate failed: {error}", file=sys.stderr)
        sys.exit(1)
