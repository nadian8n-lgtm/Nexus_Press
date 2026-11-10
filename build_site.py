"""Builds the whole static site from articles.json.

Outputs: index.html, category-<key>.html, articles/<id>.html, about/contact/privacy-policy,
weather.html, search.html, search.json, feed.xml, sitemap.xml, robots.txt, manifest.webmanifest, sw.js
"""
import html
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import legal

ROOT = Path(__file__).parent
REPO = os.getenv("GITHUB_REPOSITORY", "")  # e.g. user/Nexus_Press (set automatically in Actions)
SITE_URL = os.getenv("SITE_URL") or (
    f"https://{REPO.split('/')[0]}.github.io/{REPO.split('/')[1]}" if "/" in REPO else "")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "nadia.bouizgarne1@gmail.com"
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")  # ca-pub-XXXXXXXXXXXXXXXX after approval
# Newsletter: leave empty -> subscribers are e-mailed to CONTACT_EMAIL through FormSubmit.
# Or set NEWSLETTER_BUTTONDOWN=<your buttondown username> to use Buttondown (it can e-mail feed.xml daily).
NEWSLETTER_BUTTONDOWN = os.getenv("NEWSLETTER_BUTTONDOWN", "")
# Google Apps Script web-app URL (Code.gs): comments + contact form + newsletter. Set it as GitHub variable NP_API.
NP_API = os.getenv("NP_API", "").strip()
POLL_NS = "np-" + (re.sub(r"[^a-z0-9]+", "-", REPO.lower()).strip("-") if REPO else "nexus-press")

CATEGORIES = {
    "ar_local": "أخبار المغرب",
    "ar_world": "الأخبار الدولية",
    "ar_economy": "اقتصاد",
    "ar_tech": "تكنولوجيا",
    "ar_sports": "رياضة",
    "ar_arts": "فن وثقافة",
}
# Moroccan outlets are not used as sources any more (Morocco is covered through Google Trends).
MOROCCAN_HOSTS = ("hespress", "le360", "hibapress", "alyaoum24", "medias24", "2m.ma", "snrt", "map.ma", "mapexpress",
                  "barlamane", "goud.ma", "chouftv", "yabiladi", "lakome", "akhbarona", "assahifa", "almaghribtoday",
                  "h24info", "lematin", "leconomiste", "telquel", "aujourdhui.ma", "bladi", "febrayer", "anfaspress",
                  "kech24", "moroccoworldnews", "moroccotomorrow", "hespress", "lopinion.ma", "maroc.ma", "alaoual",
                  "almassaa", "assabah", "rue20", "lesiteinfo", "challenge.ma", "ledesk", "elbotola", "arryadia",
                  "hibapress", "tanja24", "bayanealyaoume", "sahraa", "alakhbar")
e = html.escape

POLL_BANK = [
    ("ما أكثر مجال إخباري تحرص على متابعته يوميًا؟", ["السياسة", "الاقتصاد", "التكنولوجيا", "الرياضة", "الفن والثقافة"]),
    ("ما وسيلتك المفضلة لتلقي الأخبار؟", ["المواقع الإخبارية", "وسائل التواصل الاجتماعي", "التلفاز", "النشرات البريدية"]),
    ("هل تثق في الأخبار المنتشرة على وسائل التواصل الاجتماعي؟", ["نعم غالبًا", "أحيانًا فقط", "نادرًا", "لا أثق بها"]),
    ("ما رأيك في استخدام الذكاء الاصطناعي في إعداد الأخبار؟", ["أؤيده مع مراجعة بشرية", "أؤيده بالكامل", "أعارضه", "لا رأي لي"]),
    ("كم من الوقت تقضيه يوميًا في متابعة الأخبار؟", ["أقل من 15 دقيقة", "من 15 إلى 30 دقيقة", "من 30 دقيقة إلى ساعة", "أكثر من ساعة"]),
    ("ما الوقت الذي تفضّله لقراءة الأخبار؟", ["الصباح الباكر", "خلال النهار", "المساء", "قبل النوم"]),
    ("أي أسلوب تفضّل في المقالات الإخبارية؟", ["الخبر المختصر", "المقال المعمّق", "التحليل مع الخلفية", "التقارير المصوّرة"]),
    ("ما الرياضة التي تتابعها أكثر؟", ["كرة القدم", "كرة السلة", "التنس", "رياضات أخرى"]),
    ("هل تتابع أخبار الاقتصاد وأسواق المال بانتظام؟", ["نعم يوميًا", "أسبوعيًا", "نادرًا", "لا أتابعها"]),
    ("ما المحتوى الذي تودّ أن نزيد منه في نكسوس بريس؟", ["الأخبار العاجلة", "التحليلات", "التحقيقات", "الفن والثقافة"]),
    ("كيف تقيّم موقع نكسوس بريس؟", ["ممتاز", "جيد", "مقبول", "يحتاج إلى تحسين"]),
    ("ما أكثر قضية تشغل العالم اليوم برأيك؟", ["الغلاء والاقتصاد", "المناخ والبيئة", "الذكاء الاصطناعي", "الأمن والسلام"]),
    ("هل تفضّل قراءة الأخبار بالوضع الليلي؟", ["نعم دائمًا", "أحيانًا", "لا، أفضّل الوضع العادي"]),
    ("أين تقرأ الأخبار غالبًا؟", ["على الهاتف", "على الحاسوب", "على الجهاز اللوحي", "حسب الظرف"]),
]


SW_JS = """/* Nexus Press service worker: instant repeat visits + offline fallback */
const V = 'np-__VERSION__';
const CORE = ['./', 'style.css', 'site.js', 'tools.js', 'logo.webp'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(V).then(c => Promise.allSettled(CORE.map(u => c.add(u)))));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;
  if (r.mode === 'navigate') {            // pages: network first, cache when offline
    e.respondWith(fetch(r).then(res => { const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); return res; })
      .catch(() => caches.match(r).then(m => m || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(r).then(m => {   // assets & images: cache first, refresh in background
    const net = fetch(r).then(res => { if (res.ok) { const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); } return res; }).catch(() => m);
    return m || net;
  }));
});
"""


def ad(pos, extra=""):
    """Ad unit. Renders NOTHING until ADSENSE_CLIENT and a slot id are set (so the site stays clean before approval)."""
    slot = os.getenv(f"ADSENSE_SLOT_{pos.upper()}") or os.getenv("ADSENSE_SLOT", "")
    if not (ADSENSE_CLIENT and slot):
        return ""
    return (f'<div class="ad-wrap notranslate {extra}"><ins class="adsbygoogle" style="display:block" data-ad-client="{e(ADSENSE_CLIENT)}" '
            f'data-ad-slot="{e(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


def is_moroccan(url="", publisher=""):
    host = urllib.parse.urlparse(url).netloc.lower()
    name = publisher.lower()
    return host.endswith(".ma")
