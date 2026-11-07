/* Language switcher (Google Translate) + hero slider */
(function () {
  var m = document.cookie.match(/googtrans=\/ar\/(\w+)/), cur = m ? m[1] : 'ar';
  if (cur !== 'ar') { document.documentElement.dir = 'ltr'; document.documentElement.lang = cur; }
  document.querySelectorAll('.lang-btn').forEach(function (b) {
    if (b.dataset.l === cur) b.classList.add('on');
    b.onclick = function () {
      var l = b.dataset.l, h = location.hostname, past = 'expires=Thu, 01 Jan 1970 00:00:00 GMT';
      if (l === 'ar') {
        document.cookie = 'googtrans=;path=/;' + past;
        document.cookie = 'googtrans=;path=/;domain=' + h + ';' + past;
      } else {
        document.cookie = 'googtrans=/ar/' + l + ';path=/';
        document.cookie = 'googtrans=/ar/' + l + ';path=/;domain=' + h;
      }
      location.reload();
    };
  });

  var s = document.querySelectorAll('.slide'), d = document.querySelectorAll('.dot'), i = 0, t;
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
    var p = document.getElementById('sl-prev'), nx = document.getElementById('sl-next');
    if (p) p.onclick = function () { go(i - 1); auto(); };
    if (nx) nx.onclick = function () { go(i + 1); auto(); };
  }
})();
function googleTranslateElementInit() {
  new google.translate.TranslateElement({ pageLanguage: 'ar', includedLanguages: 'ar,fr,en', autoDisplay: false }, 'google_translate_element');
}
