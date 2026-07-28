#!/usr/bin/env python3
"""Auto-etiquetado de apoyos en el video real por proyeccion (Pipeline B).

Para cada frame muestreado proyecta los apoyos GT (ortofoto PNOA) sobre la imagen
con el modelo de camara calibrado, y emite cajas YOLO. El montaje se re-estima
por lotes (registro de bordes) para absorber el posible paneo lento de la camara.

Salida: dataset YOLO (images/{train,val}, labels/{train,val}, dataset.yaml),
clase 0 = tower.

Uso:
  python autolabel_towers.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VIDEO = ROOT.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"
ORTHO = ROOT.parent.parent / "tmp/pnoa_flight_area.jpg"
ORTHO_GEO = ROOT.parent.parent / "tmp/pnoa_flight_area.geo.json"

R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
W, H = 3840, 2160          # frame tras rotacion 270
SAVE_W, SAVE_H = 1920, 1080  # resolucion de guardado (labels normalizados: independiente)

T_START_S = 5.0        # los primeros segundos salen oscuros/rojos
LABEL_EVERY_FRAMES = 15
REG_EVERY_S = 3.0
POLE_H_M = 12.0        # altura estimada del apoyo (cabeza sobre terreno)
POLE_W_M = 5.0         # anchura estimada (cruceta)
MIN_DIST_M, MAX_DIST_M = 12.0, 350.0
MIN_BOX_PX = 10
TERRAIN_MSL = 256.4

NOMINAL_MOUNT = (180.0, -35.0, 0.0, 72.0)  # yaw_m, pitch_m, roll_m, fov_v


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def load_inputs():
    traj = list(csv.DictReader((OUT / "trajectory_m20_1rr.csv").open(encoding="utf-8")))
    poles = []
    for line in (OUT / "tower_ground_truth.csv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("id,") or not line.strip():
            continue
        p = line.split(",")
        poles.append({"id": p[0].strip(), "lat": float(p[1]), "lon": float(p[2])})
    geo = json.loads(ORTHO_GEO.read_text(encoding="utf-8"))
    return traj, poles, geo


class Register:
    """Re-estima (yaw_m, pitch_m, fov) por lotes via registro de bordes orto<->frame."""

    SW, SH = 960, 540

    def __init__(self, traj, geo):
        self.traj = traj
        self.bbox = geo["bbox"]
        self.ows, self.ohs = geo["width"] // 2, geo["height"] // 2
        ortho = cv2.imread(str(ORTHO))
        ortho_small = cv2.resize(ortho, (self.ows, self.ohs))
        self.ortho_edges = cv2.cvtColor(ortho_small, cv2.COLOR_BGR2GRAY)
        self.ortho_edges = cv2.Canny(ortho_small, 60, 160)
        self.schedule = []  # (t_rel_s, yaw_m, pitch_m, fov, obj)

    def estimate(self, frame_bgr, t_rel: float, row, x0):
        frame_small = cv2.resize(frame_bgr, (self.SW, self.SH))
        frame_edges = cv2.Canny(frame_small, 60, 160)
        dt_frame = cv2.distanceTransform(255 - frame_edges, cv2.DIST_L2, 3)
        dlat, dlon, dalt = float(row["lat"]), float(row["lon"]), float(row["alt_msl"])
        dyaw, dpit, drol = float(row["yaw"]), float(row["pitch"]), float(row["roll"])
        bbox = self.bbox
        # cuenca validada por correspondencias de apoyos: no salir de aqui
        BOUNDS = ((140.0, 220.0), (-52.0, -25.0), (-5.0, 5.0), (55.0, 85.0))

        def clip(params):
            return np.array([min(max(v, lo), hi) for v, (lo, hi) in zip(params, BOUNDS)])

        def warp(params):
            yaw_m, pitch_m, _, fv = params
            fy = H / (2 * math.tan(math.radians(fv) / 2))
            fh = 2 * math.degrees(math.atan((W / H) * math.tan(math.radians(fv) / 2)))
            fx = W / (2 * math.tan(math.radians(fh) / 2))
            r_nb = rz(dyaw) @ ry(dpit) @ rx(drol)
            r_m = rz(yaw_m) @ ry(pitch_m) @ rx(0.0)
            M = np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]]) @ (r_nb @ r_m @ A_BC).T
            src, dst = [], []
            for flat in np.linspace(bbox[1] + 0.0003, bbox[3] - 0.0003, 10):
                for flon in np.linspace(bbox[0] + 0.0003, bbox[2] - 0.0003, 10):
                    n = math.radians(flat - dlat) * R_EARTH
                    e = math.radians(flon - dlon) * R_EARTH * math.cos(math.radians(dlat))
                    v = M @ np.array([n, e, dalt - TERRAIN_MSL])
                    if v[2] <= 1e-9:
                        continue
                    u, w_ = v[0] / v[2], v[1] / v[2]
                    if not (-W < u < 2 * W and -H < w_ < 2 * H):
                        continue
                    ox = (flon - bbox[0]) / (bbox[2] - bbox[0]) * self.ows
                    oy = (bbox[3] - flat) / (bbox[3] - bbox[1]) * self.ohs
                    src.append([ox, oy])
                    dst.append([u * self.SW / W, w_ * self.SH / H])
            if len(src) < 8:
                return None
            Hmat, _ = cv2.findHomography(np.array(src, np.float32), np.array(dst, np.float32), 0)
            if Hmat is None:
                return None
            return cv2.warpPerspective(self.ortho_edges, Hmat, (self.SW, self.SH))

        def obj(params):
            w_ = warp(clip(params))
            if w_ is None:
                return 1e6
            wf = w_ > 0
            if int(wf.sum()) < 200:
                return 1e6
            return float(dt_frame[wf].mean())

        sol = minimize(obj, np.array(x0), method="Nelder-Mead",
                       options={"maxfev": 200, "xatol": 0.3, "fatol": 0.005})
        yaw_m, pitch_m, fov = (float(v) for v in clip(sol.x)[[0, 1, 3]])
        self.schedule.append((t_rel, yaw_m, pitch_m, fov, float(sol.fun)))
        return yaw_m, pitch_m, fov, float(sol.fun)

    def mount_at(self, t_rel: float):
        if not self.schedule:
            return NOMINAL_MOUNT
        sch = sorted(self.schedule)
        good = [s for s in sch if s[4] < 8.0]
        ref = good if good else sch
        best = min(ref, key=lambda s: abs(s[0] - t_rel))
        return (best[1], best[2], 0.0, best[3])


def project_point(row, mount, lat, lon, alt_msl):
    yaw_m, pitch_m, roll_m, fv = mount
    fy = H / (2 * math.tan(math.radians(fv) / 2))
    fh = 2 * math.degrees(math.atan((W / H) * math.tan(math.radians(fv) / 2)))
    fx = W / (2 * math.tan(math.radians(fh) / 2))
    dlat, dlon, dalt = float(row["lat"]), float(row["lon"]), float(row["alt_msl"])
    r_nb = rz(float(row["yaw"])) @ ry(float(row["pitch"])) @ rx(float(row["roll"]))
    r_m = rz(yaw_m) @ ry(pitch_m) @ rx(roll_m)
    M = np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]]) @ (r_nb @ r_m @ A_BC).T
    n = math.radians(lat - dlat) * R_EARTH
    e = math.radians(lon - dlon) * R_EARTH * math.cos(math.radians(dlat))
    v = M @ np.array([n, e, dalt - alt_msl])
    if v[2] <= 1e-9:
        return None, None
    return (v[0] / v[2], v[1] / v[2]), v[2]


def main() -> int:
    traj, poles, geo = load_inputs()
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"video: {n_frames} frames @ {fps:.3f} fps")

    ds = OUT / "dataset"
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (ds / sub).mkdir(parents=True, exist_ok=True)
    (ds / "dataset.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: tower\n", encoding="utf-8")

    reg = Register(traj, geo)
    x0 = np.array([NOMINAL_MOUNT[0], NOMINAL_MOUNT[1], NOMINAL_MOUNT[2], NOMINAL_MOUNT[3]])

    stats = {"frames": 0, "labeled": 0, "boxes": 0, "reg_ok": 0, "reg_fallback": 0}
    last_reg_t = -1e9
    fi = int(T_START_S * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)  # un solo seek; el resto es lectura secuencial
    while fi < n_frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        t_rel = fi / fps
        row = traj[fi]

        if t_rel >= 8.0 and t_rel - last_reg_t >= REG_EVERY_S:
            # siempre desde el montaje nominal validado: evita deriva de cuenca
            yaw_m, pitch_m, fov, obj = reg.estimate(frame, t_rel, row, x0)
            if obj < 8.0:
                stats["reg_ok"] += 1
            else:
                stats["reg_fallback"] += 1
            last_reg_t = t_rel
            print(f"  [reg] t={t_rel:5.1f}s yaw_m={yaw_m:6.1f} pitch_m={pitch_m:5.1f} fov={fov:4.1f} obj={obj:.2f}")

        if fi % LABEL_EVERY_FRAMES == 0:
            mount = reg.mount_at(t_rel)
            labels = []
            for pole in poles:
                base, _ = project_point(row, mount, pole["lat"], pole["lon"], TERRAIN_MSL)
                top, depth = project_point(row, mount, pole["lat"], pole["lon"], TERRAIN_MSL + POLE_H_M)
                if base is None or top is None or depth is None:
                    continue
                dist = math.hypot(
                    math.radians(pole["lat"] - float(row["lat"])) * R_EARTH,
                    math.radians(pole["lon"] - float(row["lon"])) * R_EARTH * math.cos(math.radians(float(row["lat"]))),
                )
                if not (MIN_DIST_M <= dist <= MAX_DIST_M):
                    continue
                bx, by = base
                tx, ty = top
                if not (-80 < bx < W + 80 and -80 < by < H + 80):
                    continue
                height_px = abs(by - ty)
                fy_ = H / (2 * math.tan(math.radians(mount[3]) / 2))
                width_px = max(0.7 * height_px, fy_ * POLE_W_M / max(depth, 1.0))
                # margen por incertidumbre GPS/GT (~2.5 m), acotado
                margin_px = min(fy_ * 2.5 / max(depth, 1.0), 0.5 * width_px)
                x1 = min(bx, tx) - width_px / 2 - margin_px
                x2 = max(bx, tx) + width_px / 2 + margin_px
                y1 = ty - 0.15 * height_px
                y2 = by + 0.10 * height_px
                x1, x2 = max(0.0, x1), min(float(W), x2)
                y1, y2 = max(0.0, y1), min(float(H), y2)
                if (x2 - x1) < MIN_BOX_PX or (y2 - y1) < MIN_BOX_PX:
                    continue
                cx = ((x1 + x2) / 2) / W
                cy = ((y1 + y2) / 2) / H
                labels.append((0, cx, cy, (x2 - x1) / W, (y2 - y1) / H))

            split = "train" if t_rel < 50.0 else "val"
            name = f"f{fi:05d}"
            cv2.imwrite(str(ds / "images" / split / f"{name}.jpg"),
                        cv2.resize(frame, (SAVE_W, SAVE_H)), [cv2.IMWRITE_JPEG_QUALITY, 90])
            with (ds / "labels" / split / f"{name}.txt").open("w", encoding="utf-8") as f:
                for cls, cx, cy, bw, bh in labels:
                    f.write(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            stats["frames"] += 1
            stats["boxes"] += len(labels)
            if labels:
                stats["labeled"] += 1

        fi += 1
    cap.release()
    print(f"\n== auto-etiquetado == frames guardados: {stats['frames']} (con cajas: {stats['labeled']}), "
          f"cajas totales: {stats['boxes']}, registros ok: {stats['reg_ok']}, fallback: {stats['reg_fallback']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
