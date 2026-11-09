#!/usr/bin/env python3
"""Corrida nocturna de precios de Aromario (diseño del 2026-10-29).

Cada noche, desde GitHub Actions: baja de nuevo los feeds de las tiendas afiliadas, vuelve a poner
precio a cada enlace de tiendas.json (el mismo cruce que hizo assets/precios.json del paquete .31) y
escribe precios.json en la raíz del sitio, que GitHub Pages sirve en https://aromario.app/precios.json.

Formato (el que lee StorePrices.kt en la app, sin cambios):
  {"generado": "AAAA-MM-DD", "precios": {"<ficha>": {"<tienda>": [precio, "USD"] |
                                                       [precio, "EUR", precio_de_lista]}}}
"_fuentes" es informativo (la app lo ignora): de qué feed y de qué fecha sale cada tienda.

Reglas:
- El precio sale solo del feed de afiliado. Nunca de la página de la tienda; nunca se inventa.
- Precio de lista solo si el feed lo trae y es mayor que el de venta.
- Si un feed falla o no tiene credencial, esa tienda conserva el precio de la corrida anterior hasta
  MAX_DIAS días; después queda sin precio.
- Solo Python estándar (sin pip). Cero tokens.

Uso:
  python3 precios.py                       # corrida normal (lo que hace el workflow)
  python3 precios.py indice tiendas.json   # regenerar enlaces.json cuando cambie tiendas.json de la app
"""
import base64, csv, datetime, gzip, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, '..', '..'))
INDICE = os.path.join(AQUI, 'enlaces.json')
SALIDA = os.path.join(RAIZ, 'precios.json')
MAX_DIAS = 14
UA = 'Aromario-precios/1.0 (+https://aromario.app)'
HOY = datetime.date.today().isoformat()


# ---------------------------------------------------------------- tiendas CJ
# 1.1.33 (orden de Claudio): FragranceShop y Perfume Giants (y eCosmetics) además de Perfumania.
# tienda -> (dominio, patrón del slug del producto en la URL, secreto opcional con el id de anunciante)
CJ_TIENDAS = {
    'perfumania': ('perfumania.com', r'/products/([^/?#]+)', 'CJ_PERFUMANIA_ID'),
    'fragranceshop': ('fragranceshop.com', r'/product/([^/?#]+)', 'CJ_FRAGRANCESHOP_ID'),
    'perfumegiants': ('perfumegiants.com', r'/products/([^/?#]+)', 'CJ_PERFUMEGIANTS_ID'),
    'ecosmetics': ('ecosmetics.com', r'/product/([^/?#]+)', 'CJ_ECOSMETICS_ID'),
}


def clave_cj(tienda, url):
    """Slug del producto de una tienda CJ en una URL de destino (o None)."""
    dom, pat, _ = CJ_TIENDAS[tienda]
    m = re.search(re.escape(dom) + pat, urllib.parse.unquote(url or ''))
    return m.group(1).lower() if m else None


# ---------------------------------------------------------------- índice de enlaces
def clave_url(u):
    """URL de producto normalizada (sin esquema, query ni barra final) para comparar feed y enlace."""
    p = urllib.parse.urlparse(urllib.parse.unquote(u.strip()))
    host = p.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    return host + p.path.rstrip('/').lower()


def clave_enlace(tienda, url):
    """Qué buscar en el feed para el enlace de tiendas.json. None si el formato no se reconoce."""
    p = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(p.query)
    if 'awin1.com' in p.netloc:
        if p.path.endswith('/pclick.php') and 'p' in q:          # id de producto de Awin
            return 'awin', q.get('m', [''])[0], 'p:' + q['p'][0]
        if p.path.endswith('/cread.php') and 'ued' in q:         # deep link a la ficha de la tienda
            return 'awin', q.get('awinmid', [''])[0], 'u:' + clave_url(q['ued'][0])
    if 'linksynergy.com' in p.netloc and 'murl' in q:            # FragranceNet: el SKU cierra la URL
        sku = urllib.parse.urlparse(q['murl'][0]).path.rstrip('/').rsplit('/', 1)[-1]
        if sku.isdigit():
            return 'rakuten', 'fragrancenet', sku
    if tienda in CJ_TIENDAS and 'url' in q:                      # CJ: slug del producto en la tienda
        k = clave_cj(tienda, q['url'][0])
        if k:
            return 'cj', tienda, k
    return None


