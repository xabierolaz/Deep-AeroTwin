#!/usr/bin/env python3
"""Etiquetado por tracking del apoyo P3 en el video real (Pipeline B).

Siembra un tracker CSRT con una caja manual en el frame 1871 (t=32) y sigue el
apoyo hacia atras y hacia adelante en el tiempo, generando etiquetas YOLO por
frame. Guarda tiras de verificacion para inspeccion visual.

El tracker es apariencia-pura: no depende de la calibracion de camara.

Uso:
  python track_label_towers.py
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import cv2

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VIDEO = ROOT.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--rotate", type=int, default=0, help="0|90|180|270 grados (cv2). 0 = portrait tal cual")
_ap.add_argument("--width", type=int, default=2160)
_ap.add_argument("--height", type=int, default=3840)
_ap.add_argument("--seed-frame", type=int, default=1871)
_ap.add_argument("--seed-box", type=int, nargs=4, default=[930, 1540, 240, 470], metavar=("X", "Y", "W", "H"))
_ap.add_argument("--dataset-name", default="dataset_tracked_portrait")
_ap.add_argument("--label-every", type=int, default=5)
_ap.add_argument("--video", type=str, default=str(VIDEO))
_ap.add_argument("--t-min", type=float, default=15.0)
_ap.add_argument("--t-max", type=float, default=44.0)
_args = _ap.parse_args()

VIDEO = Path(_args.video)

W, H = _args.width, _args.height
SAVE_W, SAVE_H = 1920, 1080

SEED_FRAME = _args.seed_frame
SEED_BOX = tuple(_args.seed_box)
ROTATE = _args.rotate % 360
T_MIN_S, T_MAX_S = _args.t_min, _args.t_max
LABEL_EVERY = _args.label_every
VERIFY_EVERY = 30
TRAIN_END_S = 32.0       # train = ida+aproximacion; val = alejamiento (vistas nuevas)


def make_tracker():
    # Tracker por plantilla (matchTemplate multi-escala con actualizacion EMA).
    # Robusto para el apoyo moviendose suave; sin dependencias de contrib.
    class TemplateTracker:
        SCALES = (0.8, 1.0, 1.25)
        TPL = 160  # tamano de plantilla de trabajo

        def init(self, frame, box):
            x, y, w, h = box
            self.box = [float(x), float(y), float(w), float(h)]
            crop = frame[int(y):int(y + h), int(x):int(x + w)]
            self.tpl = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (self.TPL, self.TPL))
            self.score = 1.0

        def update(self, frame):
            x, y, w, h = self.box
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cx, cy = x + w / 2, y + h / 2
            sw, sh = w * 2.6, h * 2.6
            x1, y1 = max(0, int(cx - sw / 2)), max(0, int(cy - sh / 2))
            x2, y2 = min(W, int(cx + sw / 2)), min(H, int(cy + sh / 2))
            search = gray[y1:y2, x1:x2]
            best = None
            for s in self.SCALES:
                tw, th = max(16, int(w * s)), max(16, int(h * s))
                if search.shape[1] < tw or search.shape[0] < th:
                    continue
                tpl_s = cv2.resize(self.tpl, (tw, th))
                res = cv2.matchTemplate(search, tpl_s, cv2.TM_CCOEFF_NORMED)
                _, mx, _, ml = cv2.minMaxLoc(res)
                if best is None or mx > best[0]:
                    best = (mx, ml, tw, th)
            if best is None:
                return False, self.box
            self.score, (bx, by), bw, bh = best[0], best[1], best[2], best[3]
            nx, ny = x1 + bx, y1 + by
            self.box = [float(nx), float(ny), float(bw), float(bh)]
            # actualizacion EMA de la plantilla
            crop = gray[ny:ny + bh, nx:nx + bw]
            if crop.size > 0:
                tpl_new = cv2.resize(crop, (self.TPL, self.TPL))
                self.tpl = cv2.addWeighted(self.tpl, 0.92, tpl_new, 0.08, 0)
            return self.score >= 0.45, self.box

    return TemplateTracker()


def read_frame(cap, idx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    if not ok or f is None:
        return None
    if ROTATE == 90:
        f = cv2.rotate(f, cv2.ROTATE_90_CLOCKWISE)
    elif ROTATE == 180:
        f = cv2.rotate(f, cv2.ROTATE_180)
    elif ROTATE == 270:
        f = cv2.rotate(f, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return f


def main() -> int:
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    f_min, f_max = int(T_MIN_S * fps), min(int(T_MAX_S * fps), n_frames - 1)

    labels = {}  # frame_idx -> (cx, cy, w, h) normalizado
    verify_dir = OUT / "track_verify"
    verify_dir.mkdir(parents=True, exist_ok=True)

    def run(direction):
        tracker = make_tracker()
        frame = read_frame(cap, SEED_FRAME)
        tracker.init(frame, SEED_BOX)
        idx = SEED_FRAME
        lost = 0
        while True:
            idx += direction
            if idx < f_min or idx > f_max:
                break
            frame = read_frame(cap, idx)
            if frame is None:
                break
            ok, box = tracker.update(frame)
            x, y, w, h = box
            area_ok = w > 12 and h > 12 and w < 1500 and h < 1500
            in_frame = x > -w / 2 and y > -h / 2 and x < W - w / 3 and y < H - h / 3
            if not ok or not area_ok or not in_frame:
                lost += 1
                if lost >= 3:
                    print(f"  tracker perdido en f{idx} (dir={direction:+d})")
                    break
                continue
            lost = 0
            labels[idx] = ((x + w / 2) / W, (y + h / 2) / H, w / W, h / H)
            if idx % VERIFY_EVERY == 0:
                vis = cv2.resize(frame, (SAVE_W, SAVE_H)).copy()
                s = SAVE_W / W
                cv2.rectangle(vis, (int(x * s), int(y * s)), (int((x + w) * s), int((y + h) * s)), (0, 0, 255), 2)
                cv2.imwrite(str(verify_dir / f"trk_f{idx:05d}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 80])

    print("tracking hacia atras...")
    run(-1)
    print("tracking hacia adelante...")
    run(+1)
    cap.release()
    print(f"frames con etiqueta: {len(labels)}  (rango f{min(labels)}..f{max(labels)})")

    # dataset: frames etiquetados (1 de cada LABEL_EVERY) + fondos sin apoyo
    ds = OUT / _args.dataset_name
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (ds / sub).mkdir(parents=True, exist_ok=True)
    (ds / "dataset.yaml").write_text(
        f"path: {ds.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: tower\n",
        encoding="utf-8")

    cap = cv2.VideoCapture(str(VIDEO))
    n_img = n_bg = 0
    for idx in sorted(labels):
        if idx % LABEL_EVERY != 0:
            continue
        frame = read_frame(cap, idx)
        if frame is None:
            continue
        t_rel = idx / fps
        split = "train" if t_rel < TRAIN_END_S else "val"
        name = f"f{idx:05d}"
        cv2.imwrite(str(ds / "images" / split / f"{name}.jpg"),
                    cv2.resize(frame, (SAVE_W, SAVE_H)), [cv2.IMWRITE_JPEG_QUALITY, 90])
        cx, cy, bw, bh = labels[idx]
        with (ds / "labels" / split / f"{name}.txt").open("w", encoding="utf-8") as f:
            f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        n_img += 1
    # fondos: frames sin apoyo a la vista (tramo final + inicial oscuro no)
    for t_s in range(45, 69, 2):
        idx = int(t_s * fps)
        frame = read_frame(cap, idx)
        if frame is None:
            continue
        split = "train" if t_s < 60 else "val"
        name = f"bg{idx:05d}"
        cv2.imwrite(str(ds / "images" / split / f"{name}.jpg"),
                    cv2.resize(frame, (SAVE_W, SAVE_H)), [cv2.IMWRITE_JPEG_QUALITY, 90])
        (ds / "labels" / split / f"{name}.txt").write_text("", encoding="utf-8")
        n_bg += 1
    cap.release()
    print(f"dataset_tracked: {n_img} imagenes con apoyo + {n_bg} fondos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
