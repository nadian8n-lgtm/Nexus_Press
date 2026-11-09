/**
 * Nexus Press backend  (Google Apps Script + Google Sheet, free, runs on your Gmail)
 *  - comments with moderation (one-click approve link arrives by e-mail)
 *  - contact form -> e-mail straight to your inbox
 *  - newsletter subscribers + daily digest e-mail
 *
 * SETUP (5 minutes): paste this file in script.google.com (from your Google Sheet: Extensions > Apps Script),
 * edit the 3 constants below, Deploy > New deployment > Web app > Execute as: Me, Who has access: Anyone,
 * copy the /exec URL and save it in GitHub: Settings > Secrets and variables > Actions > Variables > NP_API.
 */
const OWNER_EMAIL = 'nadia.bouizgarne1@gmail.com';
const SITE_URL = 'https://YOUR-USER.github.io/Nexus_Press/';   // <-- your site address, with the final slash
const SECRET = 'change-this-to-a-long-random-text-123XYZ';       // <-- any long random text (protects approve/delete links)
const AUTO_APPROVE = false;   // false = every comment waits for your approval (recommended)
const BAD_WORDS = ['كلب', 'حمار', 'قحبة', 'ابن الكلب', 'لعنة الله', 'fuck', 'shit', 'bitch'];   // matching comments are blocked automatically

const COMMENT_HEAD = ['id', 'time', 'article', 'name', 'email', 'text', 'status'];
const CONTACT_HEAD = ['time', 'name', 'email', 'subject', 'message'];
const SUB_HEAD = ['time', 'email', 'status'];

function sh_(name, head) {
  const ss = SpreadsheetApp.getActive() || SpreadsheetApp.create('Nexus Press data');
  let s = ss.getSheetByName(name);
  if (!s) { s = ss.insertSheet(name); s.appendRow(head); s.setFrozenRows(1); }
  return s;
}
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function html_(t) { return HtmlService.createHtmlOutput('<meta charset="utf-8"><body dir="rtl" style="font-family:sans-serif;padding:30px"><h2>' + t + '</h2></body>'); }
function sign_(s) { return Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature(s, SECRET)).slice(0, 22); }
function clean_(s, n) { return String(s || '').replace(/[\u0000-\u001f<>]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n); }
function mailOk_(e) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(e); }

function doGet(e) {
  const p = e.parameter || {};
  if (p.action === 'comments') {
    const s = sh_('comments', COMMENT_HEAD), rows = s.getDataRange().getValues().slice(1);
    const list = rows.filter(r => r[2] === p.article && r[6] === 'approved')
      .map(r => ({ id: r[0], name: r[3], text: r[5], ts: new Date(r[1]).getTime() })).sort((a, b) => b.ts - a.ts);
    return json_({ ok: true, total: list.length, comments: list.slice(0, 200) });
  }
  if ((p.action === 'approve' || p.action === 'delete') && p.token === sign_(p.action + p.id)) {
    const s = sh_('comments', COMMENT_HEAD), rows = s.getDataRange().getValues();
    for (let i = 1; i < rows.length; i++) if (String(rows[i][0]) === p.id) {
      s.getRange(i + 1, 7).setValue(p.action === 'approve' ? 'approved' : 'deleted');
      return html_(p.action === 'approve' ? '✅ تم نشر التعليق' : '🗑️ تم حذف التعليق');
    }
    return html_('التعليق غير موجود');
  }
  if (p.action === 'unsub' && p.token === sign_('unsub' + p.email)) {
    const s = sh_('subscribers', SUB_HEAD), rows = s.getDataRange().getValues();
    for (let i = 1; i < rows.length; i++) if (rows[i][1] === p.email) s.getRange(i + 1, 3).setValue('unsubscribed');
    return html_('تم إلغاء اشتراكك في النشرة البريدية');
  }
  return json_({ ok: true, service: 'Nexus Press' });
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (x) { return json_({ ok: false, error: 'bad request' }); }
  if (d.hp) return json_({ ok: true });                      // honeypot: bots fill it
  const lock = LockService.getScriptLock(); lock.waitLock(15000);
  try {
    if (d.type === 'comment') return comment_(d);
    if (d.type === 'contact') return contact_(d);
    if (d.type === 'subscribe') return subscribe_(d);
    return json_({ ok: false, error: 'unknown type' });
  } finally { lock.releaseLock(); }
}

