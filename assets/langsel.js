/* Aromario — selector de idioma (botón de tres barras). La elección se guarda en
   localStorage "aromario_lang"; "Automático" vuelve al idioma del navegador. */
(function () {
  var KEY = "aromario_lang";
  function save(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  document.querySelectorAll(".langsel").forEach(function (root) {
    var btn = root.querySelector(".langsel-btn"), menu = root.querySelector(".langsel-menu");
    if (!btn || !menu) return;
    function close() { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); }
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var open = menu.hidden;
      menu.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      if (open) { var f = menu.querySelector("[role=menuitem]"); if (f) f.focus(); }
    });
    document.addEventListener("click", function (ev) { if (!root.contains(ev.target)) close(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { close(); btn.focus(); } });
    // La lista compartida (?v=…&i=…) viaja con el cambio de idioma.
    menu.querySelectorAll("a[data-langsel]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        save(a.getAttribute("data-langsel"));
        if (a.classList.contains("current")) { ev.preventDefault(); close(); return; }
        if (location.search) { ev.preventDefault(); location.href = a.getAttribute("href") + location.search + location.hash; }
      });
    });
    var auto = menu.querySelector('[data-langsel="auto"]');
    if (auto) auto.addEventListener("click", function () {
      save("auto");
      var n = (navigator.language || "").toLowerCase().slice(0, 2);
      var a = menu.querySelector('a[data-langsel="' + n + '"]') || menu.querySelector('a[data-langsel="es"]');
      if (a && !a.classList.contains("current")) location.href = a.getAttribute("href") + location.search + location.hash;
      else close();
    });
  });
})();
