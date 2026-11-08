/* Language switcher (Google Translate, loaded only when needed) + hero slider + lazy comments */
(function () {
  var m = document.cookie.match(/googtrans=\/ar\/(\w+)/), cur = m ? m[1] : 'ar';
  if (cur !== 'ar') {
    document.documentElement.dir = 'ltr';
    document.documentElement.lang = cur;
    var gs = document.createElement('script');
    gs.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    gs.async = true;
    document.head.appendChild(gs);
  }
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

  var c = document.querySelector('.comments[data-repo]');
  if (c) {
    var loadComments = function () {
      if (c.dataset.loaded) return;
      c.dataset.loaded = '1';
      var u = document.createElement('script');
      u.src = 'https://utteranc.es/client.js';
      u.setAttribute('repo', c.dataset.repo);
      u.setAttribute('issue-term', 'pathname');
      u.setAttribute('label', 'comment');
      u.setAttribute('theme', 'github-light');
      u.crossOrigin = 'anonymous';
      u.async = true;
      c.appendChild(u);
    };
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries, o) {
        if (entries[0].isIntersecting) { loadComments(); o.disconnect(); }
      }, { rootMargin: '400px' }).observe(c);
    } else {
      loadComments();
    }
  }
})();

function googleTranslateElementInit() {
  new google.translate.TranslateElement({ pageLanguage: 'ar', includedLanguages: 'ar,fr,en', autoDisplay: false }, 'google_translate_element');
}
