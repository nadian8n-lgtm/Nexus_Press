"""Add configured AdSense units to generated article pages.

No fake publisher or ad-slot IDs are emitted. Set ADSENSE_CLIENT and the four slot IDs
as GitHub Actions repository variables only after the site/account is approved by Google.
"""

import html
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIENT = os.getenv("ADSENSE_CLIENT", "").strip()
SLOTS = {
    "top": os.getenv("ADSENSE_SLOT_TOP", "").strip(),
    "inline": os.getenv("ADSENSE_SLOT_INLINE", "").strip(),
    "bottom": os.getenv("ADSENSE_SLOT_BOTTOM", "").strip(),
    "side": os.getenv("ADSENSE_SLOT_SIDE", "").strip(),
}


def ad_unit(slot, placement):
    label = {
        "top": "إعلان أعلى المقال",
        "inline": "إعلان داخل المقال",
        "bottom": "إعلان أسفل المقال",
        "side": "إعلان جانبي",
    }[placement]
    if CLIENT.startswith("ca-pub-") and slot.isdigit():
        return (
            f'<div class="article-ad article-ad-{placement}" aria-label="{label}">'
            f'<ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{html.escape(CLIENT, quote=True)}" '
            f'data-ad-slot="{html.escape(slot, quote=True)}" '
            f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>'
            '</div>'
        )
    return (
        f'<div class="article-ad-placeholder article-ad-{placement}" aria-label="{label}">'
        f'<span>{label}</span><small>تظهر الإعلانات بعد اعتماد AdSense وإضافة معرّف الناشر ورقم الوحدة</small>'
        '</div>'
    )


def inject(path):
    source = path.read_text(encoding="utf-8")
    if "<!-- adsense-loader -->" in source:
        return False

    if CLIENT.startswith("ca-pub-"):
        loader = (
            '<!-- adsense-loader -->'
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(CLIENT, quote=True)}" crossorigin="anonymous"></script>'
        )
        source = re.sub(r"</head\s*>", loader + "</head>", source, count=1, flags=re.I)

    top = ad_unit(SLOTS["top"], "top")
    source, top_count = re.subn(r"(<main\b[^>]*>)", top + r"\1", source, count=1, flags=re.I)
    if not top_count:
        return False

    # Put desktop side units around the article when the generated article markup is present.
    source, wrapped = re.subn(
        r'(<main\b[^>]*>\s*)(<article\b[^>]*class=["\'][^"\']*\bpost\b[^"\']*["\'][^>]*>)',
        lambda m: m.group(1) + '<div class="article-ad-layout">' + ad_unit(SLOTS["side"], "side") + m.group(2),
        source,
        count=1,
        flags=re.I,
    )
    if wrapped:
        source = re.sub(
            r"</article\s*>\s*</main\s*>",
            '</article>' + ad_unit(SLOTS["side"], "side") + '</div></main>',
            source,
            count=1,
            flags=re.I,
        )
        source = re.sub(
            r"</article\s*>",
            '</article>' + ad_unit(SLOTS["bottom"], "bottom"),
            source,
            count=1,
            flags=re.I,
        )
    else:
        source = re.sub(r"</article\s*>", ad_unit(SLOTS["bottom"], "bottom") + "</article>", source, count=1, flags=re.I)

    # One in-content unit after paragraph two; avoid excessive ad density.
    body_pattern = re.compile(r'(<div\b[^>]*class=["\'][^"\']*\barticle-body\b[^"\']*["\'][^>]*>)(.*?)(</div\s*>)', re.I | re.S)
    match = body_pattern.search(source)
    if match:
        body = match.group(2)
        paragraphs = list(re.finditer(r"</p\s*>", body, re.I))
        if len(paragraphs) >= 2:
            index = paragraphs[1].end()
            body = body[:index] + ad_unit(SLOTS["inline"], "inline") + body[index:]
            source = source[:match.start(2)] + body + source[match.end(2):]

    path.write_text(source, encoding="utf-8")
    return True


def main():
    paths = sorted(set(ROOT.glob("article-*.html")) | set(ROOT.glob("news-*.html")))
    updated = sum(1 for path in paths if inject(path))
    if not CLIENT.startswith("ca-pub-"):
        print("AdSense is not active: set the approved publisher client ID and ad-slot IDs in repository variables.")
    print(f"Added article ad placements to {updated} page(s); checked {len(paths)} article page(s).")


if __name__ == "__main__":
    main()