function comment_(d) {
  const name = clean_(d.name, 40), text = clean_(d.text, 1000), article = clean_(d.article, 120), email = clean_(d.email, 80);
  if (name.length < 2 || text.length < 3 || !article) return json_({ ok: false, error: 'invalid' });
  if (d.t && d.t < 3000) return json_({ ok: false, error: 'too fast' });          // humans need > 3 s
  const cache = CacheService.getScriptCache(), k = 'c' + Utilities.base64Encode(name + article).slice(0, 40);
  if (cache.get(k)) return json_({ ok: false, error: 'wait' });
  cache.put(k, '1', 30);
  const low = text.toLowerCase(), bad = BAD_WORDS.some(w => low.indexOf(w) > -1);
  const hasLink = /https?:\/\/|www\./i.test(text);
  const status = bad ? 'blocked' : (AUTO_APPROVE && !hasLink ? 'approved' : 'pending');
  const id = Utilities.getUuid().slice(0, 8);
  sh_('comments', COMMENT_HEAD).appendRow([id, new Date(), article, name, email, text, status]);
  if (status === 'pending') {
    const base = ScriptApp.getService().getUrl();
    const link = a => base + '?action=' + a + '&id=' + id + '&token=' + encodeURIComponent(sign_(a + id));
    MailApp.sendEmail({
      to: OWNER_EMAIL, subject: 'تعليق جديد بانتظار المراجعة - نكسوس بريس',
      htmlBody: '<div dir="rtl" style="font-family:sans-serif"><p><b>' + name + '</b> على المقال <code>' + article + '</code>:</p><blockquote>' + text +
        '</blockquote><p><a href="' + link('approve') + '">✅ نشر التعليق</a> &nbsp;|&nbsp; <a href="' + link('delete') + '">🗑️ حذف</a></p></div>'
    });
  }
  return json_({ ok: true, status: status });
}

function contact_(d) {
  const name = clean_(d.name, 60), email = clean_(d.email, 80), subject = clean_(d.subject, 120), message = String(d.message || '').slice(0, 4000);
  if (!name || !mailOk_(email) || !subject || message.length < 3) return json_({ ok: false, error: 'invalid' });
  sh_('contact', CONTACT_HEAD).appendRow([new Date(), name, email, subject, message]);
  MailApp.sendEmail({ to: OWNER_EMAIL, replyTo: email, name: 'نكسوس بريس - اتصل بنا', subject: 'نكسوس بريس: ' + subject,
    body: 'الاسم: ' + name + '\nالبريد: ' + email + '\n\n' + message });
  return json_({ ok: true });
}

function subscribe_(d) {
  const email = clean_(d.email, 80).toLowerCase();
  if (!mailOk_(email)) return json_({ ok: false, error: 'invalid' });
  const s = sh_('subscribers', SUB_HEAD), rows = s.getDataRange().getValues();
  for (let i = 1; i < rows.length; i++) if (rows[i][1] === email) { s.getRange(i + 1, 3).setValue('active'); return json_({ ok: true }); }
  s.appendRow([new Date(), email, 'active']);
  MailApp.sendEmail({ to: email, name: 'نكسوس بريس', subject: 'مرحبًا بك في نشرة نكسوس بريس',
    htmlBody: '<div dir="rtl" style="font-family:sans-serif"><p>شكرًا لاشتراكك! ستصلك آخر الأخبار يوميًا.</p><p><a href="' + SITE_URL + '">زيارة الموقع</a></p></div>' });
  return json_({ ok: true });
}

/** Daily digest: Triggers (clock icon) > Add trigger > sendDailyDigest > Time-driven > Day timer > 8-9 am */
function sendDailyDigest() {
  const xml = UrlFetchApp.fetch(SITE_URL + 'feed.xml', { muteHttpExceptions: true }).getContentText();
  const items = [], re = /<item><title>([\s\S]*?)<\/title><link>([\s\S]*?)<\/link>[\s\S]*?<description>([\s\S]*?)<\/description>/g;
  let m;
  while ((m = re.exec(xml)) && items.length < 8) items.push({ t: m[1], l: m[2], d: m[3] });
  if (!items.length) return;
  const subs = sh_('subscribers', SUB_HEAD).getDataRange().getValues().slice(1).filter(r => r[2] === 'active').map(r => r[1]);
  const list = items.map(i => '<li style="margin-bottom:14px"><a href="' + i.l + '" style="font-size:17px;font-weight:bold;color:#0b3c7a;text-decoration:none">' + i.t +
    '</a><br><span style="color:#555">' + i.d + '</span></li>').join('');
  const base = ScriptApp.getService().getUrl();
  subs.slice(0, 90).forEach(em => {       // free Gmail limit: ~100 e-mails/day
    const un = base + '?action=unsub&email=' + encodeURIComponent(em) + '&token=' + encodeURIComponent(sign_('unsub' + em));
    MailApp.sendEmail({ to: em, name: 'نكسوس بريس', subject: '📰 أبرز أخبار اليوم - نكسوس بريس',
      htmlBody: '<div dir="rtl" style="font-family:Tahoma,sans-serif;max-width:600px;margin:auto"><h2 style="color:#0b3c7a">نكسوس بريس</h2><ul style="padding-right:18px">' + list +
        '</ul><p><a href="' + SITE_URL + '">المزيد في الموقع</a></p><hr><small><a href="' + un + '">إلغاء الاشتراك</a></small></div>' });
  });
}
