/* Aromario — página de deseos compartidos (ES/EN). Lee ?ids=… y arma la lista solo con datos
   públicos: nombre y marca de data/perfumes-ligero.json y la foto de verified_photos.json.
   El enlace no lleva datos de la cuenta; la lista no se marca como comprada. */
(function () {
  var root = document.getElementById("wishlist");
  if (!root) return;
  var en = document.documentElement.lang === "en";
  var base = root.getAttribute("data-base") || "";
  var T = en
    ? { buy: "Buy", empty: "This list is empty or the link is incomplete.", error: "We couldn't load the list. Try again in a moment.", count: function (n) { return n === 1 ? "1 perfume" : n + " perfumes"; } }
    : { buy: "Comprar", empty: "Esta lista está vacía o el enlace está incompleto.", error: "No pudimos cargar la lista. Prueba de nuevo en un momento.", count: function (n) { return n === 1 ? "1 perfume" : n + " perfumes"; } };
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

  var list = ids();
  if (!list.length) { msg(T.empty); return; }
  Promise.all([
    fetch(base + "data/perfumes-ligero.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }),
    fetch(base + "verified_photos.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (res) {
    var names = res[0], photos = res[1];
    var found = list.filter(function (id) { return names[id]; });
    if (!found.length) { msg(T.empty); return; }
    root.textContent = "";
    var count = document.getElementById("wl-count");
    if (count) count.textContent = T.count(found.length);
    found.forEach(function (id) { root.appendChild(card(id, names[id], photoUrl(photos, id))); });
  }).catch(function () { msg(T.error); });
})();
