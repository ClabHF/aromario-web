/* Aromario — página de deseos compartidos (14 idiomas). Lee ?ids=… y arma la lista solo con datos
   públicos: nombre y marca de data/perfumes-ligero.json y la foto de verified_photos.json.
   El enlace no lleva datos de la cuenta; la lista no se marca como comprada.
   Enlace corto (app 1.1.19+): ?v=1&i=… = índices en el orden canónico data/orden-v1.json (3 caracteres
   en base 36 por perfume) + 1 carácter de verificación. Los enlaces viejos con ?ids= siguen valiendo. */
(function () {
  var root = document.getElementById("wishlist");
  if (!root) return;
  // 14 idiomas: el de la página (<html lang>); cualquier otro -> español.
  var lang = (document.documentElement.lang || "es").toLowerCase().slice(0, 2);
  var base = root.getAttribute("data-base") || "";
  function plain(one, many) { return function (n) { return n === 1 ? one : n + " " + many; }; }
  var TT = {
    es: { buy: "Comprar", invalid: "Este enlace está dañado o incompleto. Pide que te lo envíen de nuevo.", empty: "Esta lista está vacía o el enlace está incompleto.", error: "No pudimos cargar la lista. Prueba de nuevo en un momento.", count: plain("1 perfume", "perfumes") },
    en: { buy: "Buy", invalid: "This link is damaged or incomplete. Ask for it again.", empty: "This list is empty or the link is incomplete.", error: "We couldn't load the list. Try again in a moment.", count: plain("1 perfume", "perfumes") },
    pt: { buy: "Comprar", invalid: "Este link está danificado ou incompleto. Peça que enviem de novo.", empty: "Esta lista está vazia ou o link está incompleto.", error: "Não conseguimos carregar a lista. Tente de novo em um instante.", count: plain("1 perfume", "perfumes") },
    fr: { buy: "Acheter", invalid: "Ce lien est abîmé ou incomplet. Demandez qu'on vous le renvoie.", empty: "Cette liste est vide ou le lien est incomplet.", error: "Impossible de charger la liste. Réessayez dans un instant.", count: plain("1 parfum", "parfums") },
    de: { buy: "Kaufen", invalid: "Dieser Link ist beschädigt oder unvollständig. Bitte erneut anfordern.", empty: "Diese Liste ist leer oder der Link ist unvollständig.", error: "Die Liste konnte nicht geladen werden. Versuch es gleich noch einmal.", count: plain("1 Parfüm", "Parfüms") },
    it: { buy: "Acquista", invalid: "Questo link è danneggiato o incompleto. Chiedi che te lo rimandino.", empty: "Questa lista è vuota o il link è incompleto.", error: "Non siamo riusciti a caricare la lista. Riprova tra un momento.", count: plain("1 profumo", "profumi") },
    ar: { buy: "شراء", invalid: "هذا الرابط تالف أو غير مكتمل. اطلب إرساله من جديد.", empty: "هذه القائمة فارغة أو الرابط غير مكتمل.", error: "تعذّر تحميل القائمة. حاول مجددًا بعد لحظة.", count: function (n) { return n === 1 ? "عطر واحد" : n === 2 ? "عطران" : n <= 10 ? n + " عطور" : n + " عطرًا"; } },
    tr: { buy: "Satın al", invalid: "Bu bağlantı bozuk ya da eksik. Yeniden göndermelerini iste.", empty: "Bu liste boş ya da bağlantı eksik.", error: "Liste yüklenemedi. Birazdan tekrar dene.", count: function (n) { return n + " parfüm"; } },
    pl: { buy: "Kup", invalid: "Ten link jest uszkodzony lub niepełny. Poproś o ponowne wysłanie.", empty: "Ta lista jest pusta albo link jest niepełny.", error: "Nie udało się wczytać listy. Spróbuj ponownie za chwilę.", count: function (n) { return "perfumy: " + n; } },
    ro: { buy: "Cumpără", invalid: "Acest link este deteriorat sau incomplet. Cere să ți-l trimită din nou.", empty: "Această listă este goală sau linkul este incomplet.", error: "Nu am putut încărca lista. Încearcă din nou peste câteva momente.", count: function (n) { return n === 1 ? "1 parfum" : (n % 100 === 0 || n % 100 >= 20 ? n + " de parfumuri" : n + " parfumuri"); } },
    el: { buy: "Αγορά", invalid: "Αυτός ο σύνδεσμος είναι κατεστραμμένος ή ελλιπής. Ζήτησε να σου τον ξαναστείλουν.", empty: "Αυτή η λίστα είναι κενή ή ο σύνδεσμος είναι ελλιπής.", error: "Δεν μπορέσαμε να φορτώσουμε τη λίστα. Δοκίμασε ξανά σε λίγο.", count: plain("1 άρωμα", "αρώματα") },
    hu: { buy: "Vásárlás", invalid: "Ez a link sérült vagy hiányos. Kérd, hogy küldjék el újra.", empty: "Ez a lista üres, vagy a link hiányos.", error: "Nem sikerült betölteni a listát. Próbáld újra egy pillanat múlva.", count: function (n) { return n + " parfüm"; } },
    cs: { buy: "Koupit", invalid: "Tento odkaz je poškozený nebo neúplný. Požádejte o jeho opětovné zaslání.", empty: "Tento seznam je prázdný nebo je odkaz neúplný.", error: "Seznam se nepodařilo načíst. Zkuste to za chvíli znovu.", count: function (n) { return n === 1 ? "1 parfém" : (n >= 2 && n <= 4 ? n + " parfémy" : n + " parfémů"); } },
    nl: { buy: "Kopen", invalid: "Deze link is beschadigd of onvolledig. Vraag om hem opnieuw te sturen.", empty: "Deze lijst is leeg of de link is onvolledig.", error: "We konden de lijst niet laden. Probeer het zo meteen opnieuw.", count: plain("1 parfum", "parfums") }
  };
  var T = TT[lang] || TT.es;
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
