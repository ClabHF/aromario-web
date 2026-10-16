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

  // El día en Aromario: la página se detiene y lo que se desliza es la captura dentro del teléfono.
  // Cuando la captura llega a su final, la página sigue bajando (y al revés al subir).
  var story = document.querySelector('.story');
  if (!story) return;
  var img = story.querySelector('.screen img');
  var screen = story.querySelector('.screen');
  var steps = Array.prototype.slice.call(story.querySelectorAll('.story-steps li'));
  var bar = story.querySelector('.progress i');
  var now = story.querySelector('.story-now');
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
