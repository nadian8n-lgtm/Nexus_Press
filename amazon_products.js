#!/usr/bin/env node
/**
 * Nexus Press - Amazon deals pages (Creators API, Node 18+, NO dependencies).
 *
 * IMPORTANT: Amazon retired PA-API 5 (the old paapi5-nodejs-sdk now gets HTTP 403). The replacement is the Creators API:
 * OAuth 2.0 credentials (Credential ID + Secret + Version) from Associates Central > Tools > Creators API.
 *
 * Env: AMAZON_CREDENTIAL_ID, AMAZON_CREDENTIAL_SECRET, AMAZON_CREDENTIAL_VERSION (default 3.1 = North America, 3.2 = EU, 3.3 = Far East),
 *      AMAZON_TRACKING_ID (your Associate tag), AMAZON_MARKETPLACE (default www.amazon.com),
 *      optional: AMAZON_TOKEN_URL, AMAZON_TOKEN_SCOPE
 * Test without calling Amazon:  node amazon_products.js --mock sample.json
 *
 * Output: deals/<ASIN>.html (one page per product) + deals/index.html. Old pages are deleted on every successful run,
 * because Amazon requires prices to be refreshed (24 h) and to carry a date/time.
 */
const fs = require('fs');
const path = require('path');

const E = process.env;
const MARKETPLACE = E.AMAZON_MARKETPLACE || 'www.amazon.com';
const PARTNER_TAG = E.AMAZON_TRACKING_ID || '';
const CRED_ID = E.AMAZON_CREDENTIAL_ID || '';
const CRED_SECRET = E.AMAZON_CREDENTIAL_SECRET || '';
const VERSION = E.AMAZON_CREDENTIAL_VERSION || '3.1';
const API = 'https://creatorsapi.amazon/catalog/v1/searchItems';
const TOKEN_URLS = {
  '3.1': 'https://api.amazon.com/auth/o2/token',
  '3.2': 'https://api.amazon.co.uk/auth/o2/token',
  '3.3': 'https://api.amazon.co.jp/auth/o2/token',
};
const OUT = path.join(__dirname, 'deals');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---- season / topic (same logic as your original script)
function topic(now = new Date()) {
  const m = now.getMonth() + 1;
  if (m >= 6 && m <= 8) return { keywords: 'Casual Summer Fashion tops shorts', name: 'موضة صيفية وتخفيضات', index: 'Apparel' };
  if (m === 12 || m <= 2) return { keywords: 'Unisex Winter jackets warm hoodies', name: 'موضة شتوية دافئة', index: 'Apparel' };
  if (m === 9) return { keywords: 'School backpacks students ergonomic', name: 'مستلزمات مدرسية وكتب', index: 'All' };
  return now.getDate() % 2 === 0
    ? { keywords: 'PlayStation Xbox Gift Cards digital', name: 'تكنولوجيا وألعاب', index: 'VideoGames' }
    : { keywords: 'Bestselling self development growth books', name: 'ثقافة وكتب', index: 'Books' };
}

// ---- helpers that tolerate camelCase / PascalCase differences in the response
const get = (o, ...paths) => {
  for (const p of paths) {
    let v = o;
    for (const k of p.split('.')) {
      if (v == null) break;
      const alt = k.charAt(0).toUpperCase() + k.slice(1);
      v = v[k] !== undefined ? v[k] : v[alt];
    }
    if (v != null && v !== '') return v;
  }
  return undefined;
};

