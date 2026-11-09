# Precios nocturnos

`.github/workflows/precios.yml` corre cada noche (07:17 UTC) y a mano desde Actions > Precios nocturnos > Run workflow.
Ejecuta `precios.py`, que pone precio a cada enlace de `enlaces.json` con los feeds de afiliados y publica
`/precios.json` (https://aromario.app/precios.json), en el formato que lee la app 1.1.31 (`StorePrices.kt`).

## Secretos (Settings > Secrets and variables > Actions > New repository secret)

| Red (tiendas) | Secreto | Dónde se saca |
|---|---|---|
| Awin (Comas, Nasopia, Parfivo, Parfumbella, Opulensi, Al Jazeera) | `AWIN_FEED_APIKEY` | Awin > Toolbox > Create-a-Feed: la clave que aparece en la URL de descarga (`.../apikey/XXXX/...`) |
| Rakuten (FragranceNet) | `RAKUTEN_CLIENT_ID` | Rakuten Advertising > Links > Web Services: el client_id (OAuth client_credentials) |
| | `RAKUTEN_CLIENT_SECRET` | El mismo panel: el client_secret |
| | `RAKUTEN_SID` | El mismo panel: "Site ID (SID)" (4761161) |
| | `RAKUTEN_FRAGRANCENET_MID` | Advertisers > FragranceNet: el "Advertiser ID / MID" (216) |
| CJ (Perfumania) | `CJ_TOKEN` | developers.cj.com > Personal Access Tokens > crear uno |
| | `CJ_CID` | CJ Account Manager: el "Company ID" (CID) del publisher |
| | `CJ_PERFUMANIA_ID` (opcional) | CJ > Advertisers > Perfumania: su CID de anunciante |

Sin el secreto de una red, esa red queda "bloqueada" y sus tiendas conservan el último precio hasta 14 días.
El resumen de cada corrida (qué redes entraron, cuántos enlaces con precio) queda en la página de la corrida.

## Cuando cambie tiendas.json en la app

```
python3 .github/precios/precios.py indice ruta/a/aromario-app/app/src/main/assets/tiendas.json
```
y commitear `enlaces.json`.

## Firma (1.1.33)

La app 1.1.33+ solo aplica `precios.json` y `verified_photos.json` si su firma (`<archivo>.sig`, ECDSA P-256 /
SHA-256 en base64) valida con la clave pública que lleva dentro (`SignedFiles.kt`).

| Secreto | Qué es |
|---|---|
| `FIRMA_CLAVE_PRIVADA` | La clave privada PEM (PKCS#8) que entregó Claude fuera del repo. Pegarla entera (con las líneas BEGIN/END). |
| `CJ_FRAGRANCESHOP_ID`, `CJ_PERFUMEGIANTS_ID`, `CJ_ECOSMETICS_ID` (opcionales) | CID de anunciante de cada tienda en CJ; si están vacíos, el script lo busca solo entre los anunciantes con alianza de CJ (por dominio). Sin id, la tienda conserva su último precio. |

- `precios.yml` firma su `precios.json` cada noche.
- `firmar.yml` firma `verified_photos.json` (y `precios.json`) cada vez que llegan a main.
- Sin el secreto los archivos se publican sin firmar y la app nueva conserva lo que tenía.
