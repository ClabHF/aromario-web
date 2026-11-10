#!/usr/bin/env python3
"""Pasada de feeds para SUMAR enlaces de tienda que faltan en las fichas (orden de Claudio, 2026-11-09).

Baja los mismos feeds que la corrida de precios (Awin de los programas con tienda en tiendas.json,
CJ de las 4 tiendas y Rakuten FragranceNet), cruza cada producto contra el catálogo completo de la
app (base + extra) y propone solo los enlaces que la ficha NO tiene hoy en esa tienda.
Nada entra a la app desde aquí: Bishi audita cada candidato antes de integrarlo a tiendas.json.

Cruce ESTRICTO, sin excepciones:
- Marca normalizada igual (la del feed contra la de la ficha) y nombre normalizado igual, token por
  token, después de quitar la marca, el tamaño y las palabras de relleno (spray, by, ...).
- Conjunto de tokens de variante idéntico: concentración (edt, edp, edc, parfum, le parfum, ...) y
  flanker (elixir, intense, absolute, magnetic, ...). Si la ficha no dice concentración en el nombre,
  se toma la de su id; si tampoco la tiene, solo casa con productos sin concentración.
- Género: si el producto lo declara (for him / pour homme / men contra for her / pour femme / women /
  unisex), debe ser el de la ficha. Si discrepan, se rechaza.
- Cero ambiguos: un producto que casa con más de una ficha se descarta y se anota. Los tamaños de un
  mismo producto cuentan como uno (se propone el más cercano a 100 ml); si una ficha queda con dos
  productos distintos de la misma tienda, se descarta y se anota.
- Sets, testers, minis, muestras, recargas y productos de cuerpo/cabello/hogar quedan fuera.

Uso:
  python3 enlaces.py datos tiendas.json todos_1.json ... catalogo_extra_1.json   # regenerar insumos
  python3 enlaces.py                                                             # corrida (workflow)
Salida: enlaces_candidatos.json y enlaces_resumen.md en la raíz del repo.
"""
import csv, datetime, gzip, io, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, '..', '..'))
sys.path.insert(0, os.path.join(AQUI, '..', 'precios'))
import precios as P  # noqa: E402  (descarga, credenciales y claves de producto: las mismas que la corrida de precios)

DATOS = os.path.join(AQUI, 'datos.json')
SALIDA = os.path.join(RAIZ, 'enlaces_candidatos.json')
RESUMEN = os.path.join(RAIZ, 'enlaces_resumen.md')
HOY = datetime.date.today().isoformat()

# ---------------------------------------------------------------- normalización
CONC = [  # frases (ya normalizadas) -> token de concentración; el orden importa
    ('extrait de parfum', 'parfum'), ('eau de parfum', 'edp'), ('eau de toilette', 'edt'),
    ('eau de cologne', 'edc'), ('le parfum', 'leparfum'), ('eau fraiche', 'eaufraiche'),
    ('parfum de toilette', 'pdt'), ('extrait', 'parfum'),
]
TOKENS_CONC = {'edp', 'edt', 'edc', 'parfum', 'leparfum', 'eaufraiche', 'pdt'}
FLANKER = {'elixir', 'intense', 'intensely', 'absolute', 'absolu', 'magnetic', 'extreme'}
GENERO = [  # frases -> género declarado (se quitan del nombre)
    ('for him', 'hombre'), ('for men', 'hombre'), ('for man', 'hombre'), ('pour homme', 'hombre'),
    ('for her', 'mujer'), ('for women', 'mujer'), ('for woman', 'mujer'), ('pour femme', 'mujer'),
    ('for unisex', 'unisex'), ('mens', 'hombre'), ('womens', 'mujer'), ('ladies', 'mujer'),
    ('men', 'hombre'), ('man', 'hombre'), ('women', 'mujer'), ('woman', 'mujer'), ('unisex', 'unisex'),
]
RELLENO = {'spray', 'vaporisateur', 'vapo', 'natural', 'by', 'perfume', 'fragrance', 'cologne', 'new',
           'packaging', 'and', 'oz', 'ml', 'fl'}
FUERA = {'set', 'gift', 'coffret', 'kit', 'tester', 'sample', 'vial', 'mini', 'miniature', 'travel',
         'refill', 'recharge', 'decant', 'discovery', 'deodorant', 'deo', 'stick', 'lotion', 'shower',
         'gel', 'balm', 'body', 'hair', 'soap', 'candle', 'aftershave', 'cream', 'unboxed', 'damaged',
         'pack', 'duo', 'trio', 'bundle', 'sampler', 'mist', 'powder', 'diffuser', 'creme', 'bath'}
