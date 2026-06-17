#!/usr/bin/env python3
"""
extract_control.py — extrae el vídeo de CONTROL para ControlNet (Wan2.2 Fun Control)
desde el clip de Cesium/Unreal. Es lo que "respeta la geometría de las líneas".

Modos:
  canny     bordes Canny con umbrales automáticos (líneas) — el control clásico.
  lineart   canny sobre imagen suavizada + cierre morfológico = líneas limpias y continuas.
  softedge  gradiente Sobel normalizado (bordes suaves, menos ruido en texturas finas).

Salida: vídeo de control (mismo tamaño/fps), blanco sobre negro, listo para el
nodo de ControlNet. cv2/numpy puro, sin GPU.

  python neural/extract_control.py --video tmp/ejea_clip_input.mp4 \
      --out neural/ejea_control_canny.mp4 --mode canny

Nota: depth (DepthAnything/MiDaS) NO se hace aquí (necesita modelo aparte en GPU);
si quieres depth, se añade en el paso de WSL. Canny/lineart cubren "respetar líneas".
"""
import argparse, os, sys
import numpy as np
import cv2


def auto_canny(gray, sigma=0.33):
    v = np.median(gray)
    lo = int(max(0, (1.0 - sigma) * v))
    hi = int(min(255, (1.0 + sigma) * v))
    return cv2.Canny(gray, lo, hi)


def control_frame(bgr, mode):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if mode == "canny":
        e = auto_canny(gray)
    elif mode == "lineart":
        g = cv2.bilateralFilter(gray, 7, 50, 50)
        e = auto_canny(g)
        e = cv2.morphologyEx(e, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    elif mode == "softedge":
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        mag = (mag / (mag.max() + 1e-6) * 255).astype(np.uint8)
        e = mag
    else:
        raise ValueError(mode)
    return cv2.cvtColor(e, cv2.COLOR_GRAY2BGR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="canny", choices=["canny", "lineart", "softedge"])
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"no pude abrir {args.video}")
    w = int(cap.get(3)); h = int(cap.get(4)); fps = cap.get(5) or 16.0
    n = int(cap.get(7))
    if args.max_frames:
        n = min(n, args.max_frames)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    c = 0
    for _ in range(n):
        ok, f = cap.read()
        if not ok:
            break
        vw.write(control_frame(f, args.mode)); c += 1
    cap.release(); vw.release()
    print(f"OK {c} frames -> {args.out} (mode={args.mode})")


if __name__ == "__main__":
    main()