def hacer_indice(ruta_tiendas):
    t = json.load(open(ruta_tiendas, encoding='utf-8'))
    out, raros = {}, 0
    for fid, links in t['fichas'].items():
        for tienda, url in links.items():
            k = clave_enlace(tienda, url)
            if k is None:
                raros += 1
                continue
            out.setdefault(fid, {})[tienda] = list(k)
    marcas = sorted({urllib.parse.urlparse(urllib.parse.parse_qs(urllib.parse.urlparse(u).query)['murl'][0])
                     .path.strip('/').split('/')[1].replace('-', ' ')
                     for links in t['fichas'].values() for s, u in links.items() if s == 'fragrancenet'})
    json.dump({'_nota': 'Generado de app/src/main/assets/tiendas.json con "precios.py indice". '
                        'ficha -> tienda -> [red, comercio, clave].',
               'generado': HOY, 'marcas_fragrancenet': marcas, 'fichas': out},
              open(INDICE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('índice:', sum(len(v) for v in out.values()), 'enlaces en', len(out), 'fichas;',
          raros, 'sin formato reconocido;', len(marcas), 'marcas de FragranceNet')


# ---------------------------------------------------------------- utilidades
def pedir(url, data=None, headers=None, intentos=3, timeout=120):
    h = {'User-Agent': UA}
    h.update(headers or {})
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or i == intentos - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == intentos - 1:
                raise
        time.sleep(5 * (i + 1))


def num(x):
    try:
        v = float(str(x).replace(',', '.').strip())
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def precio(venta, lista, moneda):
    """[precio, moneda] o [precio, moneda, lista] si la lista es mayor; None si no hay precio válido."""
    venta, lista = num(venta), num(lista)
    moneda = (moneda or '').strip().upper()
    if venta is None and lista is not None:
        venta, lista = lista, None
    if venta is None or len(moneda) != 3:
        return None
    p = [round(venta, 2), moneda]
    if lista is not None and lista > venta + 0.004:
        p.append(round(lista, 2))
    return p


class SinCredencial(Exception):
    pass


def env(*nombres):
    faltan = [n for n in nombres if not os.environ.get(n, '').strip()]
    if faltan:
        raise SinCredencial('falta el secreto ' + ', '.join(faltan))
    return [os.environ[n].strip() for n in nombres]


# ---------------------------------------------------------------- feeds
def feed_awin(comercios):
    """Awin (Comas, Nasopia, Parfivo, Parfumbella, Opulensi, Al Jazeera). Un solo secreto: la clave
    de feeds del publisher (Awin > Toolbox > Create-a-Feed). Devuelve {(comercio, clave): precio}."""
    (key,) = env('AWIN_FEED_APIKEY')
    lista = pedir(f'https://productdata.awin.com/datafeed/list/apikey/{key}').decode('utf-8', 'replace')
    fids, vistos = [], set()
    for fila in csv.DictReader(io.StringIO(lista)):
        mid = (fila.get('Advertiser ID') or '').strip()
        estado = (fila.get('Membership Status') or '').strip().lower()
        if mid in comercios and estado in ('active', 'joined', ''):
            fids.append((fila.get('Feed ID') or '').strip())
            vistos.add(mid)
    fids = [f for f in fids if f]
    if not fids:
        raise RuntimeError('la lista de feeds de Awin no trae ninguno de los comercios ' + ','.join(sorted(comercios)))
    cols = 'aw_product_id,merchant_id,merchant_deep_link,search_price,rrp_price,product_price_old,currency'
    out = {}
    for i in range(0, len(fids), 10):
        url = (f'https://productdata.awin.com/datafeed/download/apikey/{key}/language/any/fid/'
               f'{",".join(fids[i:i + 10])}/columns/{cols}/format/csv/delimiter/%2C/compression/gzip/adultcontent/1/')
        raw = pedir(url, timeout=600)
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        for f in csv.DictReader(io.StringIO(raw.decode('utf-8', 'replace'))):
            mid = (f.get('merchant_id') or '').strip()
            p = precio(f.get('search_price'), f.get('rrp_price') or f.get('product_price_old'), f.get('currency'))
            if not p:
                continue
            if f.get('aw_product_id'):
                out.setdefault((mid, 'p:' + f['aw_product_id'].strip()), p)
            if f.get('merchant_deep_link'):
                out.setdefault((mid, 'u:' + clave_url(f['merchant_deep_link'])), p)
    faltan = sorted(set(comercios) - vistos)
    return out, ('sin feed en la cuenta para los comercios ' + ', '.join(faltan)) if faltan else ''


def feed_rakuten(marcas):
    """FragranceNet por la API Product Search de Rakuten Advertising (la misma del cruce del 2026-11-05).
    Secretos: RAKUTEN_CLIENT_ID y RAKUTEN_CLIENT_SECRET (credenciales OAuth de la cuenta), RAKUTEN_SID
    (id del sitio) y RAKUTEN_FRAGRANCENET_MID (id del comercio FragranceNet en Rakuten, 216).
    Token: OAuth client_credentials con Basic auth (client_id:client_secret) y scope = SID."""
    cid, csec, sid, mid = env('RAKUTEN_CLIENT_ID', 'RAKUTEN_CLIENT_SECRET', 'RAKUTEN_SID', 'RAKUTEN_FRAGRANCENET_MID')
    basic = base64.b64encode(f'{cid}:{csec}'.encode()).decode()

    def token():
        return json.loads(pedir('https://api.linksynergy.com/token',
                                data=urllib.parse.urlencode({'grant_type': 'client_credentials',
                                                             'scope': sid}).encode(),
                                headers={'Authorization': 'Basic ' + basic,
                                         'Content-Type': 'application/x-www-form-urlencoded'}))['access_token']

    tok = token()
    t0, out, fallos = time.time(), {}, 0
    for marca in marcas:
        if time.time() - t0 > 3000:          # renovar el token antes de la hora
            tok = token()
            t0 = time.time()
        pagina, total = 1, 1
        while pagina <= total and pagina <= 100:
            q = urllib.parse.urlencode({'keyword': '"' + marca + '"', 'mid': mid, 'max': 100, 'pagenumber': pagina})
            try:
                raw = pedir('https://api.linksynergy.com/productsearch/1.0?' + q,
                            headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/xml'})
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise
                fallos += 1
                break
            r = ET.fromstring(raw)
            total = int(r.findtext('TotalPages') or 0)
            for it in r.iter('item'):
                sku = (it.findtext('sku') or '').strip()
                pr, sp = it.find('price'), it.find('saleprice')
                mon = (sp.get('currency') if sp is not None else None) or (pr.get('currency') if pr is not None else 'USD')
                p = precio(sp.text if sp is not None else None, pr.text if pr is not None else None, mon or 'USD')
                if sku and p:
                    out.setdefault(('fragrancenet', sku), p)
            pagina += 1
            time.sleep(0.7)                  # bajo el límite de llamadas por minuto
    return out, (f'{fallos} marcas con error de la API') if fallos else ''


def feed_cj(tiendas):
    """Tiendas CJ (Perfumania, FragranceShop, Perfume Giants, eCosmetics) por la API de productos de CJ
    (GraphQL). Secretos: CJ_TOKEN (Personal Access Token, developers.cj.com) y CJ_CID (Company ID del
    publisher). Opcionales: CJ_<TIENDA>_ID (id del anunciante; sin él se filtran los anunciantes con alianza
    por palabra clave y se reconoce la tienda por el dominio del enlace)."""
    tok, cid = env('CJ_TOKEN', 'CJ_CID')
    out, notas = {}, []
    for tienda in sorted(tiendas):
        if tienda not in CJ_TIENDAS:
            continue
        dom, _, secreto = CJ_TIENDAS[tienda]
        adv = os.environ.get(secreto, '').strip()
        filtro = f'partnerIds: ["{adv}"]' if adv else f'partnerStatus: JOINED, keywords: ["{dom.split(".")[0]}"]'
        offset, total, n = 0, 1, 0
        try:
            while offset < total and offset < 100000:
                q = ('{ shoppingProducts(companyId: "%s", %s, limit: 1000, offset: %d) '
                     '{ totalCount count resultList { link price { amount currency } salePrice { amount currency } } } }'
                     % (cid, filtro, offset))
                r = json.loads(pedir('https://ads.api.cj.com/query', data=json.dumps({'query': q}).encode(),
                                     headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}))
                if r.get('errors'):
                    raise RuntimeError('; '.join(e.get('message', '?') for e in r['errors'])[:300])
                d = r['data']['shoppingProducts']
                total = int(d.get('totalCount') or 0)
                lote = d.get('resultList') or []
                if not lote:
                    break
                for it in lote:
                    k = clave_cj(tienda, it.get('link') or '')
                    if not k:
                        continue
                    pr, sp = it.get('price') or {}, it.get('salePrice') or {}
                    p = precio(sp.get('amount'), pr.get('amount'), sp.get('currency') or pr.get('currency'))
                    if p and (tienda, k) not in out:
                        out[(tienda, k)] = p
                        n += 1
                offset += len(lote)
        except Exception as e:  # noqa: BLE001 — una tienda caída no tumba a las demás de CJ
            notas.append(f'{tienda}: {type(e).__name__}: {e}'[:200])
            continue
        notas.append(f'{tienda} {n}')
    return out, '; '.join(notas)


# ---------------------------------------------------------------- corrida
def correr():
    ind = json.load(open(INDICE, encoding='utf-8'))
    fichas = ind['fichas']
    anterior = {}
    if os.path.exists(SALIDA):
        anterior = json.load(open(SALIDA, encoding='utf-8'))
    fuentes_ant = anterior.get('_fuentes', {})
    semilla = anterior.get('_semilla_fecha', '')

    redes = {}  # red -> {tiendas}
    comercios_awin = set()
    for links in fichas.values():
        for tienda, (red, comercio, _) in links.items():
            redes.setdefault(red, set()).add(tienda)
            if red == 'awin':
                comercios_awin.add(comercio)

    tablas, estado = {}, {}
    trabajos = {'awin': lambda: feed_awin(comercios_awin),
                'rakuten': lambda: feed_rakuten(ind.get('marcas_fragrancenet', [])),
                'cj': lambda: feed_cj(redes.get('cj', set()))}
    for red, fn in trabajos.items():
        if red not in redes:
            continue
        t = time.time()
        try:
            tabla, nota = fn()
            if not tabla:
                raise RuntimeError('el feed llegó vacío')
            tablas[red] = tabla
            estado[red] = ('ok', f'{len(tabla)} productos con precio' + (f'; {nota}' if nota else ''))
        except SinCredencial as e:
            estado[red] = ('bloqueado', str(e))
        except Exception as e:  # noqa: BLE001 — una red caída no tumba a las demás
            estado[red] = ('error', f'{type(e).__name__}: {e}'[:300])
        print(red, estado[red][0], estado[red][1], f'({time.time() - t:.0f} s)', flush=True)

    hoy = datetime.date.fromisoformat(HOY)
    precios, fuentes, cuentas = {}, {}, {}
    for fid, links in fichas.items():
        for tienda, (red, comercio, clave) in links.items():
            c = cuentas.setdefault(tienda, {'enlaces': 0, 'con_precio': 0})
            c['enlaces'] += 1
            if red in tablas:
                p = tablas[red].get((comercio, clave))
                fuentes[tienda] = {'fecha': HOY, 'origen': 'feed ' + red}
            else:
                f = fuentes_ant.get(tienda) or ({'fecha': semilla, 'origen': 'cruce del paquete .31'} if semilla else None)
                vivo = f and f.get('fecha') and (hoy - datetime.date.fromisoformat(f['fecha'])).days <= MAX_DIAS
                p = anterior.get('precios', {}).get(fid, {}).get(tienda) if vivo else None
                if vivo:
                    fuentes[tienda] = f
            if p:
                precios.setdefault(fid, {})[tienda] = p
                c['con_precio'] += 1

    salida = {'_nota': 'Precio de cada enlace de tiendas.json según el feed de afiliado de su tienda. '
                       'Formato: ficha -> tienda -> [precio, moneda] o [precio, moneda, precio_de_lista]. '
                       'Lo publica cada noche .github/workflows/precios.yml.',
              'generado': HOY, '_fuentes': fuentes, 'precios': precios}
    if semilla:
        salida['_semilla_fecha'] = semilla
    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, separators=(',', ':'))

    # Informe para el resumen de la corrida en Actions.
    lin = [f'## Precios {HOY}', '', '| Red | Estado | Detalle |', '|---|---|---|']
    for red in sorted(redes):
        e = estado.get(red, ('—', ''))
        lin.append(f'| {red} ({", ".join(sorted(redes[red]))}) | {e[0]} | {e[1]} |')
    lin += ['', '| Tienda | Enlaces | Con precio | Fuente |', '|---|---|---|---|']
    for t in sorted(cuentas):
        f = fuentes.get(t)
        lin.append(f'| {t} | {cuentas[t]["enlaces"]} | {cuentas[t]["con_precio"]} | '
                   f'{(f["origen"] + " " + f["fecha"]) if f else "sin precio"} |')
    lin += ['', f'Total: {sum(len(v) for v in precios.values())} enlaces con precio en {len(precios)} fichas.']
    informe = '\n'.join(lin)
    print(informe)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(informe + '\n')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'indice':
        hacer_indice(sys.argv[2])
    else:
        correr()
