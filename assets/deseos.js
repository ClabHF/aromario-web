/* Aromario — página de deseos compartidos (ES/EN). Lee ?ids=… y arma la lista solo con datos
   públicos: nombre y marca de data/perfumes-ligero.json y la foto de verified_photos.json.
   El enlace no lleva datos de la cuenta; la lista no se marca como comprada.
   Enlace corto (app 1.1.20+): ?v=1&i=… = índices en el orden canónico data/orden-v1.json (3 caracteres
   en base 36 por perfume) + 1 carácter de verificación. Los enlaces viejos con ?ids= siguen valiendo. */
(function () {
  var root = document.getElementById("wishlist");
  if (!root) return;
  var en = document.documentElement.lang === "en";
  var base = root.getAttribute("data-base") || "";
  var T = en
    ? { buy: "Buy", invalid: "This link is damaged or incomplete. Ask for it again.", empty: "This list is empty or the link is incomplete.", error: "We couldn't load the list. Try again in a moment.", count: function (n) { return n === 1 ? "1 perfume" : n + " perfumes"; } }
    : { buy: "Comprar", invalid: "Este enlace está dañado o incompleto. Pide que te lo envíen de nuevo.", empty: "Esta lista está vacía o el enlace está incompleto.", error: "No pudimos cargar la lista. Prueba de nuevo en un momento.", count: function (n) { return n === 1 ? "1 perfume" : n + " perfumes"; } };
  var CJ = "https://www.jdoqocy.com/click-101899442-15733833";

  function ids() {
    var raw = new URLSearchParams(location.search).get("ids") || "";
    var seen = {}, out = [];
    raw.split(",").forEach(function (s) {
      s = s.trim();
      if (/^[A-Za-z0-9._-]{1,160}$/.test(s) && !seen[s]) { seen[s] = 1; out.push(s); }
    });
    return out.slice(0, 200);
  }
  // Enlace corto: devuelve la lista de índices, null si no es corto, o false si está alterado.
  function shortLink() {
    var q = new URLSearchParams(location.search);
    var v = q.get("v"), s = (q.get("i") || "").toLowerCase();
    if (!v && !s) return null;
    if (!/^[1-9][0-9]{0,2}$/.test(v || "") || !/^[0-9a-z]+$/.test(s) || (s.length - 1) % 3 !== 0 || s.length < 4) return false;
    var body = s.slice(0, -1), idx = [], sum = 0;
    for (var i = 0; i < body.length; i += 3) {
      var n = parseInt(body.substr(i, 3), 36);
      idx.push(n);
      sum += (idx.length) * n;
    }
    if ((sum % 36).toString(36) !== s.slice(-1)) return false;
    return { v: v, idx: idx.slice(0, 200) };
  }
  function buyUrl(marca, nombre) {
    return CJ + "?url=" + encodeURIComponent("https://perfumania.com/search?q=" + encodeURIComponent(marca + " " + nombre));
  }
  function photoUrl(photos, id) {
    if (!photos) return null;
    var key = id.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    if ((photos.verified_ids || []).indexOf(key) < 0) return null;
    var repo = (photos.photo_repo || {})[key];
    if (!repo) return null;
    var b = (photos.photo_bases || {})[repo] || ("https://clabhf.github.io/aromario-fotos-" + repo + "/botellas/");
    if (b.slice(-1) !== "/") b += "/";
    var ext = (photos.photo_ext || {})[key] || photos.default_ext || "webp";
    return b + "botella_" + key + "." + ext;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function card(id, info, photo) {
    var nombre = info[0], marca = info[1];
    var c = el("article", "wl-card");
    var pic = el("div", "wl-photo");
    if (photo) {
      var img = new Image();
      img.alt = nombre; img.loading = "lazy"; img.decoding = "async"; img.src = photo;
      img.onerror = function () { pic.textContent = ""; pic.appendChild(el("span", "wl-mono", nombre.charAt(0).toUpperCase())); };
      pic.appendChild(img);
    } else {
      pic.appendChild(el("span", "wl-mono", nombre.charAt(0).toUpperCase()));
    }
    var txt = el("div", "wl-text");
    txt.appendChild(el("h2", "wl-name", nombre));
    txt.appendChild(el("p", "wl-brand", marca));
    var a = el("a", "btn btn-primary btn-sm", T.buy);
    a.href = buyUrl(marca, nombre); a.target = "_blank"; a.rel = "sponsored noopener";
    txt.appendChild(a);
    c.appendChild(pic); c.appendChild(txt);
    return c;
  }
  function msg(t) { root.textContent = ""; root.appendChild(el("p", "wl-msg", t)); }

  var short = shortLink();
  if (short === false) { msg(T.invalid); return; }
  var list = short ? null : ids();
  if (!short && !list.length) { msg(T.empty); return; }
  Promise.all([
    fetch(base + "data/perfumes-ligero.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }),
    fetch(base + "verified_photos.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    // Cada versión del orden se conserva publicada para que los enlaces ya compartidos sigan valiendo.
    short ? fetch(base + "data/orden-v" + short.v + ".json").then(function (r) { if (!r.ok) throw 1; return r.json(); }) : null
  ]).then(function (res) {
    var names = res[0], photos = res[1];
    if (short) {
      var order = res[2], seen = {};
      if (short.idx.some(function (n) { return n >= order.length; })) { msg(T.invalid); return; }
      list = short.idx.map(function (n) { return order[n]; }).filter(function (id) {
        if (seen[id]) return false; seen[id] = 1; return true;
      });
    }
    var found = list.filter(function (id) { return names[id]; });
    if (!found.length) { msg(T.empty); return; }
    root.textContent = "";
    var count = document.getElementById("wl-count");
    if (count) count.textContent = T.count(found.length);
    found.forEach(function (id) { root.appendChild(card(id, names[id], photoUrl(photos, id))); });
  }).catch(function (e) { msg(e === 1 ? T.invalid : T.error); });
})();
