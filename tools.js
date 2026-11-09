/* Nexus Press - tools: weather + prayer times for any city in the world, and site search.
   APIs (free, no key): Open-Meteo (geocoding + forecast), Aladhan (prayer times), BigDataCloud (reverse geocode for "my location"). */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var pre = document.body.getAttribute('data-pre') || '';
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function jget(url, ttl) {
    var k = 'npc:' + url, now = Date.now();
    try { var c = JSON.parse(sessionStorage.getItem(k) || 'null'); if (c && now - c.t < ttl) return Promise.resolve(c.d); } catch (e) {}
    return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      try { sessionStorage.setItem(k, JSON.stringify({ t: now, d: d })); } catch (e) {}
      return d;
    });
  }
  var NUM = 'ar-u-nu-latn';

  /* =========================================================== weather & prayer */
  var GEO = 'https://geocoding-api.open-meteo.com/v1/search', WX = 'https://api.open-meteo.com/v1/forecast', PR = 'https://api.aladhan.com/v1/timings/';
  var WMO = {
    0: ['صافٍ', '☀️', '🌙'], 1: ['صافٍ غالبًا', '🌤️', '🌙'], 2: ['غائم جزئيًا', '⛅', '☁️'], 3: ['غائم', '☁️', '☁️'],
    45: ['ضباب', '🌫️'], 48: ['ضباب صقيعي', '🌫️'], 51: ['رذاذ خفيف', '🌦️'], 53: ['رذاذ', '🌦️'], 55: ['رذاذ كثيف', '🌧️'],
    56: ['رذاذ متجمد', '🌧️'], 57: ['رذاذ متجمد', '🌧️'], 61: ['مطر خفيف', '🌦️'], 63: ['مطر', '🌧️'], 65: ['مطر غزير', '🌧️'],
    66: ['مطر متجمد', '🌧️'], 67: ['مطر متجمد', '🌧️'], 71: ['ثلوج خفيفة', '🌨️'], 73: ['ثلوج', '❄️'], 75: ['ثلوج كثيفة', '❄️'],
    77: ['حبيبات ثلجية', '❄️'], 80: ['زخات مطر', '🌦️'], 81: ['زخات مطر', '🌧️'], 82: ['زخات غزيرة', '⛈️'],
    85: ['زخات ثلج', '🌨️'], 86: ['زخات ثلج كثيفة', '🌨️'], 95: ['عاصفة رعدية', '⛈️'], 96: ['عاصفة رعدية وبرَد', '⛈️'], 99: ['عاصفة رعدية وبرَد', '⛈️']
  };
  function wc(code, day) { var w = WMO[code] || ['—', '🌡️']; return { t: w[0], e: (day === 0 && w[2]) ? w[2] : w[1] }; }
  var PRAYERS = [['Fajr', 'الفجر'], ['Sunrise', 'الشروق'], ['Dhuhr', 'الظهر'], ['Asr', 'العصر'], ['Maghrib', 'المغرب'], ['Isha', 'العشاء']];
  var COUNTING = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
  var CHIPS = [
    { n: 'الرباط', c: 'المغرب', cc: 'MA', lat: 34.0209, lon: -6.8416 }, { n: 'الدار البيضاء', c: 'المغرب', cc: 'MA', lat: 33.5731, lon: -7.5898 },
    { n: 'طنجة', c: 'المغرب', cc: 'MA', lat: 35.7595, lon: -5.834 }, { n: 'مراكش', c: 'المغرب', cc: 'MA', lat: 31.6295, lon: -7.9811 },
    { n: 'مكة المكرمة', c: 'السعودية', cc: 'SA', lat: 21.4225, lon: 39.8262 }, { n: 'المدينة المنورة', c: 'السعودية', cc: 'SA', lat: 24.4686, lon: 39.6142 },
    { n: 'القاهرة', c: 'مصر', cc: 'EG', lat: 30.0444, lon: 31.2357 }, { n: 'دبي', c: 'الإمارات', cc: 'AE', lat: 25.2048, lon: 55.2708 },
    { n: 'إسطنبول', c: 'تركيا', cc: 'TR', lat: 41.0082, lon: 28.9784 }, { n: 'باريس', c: 'فرنسا', cc: 'FR', lat: 48.8566, lon: 2.3522 },
    { n: 'لندن', c: 'بريطانيا', cc: 'GB', lat: 51.5072, lon: -0.1276 }, { n: 'نيويورك', c: 'أمريكا', cc: 'US', lat: 40.7128, lon: -74.006 }
  ];
  var METHODS = [['auto', 'تلقائي حسب البلد'], ['21', 'المغرب (وزارة الأوقاف)'], ['4', 'أم القرى (مكة)'], ['3', 'رابطة العالم الإسلامي'], ['5', 'الهيئة المصرية'], ['2', 'أمريكا الشمالية (ISNA)'], ['1', 'كراتشي']];
  var timer = null, current = null;

  function label(c) { return c.n + (c.a && c.a !== c.n ? '، ' + c.a : '') + (c.c ? '، ' + c.c : ''); }
  function fromGeo(r) { return { n: r.name, a: r.admin1, c: r.country, cc: r.country_code, lat: r.latitude, lon: r.longitude, tz: r.timezone }; }
  function geocode(q) { return jget(GEO + '?name=' + encodeURIComponent(q) + '&count=7&language=ar&format=json', 3600000).then(function (j) { return j.results || []; }); }
  function fmtT(sec) { sec = Math.max(0, Math.floor(sec)); var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60, p = function (n) { return (n < 10 ? '0' : '') + n; }; return p(h) + ':' + p(m) + ':' + p(s); }

  function suggest(input, ul, pick) {
    var tm;
    input.addEventListener('input', function () {
      clearTimeout(tm); var q = input.value.trim();
      if (q.length < 2) { ul.classList.remove('on'); return; }
      tm = setTimeout(function () {
        geocode(q).then(function (rs) {
          ul.innerHTML = rs.map(function (r, i) { return '<li data-i="' + i + '">' + esc(label(fromGeo(r))) + '</li>'; }).join('') || '<li>لا توجد نتائج</li>';
          ul.classList.add('on');
          $$('li[data-i]', ul).forEach(function (li) { li.onclick = function () { ul.classList.remove('on'); input.value = ''; pick(fromGeo(rs[+li.dataset.i])); }; });
        }).catch(function () { ul.classList.remove('on'); });
      }, 250);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return; e.preventDefault();
      var q = input.value.trim(); if (q.length < 2) return;
      geocode(q).then(function (rs) { if (rs[0]) { ul.classList.remove('on'); input.value = ''; pick(fromGeo(rs[0])); } });
    });
    document.addEventListener('click', function (e) { if (e.target !== input && !ul.contains(e.target)) ul.classList.remove('on'); });
  }

  function locate(pick, say) {
    if (!navigator.geolocation) { say('متصفحك لا يدعم تحديد الموقع.'); return; }
    say('جارٍ تحديد موقعك…');
    navigator.geolocation.getCurrentPosition(function (p) {
      var c = { n: 'موقعي', lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4) };
      jget('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=' + c.lat + '&longitude=' + c.lon + '&localityLanguage=ar', 86400000)
        .then(function (j) { c.n = j.city || j.locality || j.principalSubdivision || 'موقعي'; c.c = j.countryName; c.cc = j.countryCode; })
        .catch(function () {}).then(function () { pick(c); });
    }, function () { say('تعذّر تحديد موقعك. اكتب اسم المدينة بدلًا من ذلك.'); }, { timeout: 10000, maximumAge: 600000 });
  }

  function getWeather(c) {
    return jget(WX + '?latitude=' + c.lat + '&longitude=' + c.lon +
      '&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day' +
      '&hourly=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max' +
      '&forecast_days=7&timezone=auto', 600000);
  }
  function getPrayer(c, off, method) {
    var n = new Date(Date.now() + off * 1000), p = function (x) { return (x < 10 ? '0' : '') + x; };
    var u = PR + p(n.getUTCDate()) + '-' + p(n.getUTCMonth() + 1) + '-' + n.getUTCFullYear() + '?latitude=' + c.lat + '&longitude=' + c.lon;
    if (c.tz) u += '&timezonestring=' + encodeURIComponent(c.tz);
    var m = method === 'auto' ? (c.cc === 'MA' ? '21' : '') : method;
    if (m) u += '&method=' + m;
    return jget(u, 1800000);
  }
  function hm(t) { return String(t || '').split(' ')[0]; }
  function toMin(t) { var a = hm(t).split(':'); return (+a[0]) * 60 + (+a[1]); }
  function nextPrayer(times, off) {
    var n = new Date(Date.now() + off * 1000), now = n.getUTCHours() * 3600 + n.getUTCMinutes() * 60 + n.getUTCSeconds();
    for (var i = 0; i < COUNTING.length; i++) { var s = toMin(times[COUNTING[i]]) * 60; if (s > now) return { k: COUNTING[i], left: s - now }; }
    return { k: 'Fajr', left: toMin(times.Fajr) * 60 + 86400 - now };
  }
  function pname(k) { for (var i = 0; i < PRAYERS.length; i++) if (PRAYERS[i][0] === k) return PRAYERS[i][1]; return k; }

  function tickers() {
    clearInterval(timer);
    timer = setInterval(function () {
      if (!current || !current.times) return;
      var nx = nextPrayer(current.times, current.off);
      $$('.cd').forEach(function (x) { x.textContent = fmtT(nx.left); });
      $$('.nx-name').forEach(function (x) { x.textContent = pname(nx.k); });
      $$('.nx-time').forEach(function (x) { x.textContent = hm(current.times[nx.k]); });
      $$('.pr-grid div').forEach(function (d) { d.classList.toggle('on', d.dataset.k === nx.k); });
    }, 1000);
  }

  function renderFull(out, c, w, pr, method) {
    var cu = w.current, dl = w.daily, off = w.utc_offset_seconds || 0, cw = wc(cu.weather_code, cu.is_day);
    var cityNow = new Date(Date.now() + off * 1000), nowStr = cu.time;
    var hrs = '', k = 0;
    for (var i = 0; i < w.hourly.time.length && k < 24; i++) {
      if (w.hourly.time[i] >= nowStr.slice(0, 13) + ':00') {
        var hw = wc(w.hourly.weather_code[i], w.hourly.is_day[i]);
        hrs += '<div><span>' + w.hourly.time[i].slice(11, 16) + '</span><span style="font-size:22px;display:block">' + hw.e + '</span><b>' + Math.round(w.hourly.temperature_2m[i]) + '°</b></div>'; k++;
      }
    }
    var days = dl.time.map(function (d, i) {
      var dw = wc(dl.weather_code[i], 1), name = i === 0 ? 'اليوم' : new Date(d + 'T12:00:00Z').toLocaleDateString('ar-u-nu-latn', { weekday: 'long', timeZone: 'UTC' });
      return '<div><div class="d">' + name + '</div><div class="e">' + dw.e + '</div><b>' + Math.round(dl.temperature_2m_max[i]) + '°</b> / ' + Math.round(dl.temperature_2m_min[i]) + '°<div class="muted">' + dw.t + '</div></div>';
    }).join('');
    var html = '<div class="wx-now"><div><div class="m-city">📍 ' + esc(label(c)) + '</div><div class="ico">' + cw.e + '</div><div class="big">' + Math.round(cu.temperature_2m) + '°C</div><div>' + cw.t + '</div></div><ul>' +
      '<li>🌡️ الإحساس: ' + Math.round(cu.apparent_temperature) + '°</li><li>💧 الرطوبة: ' + cu.relative_humidity_2m + '%</li>' +
      '<li>💨 الرياح: ' + Math.round(cu.wind_speed_10m) + ' كم/س</li><li>☔ احتمال المطر: ' + (dl.precipitation_probability_max[0] == null ? '—' : dl.precipitation_probability_max[0] + '%') + '</li>' +
      '<li>⬆️ العظمى: ' + Math.round(dl.temperature_2m_max[0]) + '°</li><li>⬇️ الصغرى: ' + Math.round(dl.temperature_2m_min[0]) + '°</li>' +
      '<li>🌅 الشروق: ' + dl.sunrise[0].slice(11, 16) + '</li><li>🌇 الغروب: ' + dl.sunset[0].slice(11, 16) + '</li>' +
      '<li style="grid-column:1/-1">🕒 الوقت المحلي: ' + cityNow.toLocaleTimeString(NUM, { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + '</li></ul></div>' +
      '<h3 class="wx-h">الساعات القادمة</h3><div class="wx-hours">' + hrs + '</div><h3 class="wx-h">توقعات 7 أيام</h3><div class="wx-days">' + days + '</div>';
    if (pr && pr.data) {
      var t = pr.data.timings, hj = pr.data.date && pr.data.date.hijri, nx = nextPrayer(t, off);
      current.times = t; current.off = off;
      html += '<h3 class="wx-h">🕌 مواقيت الصلاة</h3><div class="pr-head"><b>' + (hj ? esc(hj.weekday.ar + ' ' + hj.day + ' ' + hj.month.ar + ' ' + hj.year + ' هـ') : '') + '</b>' +
        '<label>طريقة الحساب: <select id="pr-method">' + METHODS.map(function (m) { return '<option value="' + m[0] + '"' + (m[0] === method ? ' selected' : '') + '>' + m[1] + '</option>'; }).join('') + '</select></label></div>' +
        '<div class="pr-next"><span>الصلاة القادمة: <span class="nx-name">' + pname(nx.k) + '</span> (<span class="nx-time">' + hm(t[nx.k]) + '</span>)</span><span>بعد <span class="cd">' + fmtT(nx.left) + '</span></span></div>' +
        '<div class="pr-grid">' + PRAYERS.map(function (p) { return '<div data-k="' + p[0] + '"' + (p[0] === nx.k ? ' class="on"' : '') + '>' + p[1] + '<b>' + hm(t[p[0]]) + '</b></div>'; }).join('') + '</div>';
    } else html += '<p class="muted">تعذّر تحميل مواقيت الصلاة الآن، حاول لاحقًا.</p>';
    html += '<p class="src-note">مصادر البيانات: Open-Meteo للطقس وAladhan لمواقيت الصلاة. المعلومات تقريبية، وللدقة في المواقيت يُرجى مراجعة الجهات الرسمية في بلدك. جميع الأوقات بتوقيت المدينة المختارة.</p>';
    out.innerHTML = html; tickers();
    var sel = $('#pr-method', out);
    if (sel) sel.onchange = function () { store.set('np-method', sel.value); load(c, false); };
  }

  function renderMini(out, c, w, pr) {
    var cu = w.current, cw = wc(cu.weather_code, cu.is_day), off = w.utc_offset_seconds || 0;
    var html = '<div class="m-top"><div><div class="m-city">📍 ' + esc(c.n) + '</div><div class="m-temp">' + Math.round(cu.temperature_2m) + '°</div><div class="muted">' + cw.t + ' · ' + w.daily.temperature_2m_max[0] + '° / ' + w.daily.temperature_2m_min[0] + '°</div></div><div class="m-ico">' + cw.e + '</div></div>';
    if (pr && pr.data) {
      current.times = pr.data.timings; current.off = off; var nx = nextPrayer(current.times, off);
      html += '<div class="m-next">🕌 <span class="nx-name">' + pname(nx.k) + '</span> <span class="nx-time">' + hm(current.times[nx.k]) + '</span> · بعد <span class="cd">' + fmtT(nx.left) + '</span></div>';
    }
    out.innerHTML = html + '<a class="m-more" href="' + pre + 'weather.html">التفاصيل الكاملة والمواقيت ←</a>'; tickers();
  }

  function load(c, remember) {
    current = { city: c };
    if (remember !== false) store.set('np-city', JSON.stringify(c));
    var full = $('#wx-out'), mini = $('.wx-mini-out'), method = store.get('np-method') || 'auto';
    var holders = [full, mini].filter(Boolean);
    holders.forEach(function (h) { h.innerHTML = '<p class="muted">جارٍ تحميل البيانات…</p>'; });
    getWeather(c).then(function (w) {
      if (w.timezone && !c.tz) c.tz = w.timezone;
      return getPrayer(c, w.utc_offset_seconds || 0, method).catch(function () { return null; }).then(function (pr) {
        if (full) renderFull(full, c, w, pr, method);
        if (mini) renderMini(mini, c, w, pr);
      });
    }).catch(function () { holders.forEach(function (h) { h.innerHTML = '<p class="muted">تعذّر تحميل الطقس الآن. تحقق من الاتصال وحاول مرة أخرى.</p>'; }); });
  }

  var saved = null; try { saved = JSON.parse(store.get('np-city') || 'null'); } catch (e) {}
  var pick = function (c) { load(c); };
  var mq = $('.wx-mini-q');
  if (mq) {
    var msay = function (t) { var o = $('.wx-mini-out'); if (o) o.innerHTML = '<p class="muted">' + esc(t) + '</p>'; };
    suggest(mq, $('.wx-sug', mq.parentNode), pick);
    $('.wx-geo', mq.parentNode).onclick = function () { locate(pick, msay); };
    if (saved) load(saved, false);
  }
  var fq = $('#wx-q');
  if (fq) {
    suggest(fq, $('#wx-sug'), pick);
    $('#wx-geo').onclick = function () { locate(pick, function (t) { $('#wx-out').innerHTML = '<p class="muted">' + esc(t) + '</p>'; }); };
    var chips = $('#wx-chips');
    chips.innerHTML = CHIPS.map(function (c, i) { return '<button type="button" data-i="' + i + '">' + c.n + '</button>'; }).join('');
    $$('button', chips).forEach(function (b) { b.onclick = function () { pick(CHIPS[+b.dataset.i]); }; });
    var qs = new URLSearchParams(location.search).get('city');
    if (qs) geocode(qs).then(function (rs) { load(rs[0] ? fromGeo(rs[0]) : saved || CHIPS[0]); });
    else load(saved || CHIPS[0], !!saved);
  }

  /* =========================================================== search */
  var sapp = $('#search-app');
  if (sapp) {
    var norm = function (s) {
      return String(s || '').toLowerCase().replace(/[\u064B-\u065F\u0670\u0640]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').replace(/[^\u0600-\u06FFa-z0-9\s]/g, ' ');
    };
    var out = $('#search-out'), input = $('#sq'), idx = null;
    var run = function () {
      var q = norm(input.value).split(/\s+/).filter(function (x) { return x.length > 1; });
      if (!idx) return;
      if (!q.length) { out.innerHTML = '<p class="muted">اكتب كلمة للبحث في المقالات.</p>'; return; }
      var rows = idx.map(function (a) {
        var t = norm(a.t), s = norm(a.s + ' ' + a.c), sc = 0, hit = 0;
        q.forEach(function (w) { if (t.indexOf(w) > -1) { sc += 3; hit++; } else if (s.indexOf(w) > -1) { sc += 1; hit++; } });
        return { a: a, sc: sc, hit: hit };
      }).filter(function (r) { return r.hit === q.length; }).sort(function (x, y) { return y.sc - x.sc || (y.a.d > x.a.d ? 1 : -1); });
      out.innerHTML = rows.length ? rows.map(function (r) {
        var a = r.a;
        return '<a class="card" href="' + pre + 'articles/' + esc(a.i) + '.html"><img loading="lazy" decoding="async" width="480" height="270" src="' + pre + esc(a.m) + '" alt="' + esc(a.t) + '"><div class="info"><span class="badge">' + esc(a.c) + '</span><h3>' + esc(a.t) + '</h3><p>' + esc(a.d) + '</p></div></a>';
      }).join('') : '<p class="muted">لا توجد نتائج مطابقة. جرّب كلمات أخرى.</p>';
    };
    input.value = new URLSearchParams(location.search).get('q') || '';
    fetch(pre + 'search.json').then(function (r) { return r.json(); }).then(function (j) { idx = j; run(); }).catch(function () { out.innerHTML = '<p class="muted">تعذّر تحميل فهرس البحث.</p>'; });
    input.addEventListener('input', run);
  }
})();