async function getToken() {
  if (!CRED_ID || !CRED_SECRET) throw new Error('Missing AMAZON_CREDENTIAL_ID / AMAZON_CREDENTIAL_SECRET (Creators API credentials, not the old AWS keys)');
  const url = E.AMAZON_TOKEN_URL || TOKEN_URLS[VERSION];
  if (!url) throw new Error(`Credential version ${VERSION}: set AMAZON_TOKEN_URL (Cognito token URL shown in Associates Central)`);
  const v3 = VERSION.startsWith('3');
  const scope = E.AMAZON_TOKEN_SCOPE || (v3 ? 'creatorsapi::default' : 'creatorsapi/default');
  const res = await fetch(url, v3
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ grant_type: 'client_credentials', client_id: CRED_ID, client_secret: CRED_SECRET, scope }) }
    : { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ grant_type: 'client_credentials', client_id: CRED_ID, client_secret: CRED_SECRET, scope }) });
  const j = await res.json().catch(() => ({}));
  if (!res.ok || !j.access_token) throw new Error(`Token request failed (HTTP ${res.status}): ${JSON.stringify(j).slice(0, 300)}`);
  return j.access_token;
}

async function searchItems(t) {
  const token = await getToken();
  const res = await fetch(API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: VERSION.startsWith('2') ? `Bearer ${token}, Version ${VERSION}` : `Bearer ${token}`,
      'x-marketplace': MARKETPLACE,
    },
    body: JSON.stringify({
      keywords: t.keywords, searchIndex: t.index, itemCount: 3, sortBy: 'AvgCustomerReviews',
      partnerTag: PARTNER_TAG, marketplace: MARKETPLACE,
      resources: ['images.primary.large', 'itemInfo.title', 'offersV2.listings.price'],
    }),
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`SearchItems failed (HTTP ${res.status}): ${JSON.stringify(j).slice(0, 400)}`);
  return j;
}

function normalize(item) {
  const price = get(item, 'offersV2.listings.0.price.money.displayAmount', 'offersV2.listings.0.price.displayAmount',
    'offers.listings.0.price.displayAmount') || '';
  return {
    asin: String(get(item, 'asin') || '').replace(/[^A-Za-z0-9]/g, ''),
    title: get(item, 'itemInfo.title.displayValue') || '',
    image: get(item, 'images.primary.large.url') || '',   // Amazon's own image URL, used exactly as returned (no changes)
    url: get(item, 'detailPageURL') || '',
    price,
  };
}

const stamp = () => new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC';

const CSS = `*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,system-ui,sans-serif;line-height:1.9;color:#1e293b;background:#f5f8fb}
.wrap{max-width:860px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px;font-weight:700}
.top a{color:#0b3c7a;text-decoration:none}.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:22px}
h1{font-size:clamp(20px,5vw,28px);line-height:1.5;margin:0 0 12px;border-bottom:4px solid #ff9900;padding-bottom:10px}
.note{font-size:13px;color:#475569;background:#eef2f7;border-right:4px solid #718096;border-radius:6px;padding:10px 14px;margin:0 0 16px}
.box{display:flex;gap:20px;align-items:center;flex-wrap:wrap;border:1px solid #e7e9ec;border-radius:12px;padding:18px;margin:16px 0}
.box img{width:min(220px,100%);height:auto;border-radius:8px;margin:0 auto;display:block}.box .info{flex:1;min-width:230px}
.price{color:#b12704;font-weight:700;font-size:20px;margin:6px 0}.small{display:block;font-size:12px;color:#64748b;line-height:1.6;margin:6px 0 12px}
.btn{display:inline-block;background:#ffd814;border:1px solid #fcd200;color:#111;padding:12px 22px;border-radius:30px;font-weight:700;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px}.item{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-decoration:none;color:inherit}
.item img{width:100%;height:180px;object-fit:contain;background:#fff}.item b{display:block;font-size:15px;line-height:1.6;margin-top:8px}
@media(prefers-color-scheme:dark){body{background:#0b1220;color:#dbe4f0}.card,.item{background:#111b2f;border-color:#243350}.note{background:#17233a;color:#94a3b8}.top a{color:#7dd3fc}.box{border-color:#243350}.box img,.item img{background:#fff}}`;

