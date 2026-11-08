"""Quality gate: exits with code 1 if the built site has broken internal links, missing images or missing core files."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).parent
SKIP_PREFIX = ("http:", "https:", "//", "mailto:", "tel:", "data:", "#", "javascript:")
problems = []

for need in ("style.css", "site.js", "image_MUwSAA.png", "index.html", "about.html", "contact.html", "privacy-policy.html"):
    if not (ROOT / need).exists():
        problems.append(f"missing core file: {need}")

pages = [p for p in list(ROOT.glob("*.html")) + list((ROOT / "articles").glob("*.html"))
         if not p.name.startswith("google") and p.name != "404.html"]
for page in pages:
    text = page.read_text(encoding="utf-8")
    for val in re.findall(r'(?:href|src)="([^"]+)"', text):
        if val.startswith(SKIP_PREFIX):
            continue
        target = (page.parent / unquote(urlparse(val).path)).resolve()
        if not target.exists():
            problems.append(f"{page.relative_to(ROOT)} -> missing {val}")
    for needle in ('class="main-nav"', 'class="footer"'):
        if needle not in text:
            problems.append(f"{page.relative_to(ROOT)} lacks {needle}")

if problems:
    print("SITE CHECK FAILED:")
    print("\n".join(sorted(set(problems))[:50]))
    sys.exit(1)
print(f"site check OK: {len(pages)} pages, all internal links and images exist")
