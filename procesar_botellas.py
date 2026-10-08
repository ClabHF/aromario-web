#!/usr/bin/env python3
"""
procesar_botellas.py - Re-recorta en masa las imágenes de images/botellas/.

- Quita fondo, sombras proyectadas y reflejos de la base (rembg + refinado).
- Bordes anti-aliasados, sin halos blancos ni "mordidas".
- Rellena los huecos internos del vidrio transparente (el frasco queda sólido/translúcido).
- Guarda PNG RGBA con fondo 100% transparente, MISMO nombre y MISMO tamaño de lienzo.
- Reemplaza el archivo original (escritura atómica). No crea carpetas.

Uso:
    python procesar_botellas.py --limit 3          # prueba con 3 imágenes
    python procesar_botellas.py                    # procesa todos los PNG de images/botellas/
"""
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

# --------------------------------------------------------------------------
# Refinado de máscara (función pura: se puede probar sin rembg)
# --------------------------------------------------------------------------

def _largest_components(mask: np.ndarray, min_frac: float = 0.02) -> np.ndarray:
    """Conserva el componente mayor y los que midan >= min_frac de él (tapón + cuerpo)."""
    lab, n = ndi.label(mask)
    if n <= 1:
        return mask
    sizes = ndi.sum(mask, lab, index=range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * min_frac]
    return np.isin(lab, keep)