const DISCLOSURE = `<p class="note">إفصاح: هذه الصفحة تحتوي على روابط تابعة (Affiliate). بصفتنا شركاء في برنامج Amazon Associates قد نحصل على عمولة من المشتريات المؤهلة دون أي تكلفة إضافية عليك.<br>
<span dir="ltr">As an Amazon Associate I earn from qualifying purchases.</span></p>`;

function page(p, t, when) {
  const priceHtml = p.price
    ? `<div class="price">${esc(p.price)}</div>
<span class="small" dir="ltr">Amazon prices are subject to change. Price as of ${esc(when)}.</span>`
    : `<span class="small">السعر الحالي وتوفر المنتج يظهران في صفحة المنتج على أمازون.</span>`;
  return `<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(p.title)} | نكسوس بريس</title><meta name="description" content="${esc(p.title)} - اختيار من قسم ${esc(t.name)} على أمازون.">
<meta name="robots" content="noindex,follow"><style>${CSS}</style></head><body><div class="wrap">
<div class="top"><a href="../index.html">← نكسوس بريس</a><a href="index.html">كل العروض</a></div>
<div class="card">${DISCLOSURE}<h1>${esc(p.title)}</h1>
<p>منتج من قسم <b>${esc(t.name)}</b>، ظهر ضمن أعلى النتائج على أمازون عند الترتيب حسب تقييمات العملاء. التقييمات والمواصفات الكاملة والآراء الحقيقية للمشترين متاحة في صفحة المنتج على أمازون.</p>
<div class="box"><img src="${esc(p.image)}" alt="${esc(p.title)}" loading="lazy" decoding="async">
<div class="info"><h2 style="font-size:17px;margin:0">${esc(p.title)}</h2>${priceHtml}
<a class="btn" href="${esc(p.url)}" target="_blank" rel="sponsored nofollow noopener noreferrer">عرض على أمازون</a></div></div>
</div></div></body></html>`;
}

function indexPage(list, t, when) {
  const cards = list.map((p) => `<a class="item" href="${p.asin}.html"><img src="${esc(p.image)}" alt="${esc(p.title)}" loading="lazy" decoding="async"><b>${esc(p.title)}</b>${p.price ? `<span class="price">${esc(p.price)}</span>` : ''}</a>`).join('');
  return `<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>اختيارات من أمازون | نكسوس بريس</title><meta name="robots" content="noindex,follow"><style>${CSS}</style></head><body><div class="wrap">
<div class="top"><a href="../index.html">← نكسوس بريس</a></div>
<div class="card">${DISCLOSURE}<h1>اختيارات اليوم: ${esc(t.name)}</h1><div class="grid">${cards}</div>
<span class="small" dir="ltr">Amazon prices are subject to change. Price as of ${esc(when)}.</span></div></div></body></html>`;
}

async function main() {
  const t = topic();
  const mi = process.argv.indexOf('--mock');
  const data = mi > -1 ? JSON.parse(fs.readFileSync(process.argv[mi + 1], 'utf8')) : await searchItems(t);
  const items = get(data, 'searchResult.items') || [];
  const list = items.map(normalize).filter((p) => p.asin && p.title && p.image && p.url);
  if (!list.length) throw new Error('No usable products returned: ' + JSON.stringify(data).slice(0, 300));
  const when = stamp();
  fs.mkdirSync(OUT, { recursive: true });
  for (const f of fs.readdirSync(OUT)) if (f.endsWith('.html')) fs.unlinkSync(path.join(OUT, f));   // never keep stale prices
  for (const p of list) {
    fs.writeFileSync(path.join(OUT, `${p.asin}.html`), page(p, t, when));
    console.log('page written:', p.asin, '-', p.title.slice(0, 60));
  }
  fs.writeFileSync(path.join(OUT, 'index.html'), indexPage(list, t, when));
  console.log(`done: ${list.length} products, price time ${when}`);
}

main().catch((e) => { console.error('amazon_products failed:', e.message); process.exit(1); });
