/* Nexus Press - learning assistant (engine: Puter.js, https://js.puter.com/v2/ ; loaded only when the visitor sends a message) */
(function () {
  'use strict';
  var box = document.getElementById('ai-chat');
  if (!box) return;
  var msgs = document.getElementById('ai-msgs'), form = document.getElementById('ai-form'),
      input = document.getElementById('ai-input'), note = document.getElementById('ai-note');
  var hist = [], busy = false, last = 0, loading = null;
  var SYSTEM = 'أنت مساعد تعليمي لموقع نكسوس بريس في قسم أكاديمية الذكاء الاصطناعي. أجب بالعربية بوضوح وإيجاز وبأمثلة بسيطة، ' +
    'وبشيفرة بايثون قصيرة عند الحاجة. لا تتحدث عن أخبار عاجلة ولا تقدم نصائح طبية أو قانونية أو مالية. إذا لم تعرف الجواب فقل ذلك صراحة.';

  function say(t, ok) { note.textContent = t || ''; note.className = 'form-msg ' + (ok ? 'ok' : 'err'); }
  function add(role) {
    var d = document.createElement('div'); d.className = 'ai-m ' + (role === 'u' ? 'u' : 'b');
    msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d;
  }
  function loadPuter() {
    if (window.puter) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise(function (res, rej) {
      var s = document.createElement('script'); s.src = 'https://js.puter.com/v2/'; s.async = true;
      s.onload = res; s.onerror = function () { loading = null; rej(new Error('load')); };
      document.head.appendChild(s);
    });
    return loading;
  }
  function textOf(r) {
    if (typeof r === 'string') return r;
    var c = r && r.message && r.message.content;
    if (Array.isArray(c)) return c.map(function (p) { return p.text || ''; }).join('');
    return typeof c === 'string' ? c : (r && r.text) || '';
  }

  form.addEventListener('submit', async function (ev) {
    ev.preventDefault();
    var q = input.value.trim();
    if (!q || busy) return;
    if (Date.now() - last < 3000) { say('انتظر لحظات قبل السؤال التالي.', false); return; }
    busy = true; last = Date.now(); say('');
    add('u').textContent = q; input.value = '';
    var out = add('b'); out.textContent = '…';
    var ctx = hist.slice(-6).map(function (m) { return (m.r === 'u' ? 'المستخدم: ' : 'المساعد: ') + m.t; }).join('\n');
    var prompt = SYSTEM + '\n\n' + (ctx ? ctx + '\n' : '') + 'المستخدم: ' + q + '\nالمساعد:';
    try {
      await loadPuter();
      var opts = { stream: true }, model = box.getAttribute('data-puter-model');
      if (model) opts.model = model;
      var res = await window.puter.ai.chat(prompt, opts), full = '';
      if (res && typeof res[Symbol.asyncIterator] === 'function') {
        out.textContent = '';
        for await (var part of res) {
          if (part && part.text) { full += part.text; out.textContent = full; msgs.scrollTop = msgs.scrollHeight; }
        }
      } else { full = textOf(res); out.textContent = full; }
      if (!full) { out.textContent = 'لم يصل رد. حاول مرة أخرى.'; }
      hist.push({ r: 'u', t: q }, { r: 'b', t: full });
    } catch (e) {
      out.textContent = 'تعذّر الحصول على رد الآن. تأكد من اتصالك أو سجّل الدخول في نافذة Puter إن ظهرت، ثم أعد المحاولة.';
    }
    busy = false;
  });
})();