def refine(rgba: np.ndarray, model_alpha: np.ndarray, keep_margin: float = 0.006,
           glass_alpha: int = 90) -> np.ndarray:
    """
    rgba:        imagen original (H,W,4) uint8
    model_alpha: máscara del modelo (H,W) uint8 0..255 (rembg)
    Devuelve RGBA (H,W,4) uint8 con alfa suave, sin halos y sin sombras.
    """
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3].copy()
    a0 = rgba[:, :, 3]

    # 1) Silueta del modelo (sin sombras), rellenando huecos de vidrio
    s_model = _largest_components(model_alpha > 127)
    s_model = ndi.binary_fill_holes(s_model)

    # 2) Silueta original, limitada a un margen alrededor de la del modelo
    #    (recupera partes blancas que el modelo se comió, pero descarta sombras lejanas)
    # (el fondo negro opaco horneado en algunas imágenes se excluye: solo vale lo que no es matte)
    cand = (a0 > 127) & (rgb.max(axis=2) <= 12)
    lab_m, _ = ndi.label(cand)
    outside = cv2.dilate((a0 <= 127).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    outside[0, :] = outside[-1, :] = outside[:, 0] = outside[:, -1] = True
    touch = np.unique(lab_m[outside & cand])
    matte = np.isin(lab_m, touch[touch > 0])
    s_orig = ndi.binary_fill_holes((a0 > 127) & ~matte)
    k = max(2, int(round(keep_margin * max(h, w))))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    near = cv2.dilate(s_model.astype(np.uint8), kernel).astype(bool)
    sil = s_model | (s_orig & near)
    sil = _largest_components(sil)
    sil = ndi.binary_fill_holes(sil)

    # 3) Limpieza morfológica (rebabas de 1-2 px, agujeros diminutos)
    ker3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    sil_u8 = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_OPEN, ker3)
    sil_u8 = cv2.morphologyEx(sil_u8, cv2.MORPH_CLOSE, ker3)
    sil = ndi.binary_fill_holes(sil_u8.astype(bool))

    # 4) Vidrio: huecos + manchas claras conectadas a ellos -> una sola zona uniforme
    opaque0 = (a0 > 127) & sil
    hole = sil & ~opaque0
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    bright = opaque0 & (hsv[:, :, 2] > 185) & (hsv[:, :, 1] < 55)
    glass = np.zeros_like(sil)
    if hole.sum() > 0.002 * sil.sum():
        lab, n = ndi.label(bright | hole)
        ids = np.unique(lab[hole])
        glass = np.isin(lab, ids[ids > 0])
        inner = cv2.erode(sil.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
        glass &= inner
        glass = cv2.morphologyEx(glass.astype(np.uint8), cv2.MORPH_CLOSE,
                                 cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(bool) & sil
    if glass.any():
        ref = opaque0 & ~glass & (hsv[:, :, 2] > 60)
        near_glass = cv2.dilate(glass.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))).astype(bool)
        sample = ref & near_glass
        base = rgb[sample].mean(0) if sample.any() else np.array([200, 215, 230.0])
        tint = (base * 0.18 + 255 * 0.82).clip(0, 255).astype(np.uint8)
        rgb[glass] = tint

    # 5) Descontaminar borde: los 3 px exteriores toman el color del interior (adiós halo blanco)
    core = cv2.erode(sil.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
    if core.any():
        _, (cy, cx) = ndi.distance_transform_edt(~core, return_indices=True)
        edge_band = sil & ~core
        rgb[edge_band] = rgb[cy, cx][edge_band]

    # 6) Alfa anti-aliasado: erosiona 1 px y suaviza (borde limpio, sin escalones)
    eroded = cv2.erode(sil.astype(np.uint8), ker3).astype(np.float32)
    alpha = cv2.GaussianBlur(eroded, (0, 0), sigmaX=0.9)
    alpha = np.clip((alpha - 0.05) / 0.9, 0, 1)
    alpha = (alpha * 255).astype(np.uint8)

    # 7) Vidrio translúcido uniforme (bordes suaves hacia el cuerpo opaco)
    if glass.any():
        g = cv2.GaussianBlur(glass.astype(np.float32), (0, 0), sigmaX=1.5)
        target = alpha.astype(np.float32) * (1 - g) + np.minimum(alpha, glass_alpha).astype(np.float32) * g
        alpha = target.clip(0, 255).astype(np.uint8)

    alpha[~sil & (alpha < 8)] = 0
    rgb[alpha == 0] = 0
    return np.dstack([rgb, alpha])


# --------------------------------------------------------------------------
# rembg
# --------------------------------------------------------------------------

def make_session(model_name: str):
    from rembg import new_session
    return new_session(model_name)


def model_mask(session, rgba: np.ndarray) -> np.ndarray:
    """Pasa la imagen (compuesta sobre blanco) por rembg y devuelve solo la máscara."""
    from rembg import remove
    img = Image.fromarray(rgba, "RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    out = remove(
        bg.convert("RGB"),
        session=session,
        only_mask=True,
        post_process_mask=True,
        alpha_matting=False,
    )
    return np.array(out.convert("L"))


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def select_files(folder: Path, only: list[str]) -> list[Path]:
    files = sorted(p for p in folder.glob("*.png") if p.is_file())
    if only:
        wanted = set(only)
        return [p for p in files if p.name in wanted]
    return files


def save_atomic(arr: np.ndarray, dest: Path) -> None:
    """Escribe en un temporal dentro de la misma carpeta y reemplaza (mismo nombre final)."""
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=dest.parent)
    os.close(fd)
    try:
        Image.fromarray(arr, "RGBA").save(tmp, format="PNG", optimize=True)
        with Image.open(tmp) as chk:  # verificación antes de reemplazar
            assert chk.size == (arr.shape[1], arr.shape[0]) and chk.mode == "RGBA"
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="images/botellas", help="carpeta de imágenes (por defecto images/botellas)")
    ap.add_argument("--model", default="isnet-general-use",
                    help="modelo rembg: isnet-general-use (rápido, recomendado) o birefnet-general (más fino, más lento)")
    ap.add_argument("--only", nargs="*", default=[], help="procesar solo estos nombres de archivo")
    ap.add_argument("--limit", type=int, default=0, help="procesar solo las N primeras (pruebas)")
    ap.add_argument("--glass-alpha", type=int, default=90, help="opacidad 0-255 del vidrio vacío (por defecto 90)")
    ap.add_argument("--keep-margin", type=float, default=0.006, help="margen de recuperación vs silueta original")
    ap.add_argument("--force", action="store_true", help="reprocesar aunque ya conste en el registro")
    args = ap.parse_args()

    folder = Path(args.dir)
    if not folder.is_dir():
        print(f"No existe la carpeta {folder}. Ejecuta el script desde la raíz del repo.", file=sys.stderr)
        return 1

    log_path = Path(__file__).with_name("procesar_botellas.log")
    done = set(log_path.read_text(encoding="utf-8").split("\n")) if log_path.exists() and not args.force else set()

    files = select_files(folder, args.only)
    todo = [p for p in files if p.name not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(files)} archivos seleccionados, {len(todo)} por procesar (registro: {log_path.name})")
    if not todo:
        return 0

    session = make_session(args.model)
    t0 = time.time()
    errors = []
    for i, path in enumerate(todo, 1):
        try:
            with Image.open(path) as im:
                rgba = np.array(im.convert("RGBA"))
            m = model_mask(session, rgba)
            out = refine(rgba, m, keep_margin=args.keep_margin, glass_alpha=args.glass_alpha)
            save_atomic(out, path)
            with log_path.open("a", encoding="utf-8") as lf:
                lf.write(path.name + "\n")
            print(f"[{i}/{len(todo)}] OK  {path.name}")
        except Exception as e:  # el original queda intacto si algo falla
            errors.append((path.name, repr(e)))
            print(f"[{i}/{len(todo)}] ERROR {path.name}: {e}", file=sys.stderr)

    print(f"\nListo en {time.time() - t0:.0f}s. Errores: {len(errors)}")
    for n, e in errors:
        print(f"  - {n}: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