TAM = re.compile(r'(\d+(?:[.,]\d+)?)\s*(ml|oz|fl\.?\s*oz|fl)\b')


def plano(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = s.replace('&', ' and ').replace("'s ", 's ').replace("'", '')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9.,]+', ' ', s)).strip()


def tamano_ml(titulo):
    m = TAM.search(plano(titulo))
    if not m:
        return None
    v = float(m.group(1).replace(',', '.'))
    return v * 29.57 if 'oz' in m.group(2) else v


def frase(texto, fr, rep):
    return re.sub(r'(?<![a-z0-9])' + re.escape(fr) + r'(?![a-z0-9])', rep, texto)


def desarmar(texto, marca):
    """-> (nombre: tupla de tokens, variante: frozenset, genero declarado o None, excluido: bool)"""
    t = TAM.sub(' ', plano(texto))
    t = re.sub(r'[.,]', ' ', t)
    m = ' '.join(re.sub(r'[.,]', ' ', plano(marca)).split())
    if m:
        t = frase(t, m, ' ')
    genero = None
    for fr, g in GENERO:
        if re.search(r'(?<![a-z0-9])' + re.escape(fr) + r'(?![a-z0-9])', t):
            if genero and genero != g:
                genero = 'mixto'
            genero = genero or g
            t = frase(t, fr, ' ')
    for fr, tok in CONC:
        t = frase(t, fr, ' ' + tok + ' ')
    toks = t.split()
    excluido = any(x in FUERA for x in toks)
    var = frozenset(x for x in toks if x in TOKENS_CONC or x in FLANKER)
    nombre = tuple(x for x in toks if x not in TOKENS_CONC and x not in FLANKER and x not in RELLENO)
    return nombre, var, genero, excluido


def marca_n(m):
    return ' '.join(re.sub(r'[.,]', ' ', plano(m)).split())


