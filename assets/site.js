/* AROMARIO — comportamiento del sitio (sin librerías) */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Barra superior: cristal al hacer scroll
  var nav = document.querySelector('.nav');
  function onNav() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 8); }
  window.addEventListener('scroll', onNav, { passive: true }); onNav();

  // Menú del móvil
  var menu = document.getElementById('mobile-menu');
  var openBtn = document.getElementById('menu-open');
  var closeBtn = document.getElementById('menu-close');
  function setMenu(open) {
    if (!menu) return;
    menu.classList.toggle('open', open);
    menu.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (openBtn) openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.documentElement.style.overflow = open ? 'hidden' : '';
    if (open && closeBtn) closeBtn.focus();
  }
  if (openBtn) openBtn.addEventListener('click', function () { setMenu(true); });
  if (closeBtn) closeBtn.addEventListener('click', function () { setMenu(false); });
  if (menu) menu.addEventListener('click', function (e) { if (e.target.closest('a')) setMenu(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setMenu(false); });

  // Idioma: se recuerda la elección (antes, con el teléfono en inglés no se podía volver al español)
  document.querySelectorAll('[data-lang]').forEach(function (a) {
    a.addEventListener('click', function () { try { localStorage.setItem('aromario_lang', a.getAttribute('data-lang')); } catch (e) {} });
  });

  // Galería: flechas
  var gal = document.querySelector('.gallery');
  document.querySelectorAll('[data-gal]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!gal) return;
      var step = (gal.querySelector('figure') || { offsetWidth: 260 }).offsetWidth + 24;
      gal.scrollBy({ left: b.getAttribute('data-gal') === 'next' ? step : -step, behavior: reduce ? 'auto' : 'smooth' });
    });
  });


  var fine = window.matchMedia && window.matchMedia('(hover:hover)').matches;
  var raf = window.requestAnimationFrame || function (f) { return setTimeout(f, 16); };

  // Aparición suave al hacer scroll, también en navegadores sin animation-timeline
  var hasTimeline = window.CSS && CSS.supports && CSS.supports('animation-timeline: view()');
  if (!reduce && !hasTimeline && 'IntersectionObserver' in window) {
    var rio = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); rio.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('.rise').forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.top < window.innerHeight) return;
      el.classList.remove('rise'); el.classList.add('rise-fallback'); rio.observe(el);
    });
  }

  // Reflejo de cristal que sigue al dedo o al mouse
  if (!reduce) {
    document.querySelectorAll('.tile,.guide,.step,.float-card').forEach(function (el) {
      el.classList.add('shine');
      function move(e) {
        var r = el.getBoundingClientRect();
        el.style.setProperty('--mx', (e.clientX - r.left).toFixed(0) + 'px');
        el.style.setProperty('--my', (e.clientY - r.top).toFixed(0) + 'px');
        el.classList.add('lit');
      }
      function off() { el.classList.remove('lit'); }
      el.addEventListener('pointermove', move, { passive: true });
      el.addEventListener('pointerdown', move, { passive: true });
      el.addEventListener('pointerleave', off);
      el.addEventListener('pointerup', function (e) { if (e.pointerType !== 'mouse') setTimeout(off, 350); });
      el.addEventListener('pointercancel', off);
    });
  }

  // Parallax discreto en el hero
  var par = Array.prototype.slice.call(document.querySelectorAll('.hero .halo,.hero .float-card'));
  if (!reduce && par.length && fine) {
    var pTick = false;
    var depth = par.map(function (el) { return el.classList.contains('halo') ? 0.06 : el.classList.contains('fc-pick') ? -0.05 : 0.09; });
    var onPar = function () {
      if (pTick) return; pTick = true;
      raf(function () {
        pTick = false;
        var y = window.scrollY;
        if (y > window.innerHeight * 1.2) return;
        par.forEach(function (el, i) { el.style.translate = '0 ' + (y * depth[i]).toFixed(1) + 'px'; });
      });
    };
    window.addEventListener('scroll', onPar, { passive: true });
  }

  // Videos dentro del teléfono: solo se reproducen mientras se ven
  var vids = Array.prototype.slice.call(document.querySelectorAll('video[data-loop]'));
  if (vids.length) {
    if (reduce || !('IntersectionObserver' in window)) {
      vids.forEach(function (v) { v.removeAttribute('autoplay'); v.pause(); });
    } else {
      var vio = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          var v = e.target;
          if (e.isIntersecting) { if (v.preload === 'none') v.preload = 'auto'; var pr = v.play(); if (pr && pr.catch) pr.catch(function () {}); }
          else v.pause();
        });
      }, { threshold: 0.35 });
      vids.forEach(function (v) { vio.observe(v); });
    }
  }

  // El día en Aromario: la página se detiene y lo que se desliza es la captura dentro del teléfono.
  // Cuando la captura llega a su final, la página sigue bajando (y al revés al subir).
  var story = document.querySelector('.story');
  if (!story) return;
  var img = story.querySelector('.screen img');
  var screen = story.querySelector('.screen');
  var steps = Array.prototype.slice.call(story.querySelectorAll('.story-steps li'));
  var bar = story.querySelector('.progress i');
  var now = story.querySelector('.story-now');
  var tod = story.querySelector('.tod');
  var todLabels = tod ? (tod.getAttribute('data-labels') || 'Morning|Afternoon|Night').split('|') : [];
  var root = document.documentElement;
  if (reduce) { story.classList.add('static'); return; }
  var travel = 0, start = 0, len = 1;

  function layout() {
    if (!img || !screen) return;
    var sh = screen.clientHeight;
    var ih = img.getBoundingClientRect().height;
    travel = Math.max(0, ih - sh);
    // Altura de la sección = pantalla + recorrido de la imagen (1 px de scroll = 1,1 px de imagen)
    var vh = window.innerHeight;
    story.style.height = Math.round(vh + travel / 1.1) + 'px';
    start = story.getBoundingClientRect().top + window.scrollY;
    len = Math.max(1, story.offsetHeight - vh);
    tick();
  }
  var lastStep = -1;
  function tick() {
    var p = Math.min(1, Math.max(0, (window.scrollY - start) / len));
    if (img) img.style.transform = 'translate3d(0,' + (-p * travel).toFixed(1) + 'px,0)';
    if (bar) bar.style.width = (p * 100).toFixed(1) + '%';
    // El fondo pasa de mañana a noche mientras recorres la pantalla, y vuelve suave al salir
    var after = window.scrollY - (start + len);
    var q = after > 0 ? Math.max(0, 1 - after / (window.innerHeight * 0.9)) * p : p;
    root.style.setProperty('--p', q.toFixed(3));
    if (tod) {
      var hh = 7 + p * 16, h = Math.floor(hh), m = Math.floor((hh - h) * 60 / 5) * 5;
      tod.querySelector('b').textContent = h + ':' + (m < 10 ? '0' : '') + m;
      tod.querySelector('span').textContent = todLabels[p < 0.34 ? 0 : p < 0.67 ? 1 : 2] || '';
    }
    var i = Math.min(steps.length - 1, Math.floor(p * steps.length * 0.999));
    if (i !== lastStep) {
      steps.forEach(function (li, k) { li.classList.toggle('on', k === i); });
      if (now && steps[i]) now.textContent = steps[i].querySelector('b').textContent;
      lastStep = i;
    }
  }
  var ticking = false;
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(function () { ticking = false; tick(); }); }
  }, { passive: true });
  // En el móvil la barra del navegador cambia la altura al hacer scroll: solo se recalcula si cambia el ancho.
  var lastW = window.innerWidth;
  window.addEventListener('resize', function () { if (window.innerWidth !== lastW) { lastW = window.innerWidth; layout(); } });
  if (img && !img.complete) img.addEventListener('load', layout); else layout();
  window.addEventListener('load', layout);
})();
