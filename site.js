/* Nexus Press - core script (theme, date, language, slider, comments, share, newsletter, contact, poll, lazy tools) */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var pre = document.body.getAttribute('data-pre') || '';
  var api = document.body.getAttribute('data-api') || '';
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  function inView(el, cb, margin) {
    if (!('IntersectionObserver' in window)) { cb(); return; }
    new IntersectionObserver(function (en, o) { if (en[0].isIntersecting) { cb(); o.disconnect(); } }, { rootMargin: margin || '300px' }).observe(el);
  }

  /* ---- dark mode */
  var tb = $('#theme-btn');
  if (tb) tb.onclick = function () {
    var d = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', d); store.set('np-theme', d);
  };

  /* ---- today's date (Gregorian + Hijri) */
  var td = $('#today');
  if (td) try {
    var now = new Date(), g = now.toLocaleDateString('ar-u-nu-latn', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }), h = '';
    try { h = new Intl.DateTimeFormat('ar-SA-u-ca-islamic-umalqura-nu-latn', { day: 'numeric', month: 'long', year: 'numeric' }).format(now); } catch (e) {}
    td.textContent = g + (h ? '  •  ' + h : '');
  } catch (e) {}

  /* ---- language switcher (Google Translate, loaded only when needed) */
  var m = document.cookie.match(/googtrans=\/ar\/(\w+)/), cur = m ? m[1] : 'ar';
  if (cur !== 'ar') {
    document.documentElement.dir = 'ltr'; document.documentElement.lang = cur;
    var gs = document.createElement('script');
    gs.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit'; gs.async = true;
    document.head.appendChild(gs);
  }
  $$('.lang-btn').forEach(function (b) {
    if (b.dataset.l === cur) b.classList.add('on');
    b.onclick = function () {
      var l = b.dataset.l, host = location.hostname, past = 'expires=Thu, 01 Jan 1970 00:00:00 GMT';
      if (l === 'ar') {
        document.cookie = 'googtrans=;path=/;' + past;
        document.cookie = 'googtrans=;path=/;domain=' + host + ';' + past;
      } else {
        document.cookie = 'googtrans=/ar/' + l + ';path=/';
        document.cookie = 'googtrans=/ar/' + l + ';path=/;domain=' + host;
      }
      location.reload();
    };
  });

  /* ---- hero slider */
  var s = $$('.slide'), d = $$('.dot'), i = 0, t;
  function go(n) {
    if (!s.length) return;
    s[i].classList.remove('active'); if (d[i]) d[i].classList.remove('on');
    i = (n + s.length) % s.length;
    s[i].classList.add('active'); if (d[i]) d[i].classList.add('on');
  }
  function auto() { clearInterval(t); t = setInterval(function () { go(i + 1); }, 4500); }
  if (s.length > 1) {
    auto();
    d.forEach(function (x, n) { x.onclick = function () { go(n); auto(); }; });
    var p = $('#sl-prev'), nx = $('#sl-next');
    if (p) p.onclick = function () { go(i - 1); auto(); };
    if (nx) nx.onclick = function () { go(i + 1); auto(); };
  }

  /* ---- reading progress + back to top */
  var bar = $('#progress'), up = $('#to-top'), art = $('.article-body'), tick = false;
  function onScroll() {
    tick = false;
    var y = window.pageYOffset || document.documentElement.scrollTop;
    if (up) up.classList.toggle('on', y > 700);
    if (bar && art) {
      var r = art.getBoundingClientRect(), total = r.height - window.innerHeight * .5;
      bar.style.width = Math.max(0, Math.min(100, (-r.top / Math.max(total, 1)) * 100)) + '%';
    }
  }
  window.addEventListener('scroll', function () { if (!tick) { tick = true; requestAnimationFrame(onScroll); } }, { passive: true });
  if (up) up.onclick = function () { window.scrollTo({ top: 0, behavior: 'smooth' }); };

  /* ---- comments: name + comment, moderated, like the big e-newspapers (backend = Code.gs) */
  var cs = $('#comments');
  if (cs) (function () {
    var art = cs.dataset.article, list = $('#cm-list'), form = $('.cm-form', cs), msg = $('#cm-msg'), cnt = $('#cm-count'), left = $('#cm-left');
    var shown = 8, data = [], t0 = Date.now(), mineKey = 'np-mine-' + art;
    var el = function (tag, cls, txt) { var x = document.createElement(tag); if (cls) x.className = cls; if (txt != null) x.textContent = txt; return x; };
    function ago(ts) {
      var s = Math.max(1, Math.floor((Date.now() - ts) / 1000));
      if (s < 60) return 'الآن'; var m = Math.floor(s / 60); if (m < 60) return 'منذ ' + m + ' د';
      var h = Math.floor(m / 60); if (h < 24) return 'منذ ' + h + ' س'; var d = Math.floor(h / 24);
      if (d < 30) return 'منذ ' + d + ' يوم'; return new Date(ts).toLocaleDateString('ar-u-nu-latn');
    }
    function item(c, pending) {
      var li = el('div', 'cm' + (pending ? ' pending' : '')), av = el('div', 'cm-av', (c.name || '؟').trim().charAt(0).toUpperCase()), bd = el('div', 'cm-body');
      var hd = el('div', 'cm-head'); hd.appendChild(el('b', '', c.name)); hd.appendChild(el('span', '', pending ? 'قيد المراجعة' : ago(c.ts)));
      bd.appendChild(hd); bd.appendChild(el('p', '', c.text)); li.appendChild(av); li.appendChild(bd); return li;
    }
    function draw() {
      list.textContent = '';
      var mine = []; try { mine = JSON.parse(store.get(mineKey) || '[]'); } catch (e) {}
      mine.forEach(function (c) { list.appendChild(item(c, true)); });
      if (!data.length && !mine.length) list.appendChild(el('p', 'muted', 'لا توجد تعليقات بعد. كن أول من يعلّق على هذا المقال.'));
      data.slice(0, shown).forEach(function (c) { list.appendChild(item(c, false)); });
      if (data.length > shown) { var more = el('button', 'btn alt', 'عرض المزيد من التعليقات'); more.type = 'button'; more.onclick = function () { shown += 10; draw(); }; list.appendChild(more); }
      cnt.textContent = data.length ? '(' + data.length + ')' : '';
    }
    function loadList() {
      if (!api) { list.textContent = ''; list.appendChild(el('p', 'muted', 'خدمة التعليقات قيد التفعيل.')); return; }
      fetch(api + (api.indexOf('?') > -1 ? '&' : '?') + 'action=comments&article=' + encodeURIComponent(art))
        .then(function (r) { return r.json(); }).then(function (j) { data = j.comments || []; draw(); })
        .catch(function () { list.textContent = ''; list.appendChild(el('p', 'muted', 'تعذّر تحميل التعليقات الآن.')); });
    }
    inView(cs, loadList, '500px');
    form.elements.text.addEventListener('input', function () { left.textContent = 1000 - form.elements.text.value.length; });
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var f = form.elements, name = f.name.value.trim(), text = f.text.value.trim(), em = f.email.value.trim();
      if (!api) { say(msg, 'خدمة التعليقات قيد التفعيل حاليًا.', false); return; }
      if (name.length < 2) { say(msg, 'يرجى كتابة اسمك.', false); return; }
      if (text.length < 3) { say(msg, 'يرجى كتابة تعليقك.', false); return; }
      if (em && !okMail(em)) { say(msg, 'البريد الإلكتروني غير صحيح.', false); return; }
      if (!f.agree.checked) { say(msg, 'يرجى الموافقة على شروط النشر.', false); return; }
      var last = +store.get('np-last-cm') || 0;
      if (Date.now() - last < 30000) { say(msg, 'يرجى الانتظار قليلًا قبل إرسال تعليق آخر.', false); return; }
      var btn = form.querySelector('button[type=submit]'); btn.disabled = true; say(msg, 'جارٍ الإرسال…', true);
      post({ type: 'comment', article: art, name: name, email: em, text: text, hp: f.hp.value, t: Date.now() - t0 }).then(function (j) {
        if (!j.ok) throw new Error(j.error || 'failed');
        store.set('np-last-cm', String(Date.now())); store.set('np-name', name);
        if (j.status === 'approved') { data.unshift({ name: name, text: text, ts: Date.now() }); say(msg, 'تم نشر تعليقك. شكرًا لمشاركتك!', true); }
        else if (j.status === 'blocked') { say(msg, 'لم يُقبل التعليق لمخالفته شروط النشر.', false); }
        else {
          var mine = []; try { mine = JSON.parse(store.get(mineKey) || '[]'); } catch (e) {}
          mine.unshift({ name: name, text: text }); store.set(mineKey, JSON.stringify(mine.slice(0, 3)));
          say(msg, 'شكرًا لك! تم استلام تعليقك وسيظهر بعد مراجعته من طرف هيئة التحرير.', true);
        }
        f.text.value = ''; f.agree.checked = false; left.textContent = '1000'; draw();
      }).catch(function (e) {
        say(msg, e.message === 'wait' ? 'يرجى الانتظار قليلًا قبل إرسال تعليق آخر.' : e.message === 'too fast' ? 'أعد المحاولة بعد لحظات.' : 'تعذّر إرسال التعليق الآن، حاول لاحقًا.', false);
      }).then(function () { btn.disabled = false; });
    });
    if (store.get('np-name')) form.elements.name.value = store.get('np-name');
  })();

  /* ---- share buttons */
  $$('.share button').forEach(function (b) {
    b.onclick = function () {
      var url = location.href.split('#')[0], ttl = document.title, net = b.dataset.net, e = encodeURIComponent;
      var map = {
        whatsapp: 'https://wa.me/?text=' + e(ttl + ' ' + url),
        facebook: 'https://www.facebook.com/sharer/sharer.php?u=' + e(url),
        x: 'https://twitter.com/intent/tweet?text=' + e(ttl) + '&url=' + e(url),
        telegram: 'https://t.me/share/url?url=' + e(url) + '&text=' + e(ttl)
      };
      if (net === 'copy') {
        var done = function () { var o = b.textContent; b.textContent = 'تم النسخ ✓'; setTimeout(function () { b.textContent = o; }, 1800); };
        if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done); else done();
      } else window.open(map[net], '_blank', 'noopener,width=620,height=560');
    };
  });

  /* ---- POST to the Google Apps Script backend (text/plain avoids a CORS preflight) */
  function post(payload) {
    return fetch(api, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json(); });
  }

  /* ---- send a form through FormSubmit (arrives in the newspaper's Gmail) */
  function formsubmit(email, payload) {
    payload._captcha = 'false'; payload._template = 'table';
    return fetch('https://formsubmit.co/ajax/' + encodeURIComponent(email), {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && (j.success === false || j.success === 'false')) throw new Error(j.message || 'failed');
      return j;
    });
  }
  function say(el, txt, ok) { if (!el) return; el.textContent = txt; el.className = el.className.replace(/\b(ok|err)\b/g, '').trim() + ' ' + (ok ? 'ok' : 'err'); }
  function okMail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v); }

  /* ---- newsletter */
  $$('.nl-form').forEach(function (f) {
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var em = f.elements.email.value.trim(), msg = f.parentNode.querySelector('.nl-msg') || f.nextElementSibling;
      if (!okMail(em)) { say(msg, 'يرجى كتابة بريد إلكتروني صحيح.', false); return; }
      if (f.elements._honey && f.elements._honey.value) return;
      var btn = f.querySelector('button'); btn.disabled = true;
      var ok = function () { say(msg, 'شكرًا لاشتراكك! ستصلك أخبار نكسوس بريس قريبًا.', true); f.reset(); store.set('np-sub', '1'); };
      var fail = function () { say(msg, 'تعذّر الاشتراك الآن، حاول لاحقًا أو راسلنا عبر صفحة «اتصل بنا».', false); };
      if (api) {
        post({ type: 'subscribe', email: em, hp: f.elements._honey ? f.elements._honey.value : '' }).then(function (j) { if (!j.ok) throw 0; ok(); }, fail)
          .then(function () { btn.disabled = false; });
      } else if (f.dataset.provider === 'buttondown') {
        fetch('https://buttondown.com/api/emails/embed-subscribe/' + encodeURIComponent(f.dataset.target), {
          method: 'POST', mode: 'no-cors', body: new URLSearchParams({ email: em, embed: '1' })
        }).then(ok, fail).then(function () { btn.disabled = false; });
      } else {
        formsubmit(f.dataset.target, { email: em, _subject: 'مشترك جديد في النشرة البريدية - نكسوس بريس', _replyto: em, message: 'اشتراك جديد في النشرة البريدية: ' + em })
          .then(ok, fail).then(function () { btn.disabled = false; });
      }
    });
  });

  /* ---- contact page */
  var cf = $('#contact-form');
  if (cf) {
    var mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent), to = cf.dataset.email;
    $$('[data-mail]').forEach(function (a) { // phones: open the mail app instead of Gmail web
      if (mobile) { var sj = a.dataset.mail ? 'نكسوس بريس - ' + a.dataset.mail : 'تواصل مع نكسوس بريس'; a.href = 'mailto:' + to + '?subject=' + encodeURIComponent(sj); a.removeAttribute('target'); }
    });
    var cp = $('#ct-copy');
    if (cp) cp.onclick = function () {
      var o = cp.textContent, done = function () { cp.textContent = 'تم النسخ ✓'; setTimeout(function () { cp.textContent = o; }, 1800); };
      if (navigator.clipboard) navigator.clipboard.writeText(cp.dataset.email).then(done, done); else done();
    };
    cf.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var msg = $('#ct-msg'), v = function (n) { return cf.elements[n].value.trim(); };
      if (!v('name') || !okMail(v('email')) || !v('subject') || !v('message')) { say(msg, 'يرجى تعبئة جميع الحقول بشكل صحيح.', false); return; }
      if (cf.elements._honey.value) return;
      var btn = cf.querySelector('button[type=submit]'), mailto = 'mailto:' + to + '?subject=' + encodeURIComponent(v('subject')) +
        '&body=' + encodeURIComponent(v('message') + '\n\n' + v('name') + ' - ' + v('email'));
      var gmail = 'https://mail.google.com/mail/?view=cm&fs=1&to=' + encodeURIComponent(to) + '&su=' + encodeURIComponent(v('subject')) +
        '&body=' + encodeURIComponent(v('message') + '\n\n' + v('name') + ' - ' + v('email'));
      if (!api) { // no backend configured: open the visitor's mail client with everything filled in
        if (mobile) location.href = mailto; else window.open(gmail, '_blank', 'noopener');
        say(msg, 'تم فتح بريدك والرسالة جاهزة، اضغط «إرسال» هناك لإتمام الإرسال.', true); return;
      }
      btn.disabled = true; say(msg, 'جارٍ الإرسال…', true);
      post({ type: 'contact', name: v('name'), email: v('email'), subject: v('subject'), message: v('message'), hp: cf.elements._honey.value })
        .then(function (j) { if (!j.ok) throw 0; say(msg, 'تم إرسال رسالتك بنجاح. سنرد عليك قريبًا.', true); cf.reset(); })
        .catch(function () {
          say(msg, 'تعذّر الإرسال المباشر. ', false);
          var a = document.createElement('a'); a.href = mailto; a.textContent = 'اضغط هنا لإرسالها عبر تطبيق البريد'; msg.appendChild(a);
        }).then(function () { btn.disabled = false; });
    });
  }

  /* ---- daily poll (votes counted by counterapi.dev, one vote per browser) */
  $$('.poll[data-poll]').forEach(function (box) {
    var P, body = $('.poll-body', box);
    try { P = JSON.parse(box.dataset.poll); } catch (e) { return; }
    var api = 'https://api.counterapi.dev/v1/' + box.dataset.ns + '/', key = 'np-poll-' + P.id;
    var nm = function (n) { return 'p' + P.id.replace(/-/g, '') + 'o' + n; };
    var count = function (n) {
      return fetch(api + nm(n)).then(function (r) { return r.ok ? r.json() : {}; })
        .then(function (j) { return +(j.count || j.value || 0); }).catch(function () { return 0; });
    };
    var el = function (tag, cls, txt) { var x = document.createElement(tag); if (cls) x.className = cls; if (txt) x.textContent = txt; return x; };
    function question() { body.textContent = ''; body.appendChild(el('p', 'poll-q', P.q)); }
    function options() {
      question();
      P.o.forEach(function (o, n) {
        var b = el('button', 'poll-opt', o); b.type = 'button';
        b.onclick = function () {
          $$('.poll-opt', body).forEach(function (x) { x.disabled = true; });
          store.set(key, String(n));
          fetch(api + nm(n) + '/up').catch(function () {}).then(results);
        };
        body.appendChild(b);
      });
      var l = el('button', 'poll-link', 'عرض النتائج'); l.type = 'button'; l.onclick = results; body.appendChild(l);
    }
    function results() {
      question(); body.appendChild(el('p', 'poll-foot', 'جارٍ تحميل النتائج…'));
      Promise.all(P.o.map(function (_, n) { return count(n); })).then(function (c) {
        var tot = c.reduce(function (a, b) { return a + b; }, 0), mine = store.get(key);
        question();
        P.o.forEach(function (o, n) {
          var pc = tot ? Math.round(c[n] * 100 / tot) : 0, r = el('div', 'poll-res' + (String(n) === mine ? ' mine' : ''));
          r.appendChild(el('span', '', o + ' — ' + pc + '%' + (String(n) === mine ? ' ✓' : '')));
          var b = el('div', 'bar'), f = el('i'); f.style.width = pc + '%'; b.appendChild(f); r.appendChild(b); body.appendChild(r);
        });
        body.appendChild(el('p', 'poll-foot', tot ? 'عدد الأصوات: ' + tot + ' · يتجدد الاستطلاع كل يوم' : 'كن أول من يصوّت اليوم · يتجدد الاستطلاع كل يوم'));
        if (mine === null) { var bk = el('button', 'poll-link', '← التصويت'); bk.type = 'button'; bk.onclick = options; body.appendChild(bk); }
      });
    }
    inView(box, function () { if (store.get(key) !== null) results(); else options(); }, '200px');
  });

  /* ---- weather / prayer times / search live in tools.js (loaded only when needed) */
  var need = $('#wx-app, #search-app'), mini = $('.wx-mini');
  function loadTools() {
    if (window.__npTools) return; window.__npTools = 1;
    var sc = document.createElement('script'); sc.src = pre + 'tools.js'; sc.defer = true; document.body.appendChild(sc);
  }
  if (need) loadTools(); else if (mini) inView(mini, loadTools, '300px');

  /* ---- service worker: instant repeat visits */
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () { navigator.serviceWorker.register(pre + 'sw.js').catch(function () {}); });
  }
})();

function googleTranslateElementInit() {
  new google.translate.TranslateElement({ pageLanguage: 'ar', includedLanguages: 'ar,fr,en', autoDisplay: false }, 'google_translate_element');
}