# ---------------------------------------------------------------- insumos (catálogo + enlaces actuales)
def hacer_datos(ruta_tiendas, catalogos):
    fichas = {}
    for c in catalogos:
        d = json.load(open(c, encoding='utf-8'))
        lst = d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))
        for x in lst:
            fichas[x['id']] = [x.get('marca') or '', x.get('nombre') or '', x.get('genero') or '']
    t = json.load(open(ruta_tiendas, encoding='utf-8'))
    enlazado, ocupados, prefijos, awin_mid = {}, {}, {}, {}
    for fid, links in t['fichas'].items():
        for tienda, url in links.items():
            enlazado.setdefault(fid, []).append(tienda)
            k = P.clave_enlace(tienda, url)
            if k:
                ocupados.setdefault(tienda, {})[k[2]] = fid
                if k[0] == 'awin':
                    awin_mid[k[1]] = tienda
            if tienda in P.CJ_TIENDAS and '?url=' in url:
                prefijos.setdefault(tienda, url.split('?url=')[0])
    json.dump({'_nota': 'Insumos de enlaces.py: ficha -> [marca, nombre, género]; enlaces actuales de tiendas.json.',
               'generado': HOY, 'fichas': fichas, 'enlazado': enlazado, 'ocupados': ocupados,
               'prefijos_cj': prefijos, 'awin_mid_tienda': awin_mid},
              open(DATOS, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('datos:', len(fichas), 'fichas,', sum(len(v) for v in enlazado.values()), 'enlaces actuales')


# ---------------------------------------------------------------- feeds con título
def prod(tienda, clave, titulo, marca, url, p):
    return {'tienda': tienda, 'clave': clave, 'titulo': titulo, 'marca': marca, 'url': url, 'precio': p}


def feed_awin(mid_tienda, notas):
    (key,) = P.env('AWIN_FEED_APIKEY')
    lista = P.pedir(f'https://productdata.awin.com/datafeed/list/apikey/{key}').decode('utf-8', 'replace')
    fids, sin_tienda = [], set()
    for fila in csv.DictReader(io.StringIO(lista)):
        mid = (fila.get('Advertiser ID') or '').strip()
        estado = (fila.get('Membership Status') or '').strip().lower()
        if estado not in ('active', 'joined', ''):
            continue
        if mid in mid_tienda:
            fids.append((fila.get('Feed ID') or '').strip())
        else:
            sin_tienda.add(f'{fila.get("Advertiser Name", "?").strip()} ({mid})')
    if sin_tienda:
        notas.append('Awin: programas unidos sin tienda en tiendas.json (no se cruzan): ' + ', '.join(sorted(sin_tienda)))
    cols = 'aw_product_id,merchant_id,product_name,brand_name,aw_deep_link,merchant_deep_link,search_price,rrp_price,currency'
    out = []
    fids = [f for f in fids if f]
    for i in range(0, len(fids), 10):
        url = (f'https://productdata.awin.com/datafeed/download/apikey/{key}/language/any/fid/'
               f'{",".join(fids[i:i + 10])}/columns/{cols}/format/csv/delimiter/%2C/compression/gzip/adultcontent/1/')
        raw = P.pedir(url, timeout=600)
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        for f in csv.DictReader(io.StringIO(raw.decode('utf-8', 'replace'))):
            tienda = mid_tienda.get((f.get('merchant_id') or '').strip())
            if not tienda or not f.get('aw_deep_link'):
                continue
            out.append(prod(tienda, 'p:' + (f.get('aw_product_id') or '').strip(), f.get('product_name') or '',
                            f.get('brand_name') or '', f['aw_deep_link'].strip(),
                            P.precio(f.get('search_price'), f.get('rrp_price'), f.get('currency'))))
            if f.get('merchant_deep_link'):   # el mismo producto también puede estar enlazado por cread.php
                out[-1]['clave2'] = 'u:' + P.clave_url(f['merchant_deep_link'])
    return out


def feed_rakuten(marcas, notas):
    cid, csec, sid, mid = P.env('RAKUTEN_CLIENT_ID', 'RAKUTEN_CLIENT_SECRET', 'RAKUTEN_SID', 'RAKUTEN_FRAGRANCENET_MID')
    import base64
    basic = base64.b64encode(f'{cid}:{csec}'.encode()).decode()

    def token():
        return json.loads(P.pedir('https://api.linksynergy.com/token',
                                  data=urllib.parse.urlencode({'grant_type': 'client_credentials', 'scope': sid}).encode(),
                                  headers={'Authorization': 'Basic ' + basic,
                                           'Content-Type': 'application/x-www-form-urlencoded'}))['access_token']
    tok, t0, out, vistos, fallos = token(), time.time(), [], set(), 0
    for marca in marcas:
        if time.time() - t0 > 3000:
            tok, t0 = token(), time.time()
        pagina, total = 1, 1
        while pagina <= total and pagina <= 100:
            q = urllib.parse.urlencode({'keyword': '"' + marca + '"', 'mid': mid, 'max': 100, 'pagenumber': pagina})
            try:
                raw = P.pedir('https://api.linksynergy.com/productsearch/1.0?' + q,
                              headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/xml'})
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise
                fallos += 1
                break
            r = ET.fromstring(raw)
            total = int(r.findtext('TotalPages') or 0)
            for it in r.iter('item'):
                sku, link = (it.findtext('sku') or '').strip(), (it.findtext('linkurl') or '').strip()
                if not sku or not link or sku in vistos:
                    continue
                vistos.add(sku)
                murl = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get('murl', [''])[0]
                seg = urllib.parse.urlparse(murl).path.strip('/').split('/')
                marca_fn = seg[1].replace('-', ' ') if len(seg) > 1 else ''
                pr, sp = it.find('price'), it.find('saleprice')
                mon = (sp.get('currency') if sp is not None else None) or (pr.get('currency') if pr is not None else 'USD')
                out.append(prod('fragrancenet', sku, it.findtext('productname') or '', marca_fn, link,
                                P.precio(sp.text if sp is not None else None, pr.text if pr is not None else None, mon or 'USD')))
            pagina += 1
            time.sleep(0.7)
    if fallos:
        notas.append(f'Rakuten: {fallos} marcas con error de la API')
    return out


def feed_cj(prefijos, marcas, notas):
    tok, cid = P.env('CJ_TOKEN', 'CJ_CID')
    ids, out = None, []
    for tienda in sorted(P.CJ_TIENDAS):
        if tienda not in prefijos:
            notas.append(f'CJ {tienda}: sin enlaces en tiendas.json para copiar el formato; no se cruza')
            continue
        dom, _, secreto = P.CJ_TIENDAS[tienda]
        adv = os.environ.get(secreto, '').strip()
        if not adv:
            if ids is None:
                try:
                    ids = P.anunciantes_cj(tok, cid)
                except Exception as e:  # noqa: BLE001
                    ids = {}
                    notas.append(f'CJ: búsqueda de anunciantes: {type(e).__name__}: {e}'[:200])
            adv = ids.get(dom, '')
        if not adv:
            notas.append(f'CJ {tienda}: sin id de anunciante ({secreto}); no se cruza')
            continue
        vistos = set()

        def pagina(extra, offset):
            q = ('{ shoppingProducts(companyId: "%s", partnerIds: ["%s"]%s, limit: 1000, offset: %d) '
                 '{ totalCount resultList { title brand link price { amount currency } salePrice { amount currency } } } }'
                 % (cid, adv, extra, offset))
            r = json.loads(P.pedir('https://ads.api.cj.com/query', data=json.dumps({'query': q}).encode(),
                                   headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}))
            if r.get('errors'):
                raise RuntimeError('; '.join(e.get('message', '?') for e in r['errors'])[:300])
            d = r['data']['shoppingProducts']
            for it in d.get('resultList') or []:
                k = P.clave_cj(tienda, it.get('link') or '')
                if not k or k in vistos:
                    continue
                vistos.add(k)
                pr, sp = it.get('price') or {}, it.get('salePrice') or {}
                out.append(prod(tienda, k, it.get('title') or '', it.get('brand') or '',
                                prefijos[tienda] + '?url=' + urllib.parse.quote(it['link'].strip(), safe=''),
                                P.precio(sp.get('amount'), pr.get('amount'), sp.get('currency') or pr.get('currency'))))
            return int(d.get('totalCount') or 0), len(d.get('resultList') or [])

        def todo(extra):
            offset, total = 0, 1
            while offset < total and offset < 10000:
                try:
                    total, n = pagina(extra, offset)
                except P.urllib.error.HTTPError as e:
                    if e.code == 400 and offset > 0:
                        break
                    raise
                if not n:
                    break
                offset += n
            return total
        try:
            total = todo('')
            if total > 10000:   # la API corta en 10.000: se completa marca por marca
                notas.append(f'CJ {tienda}: {total} productos; se completa por marca del catálogo')
                for m in marcas:
                    todo(', keywords: [%s]' % json.dumps(m))
                    time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            notas.append(f'CJ {tienda}: {type(e).__name__}: {e}'[:200])
        notas.append(f'CJ {tienda}: {len(vistos)} productos leídos (anunciante {adv})')
    return out


# ---------------------------------------------------------------- cruce
def cruzar(datos, productos):
    fichas, enlazado, ocupados = datos['fichas'], datos['enlazado'], datos['ocupados']
    por_clave = {}
    sin_conc = 0
    for fid, (marca, nombre, genero) in fichas.items():
        n, v, _, _ = desarmar(nombre, marca)
        if not (v & TOKENS_CONC):
            _, vid, _, _ = desarmar(fid.replace('-', ' '), marca)
            if vid & TOKENS_CONC:
                v = v | (vid & TOKENS_CONC)
            else:
                sin_conc += 1
        if n:
            por_clave.setdefault((marca_n(marca), n, v), []).append((fid, genero))

    cuenta = {}
    def c(t, k):
        cuenta.setdefault(t, {}).setdefault(k, 0)
        cuenta[t][k] += 1

    grupos = {}            # (tienda, ficha) -> {identidad del producto: [productos]}
    ambiguos, conflictos = [], []
    for p in productos:
        t = p['tienda']
        c(t, 'productos_leidos')
        n, v, g, fuera = desarmar(p['titulo'], p['marca'] or '')
        if fuera:
            c(t, 'fuera_por_tipo'); continue
        if not n or not p['marca']:
            c(t, 'sin_marca_o_nombre'); continue
        cand = por_clave.get((marca_n(p['marca']), n, v), [])
        if not cand:
            c(t, 'sin_ficha'); continue
        ok = [fid for fid, fg in cand if g is None or g == fg]
        if not ok:
            c(t, 'rechazo_genero'); continue
        if len(ok) > 1:
            c(t, 'ambiguo_producto')
            ambiguos.append({'tienda': t, 'titulo': p['titulo'], 'url': p['url'], 'fichas': ok,
                             'motivo': 'el producto casa con más de una ficha'})
            continue
        fid = ok[0]
        dueno = ocupados.get(t, {}).get(p['clave']) or (ocupados.get(t, {}).get(p.get('clave2')) if p.get('clave2') else None)
        if dueno:
            if dueno != fid:
                c(t, 'conflicto')
                conflictos.append({'tienda': t, 'titulo': p['titulo'], 'casa_con': fid, 'enlazado_hoy_a': dueno})
            else:
                c(t, 'ya_enlazado')
            continue
        if t in enlazado.get(fid, []):
            c(t, 'ficha_ya_tiene_tienda'); continue
        grupos.setdefault((t, fid), {}).setdefault((n, v, g), []).append(p)

    candidatos = []
    for (t, fid), ident in sorted(grupos.items()):
        if len(ident) > 1:
            c(t, 'ambiguo_ficha')
            ambiguos.append({'tienda': t, 'ficha': fid, 'motivo': 'la ficha casa con más de un producto distinto',
                             'titulos': [x[0]['titulo'] for x in ident.values()]})
            continue
        ps = next(iter(ident.values()))
        elegido = min(ps, key=lambda x: abs((tamano_ml(x['titulo']) or 100) - 100))
        c(t, 'candidatos')
        candidatos.append({'ficha': fid, 'tienda': t, 'url': elegido['url'], 'titulo': elegido['titulo'],
                           'precio': elegido['precio'], 'tamanos_en_feed': len(ps),
                           'ficha_nombre': fichas[fid][1], 'ficha_marca': fichas[fid][0], 'ficha_genero': fichas[fid][2]})
    return candidatos, ambiguos, conflictos, cuenta, sin_conc


def correr():
    datos = json.load(open(DATOS, encoding='utf-8'))
    marcas = sorted({m for m, _, _ in datos['fichas'].values() if m})
    notas, productos, estado = [], [], {}
    mid_tienda = dict(datos['awin_mid_tienda'])
    mid_tienda.setdefault('124166', 'fragrance_click')  # Fragrance Click UK: unida en Awin, aun sin enlaces en tiendas.json (orden de Claudio, 2026-11-10)
    trabajos = [('awin', lambda: feed_awin(mid_tienda, notas)),
                ('rakuten', lambda: feed_rakuten(marcas, notas)),
                ('cj', lambda: feed_cj(datos['prefijos_cj'], marcas, notas))]
    for red, fn in trabajos:
        t = time.time()
        try:
            ps = fn()
            productos += ps
            estado[red] = f'ok, {len(ps)} productos'
        except P.SinCredencial as e:
            estado[red] = f'bloqueado: {e}'
        except Exception as e:  # noqa: BLE001
            estado[red] = f'error: {type(e).__name__}: {e}'[:300]
        print(red, estado[red], f'({time.time() - t:.0f} s)', flush=True)

    candidatos, ambiguos, conflictos, cuenta, sin_conc = cruzar(datos, productos)
    json.dump({'_nota': 'Candidatos a enlace de tienda. NADA entra a tiendas.json sin la auditoría de Bishi.',
               'generado': HOY, 'redes': estado, 'notas': notas, 'resumen_por_tienda': cuenta,
               'fichas_sin_concentracion': sin_conc, 'candidatos': candidatos,
               'descartados_ambiguos': ambiguos, 'conflictos_con_enlaces_actuales': conflictos},
              open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    cols = ['productos_leidos', 'candidatos', 'ya_enlazado', 'ficha_ya_tiene_tienda', 'sin_ficha',
            'rechazo_genero', 'ambiguo_producto', 'ambiguo_ficha', 'conflicto', 'fuera_por_tipo', 'sin_marca_o_nombre']
    lin = [f'## Enlaces candidatos {HOY}', '', '| Red | Estado |', '|---|---|']
    lin += [f'| {r} | {e} |' for r, e in estado.items()]
    lin += ['', '| Tienda | ' + ' | '.join(cols) + ' |', '|---' * (len(cols) + 1) + '|']
    for t in sorted(cuenta):
        lin.append(f'| {t} | ' + ' | '.join(str(cuenta[t].get(k, 0)) for k in cols) + ' |')
    lin += ['', f'**Total: {len(candidatos)} candidatos**, {len(ambiguos)} descartados por ambiguos, '
                f'{len(conflictos)} conflictos con enlaces actuales (producto que casa estricto con otra ficha).',
            f'Fichas cuyo nombre e id no dicen concentración (solo casan con productos sin concentración): {sin_conc}.', '']
    lin += ['- ' + n for n in notas]
    informe = '\n'.join(lin)
    open(RESUMEN, 'w', encoding='utf-8').write(informe + '\n')
    print(informe)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(informe + '\n')


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'datos':
        hacer_datos(sys.argv[2], sys.argv[3:])
    else:
        correr()
