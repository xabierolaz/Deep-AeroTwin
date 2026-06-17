#!/usr/bin/env python3
"""
detail_transfer.py — preserva color+iluminación+geometría del original (Cesium)
e inyecta SOLO la textura/detalle de la salida de difusión.

Idea (espacio Lab):
  L_out = lowpass(L_orig) + gain * highpass(L_gen)     # luz/geometría del original + detalle del gen
  a_out = a_orig ;  b_out = b_orig                      # color BLOQUEADO al original
así Cesium conserva color, iluminación y forma; la difusión solo añade micro-detalle.

Sliders:
  --detail-gain   cuánta textura del gen se inyecta (0=nada, 1=normal, >1 exagera)
  --sigma         escala de separación baja/alta frecuencia (px); mayor = detalle más fino
  --color-mode    lab (color del original) | keep-gen (color del gen) | match (gen recoloreado al original)

Pura cv2/numpy. Vídeo o frame único.

  python neural/detail_transfer.py --original tmp/ejea_clip_input.mp4 \
    --gen neural/StreamDiffusionV2/poc_ejea/output_000.mp4 \
    --output neural/ejea_detail.mp4 --detail-gain 1.0 --sigma 6
"""
import argparse, os, sys
import numpy as np
import cv2


def to_lab(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)


def from_lab(lab):
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def match_color(src_bgr, ref_bgr):
    """Recolorea src para que su media/desv. por canal Lab iguale a ref (AdaIN)."""
    s = to_lab(src_bgr); r = to_lab(ref_bgr)
    for c in range(3):
        ss, sm = s[..., c].std() + 1e-6, s[..., c].mean()
        rs, rm = r[..., c].std() + 1e-6, r[..., c].mean()
        s[..., c] = (s[..., c] - sm) / ss * rs + rm
    return from_lab(s)


def transfer(orig_bgr, gen_bgr, gain, sigma, color_mode):
    if gen_bgr.shape[:2] != orig_bgr.shape[:2]:
        gen_bgr = cv2.resize(gen_bgr, (orig_bgr.shape[1], orig_bgr.shape[0]))
    o = to_lab(orig_bgr); g = to_lab(gen_bgr)
    Lo, Lg = o[..., 0], g[..., 0]
    lo = cv2.GaussianBlur(Lo, (0, 0), sigma)        # iluminación/forma del original
    hg = Lg - cv2.GaussianBlur(Lg, (0, 0), sigma)   # textura/detalle del gen
    L_out = lo + gain * hg
    out = o.copy()
    out[..., 0] = L_out
    if color_mode == "lab":          # color bloqueado al original (recomendado)
        pass                          # a,b ya son del original (out=o.copy())
    elif color_mode == "keep-gen":   # color del gen, luz/geo del original
        out[..., 1] = g[..., 1]; out[..., 2] = g[..., 2]
    elif color_mode == "match":      # color del gen pero ajustado al original
        m = to_lab(match_color(gen_bgr, orig_bgr))
        out[..., 1] = m[..., 1]; out[..., 2] = m[..., 2]
    return from_lab(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--gen", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--detail-gain", type=float, default=1.0)
    ap.add_argument("--sigma", type=float, default=6.0)
    ap.add_argument("--color-mode", default="lab", choices=["lab", "keep-gen", "match"])
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    co = cv2.VideoCapture(args.original); cg = cv2.VideoCapture(args.gen)
    if not co.isOpened() or not cg.isOpened():
        sys.exit("no pude abrir original/gen")
    ow = int(co.get(3)); oh = int(co.get(4)); fps = co.get(5) or 16.0
    n = min(int(co.get(7)), int(cg.get(7)))
    if args.max_frames: n = min(n, args.max_frames)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    vw = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ow, oh))
    w = 0
    for _ in range(n):
        ok1, o = co.read(); ok2, g = cg.read()
        if not (ok1 and ok2): break
        vw.write(transfer(o, g, args.detail_gain, args.sigma, args.color_mode)); w += 1
    co.release(); cg.release(); vw.release()
    print(f"OK {w} frames -> {args.output}")


if __name__ == "__main__":
    main()
