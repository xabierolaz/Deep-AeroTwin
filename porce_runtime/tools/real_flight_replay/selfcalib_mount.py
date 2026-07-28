#!/usr/bin/env python3
"""Auto-calibracion del montaje de camara con detecciones YOLO (Pipeline B).

Ejecuta el detector (entrenado en frames rot270/landscape) sobre el video,
convierte el punto cabeza-del-apoyo a coordenadas PORTRAIT (video tal cual se
almacena), y ajusta (mount_yaw, mount_pitch, mount_roll, fov_v, dt, dN, dE, h)
minimizando el error de reproyeccion sobre el GT PNOA (P3) con perdida robusta.

Cientos de detecciones del mismo apoyo a distancias variadas => ajuste bien
condicionado (frente a 4 marcas manuales).

Uso:
  python selfcalib_mount.py [--every 5] [--conf 0.25]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from ultralytics import YOLO

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VIDEO = ROOT.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"
WEIGHTS = OUT / "yolo_tower_real_tower_tracked_v1.pt"

R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
WP, HP = 2160.0, 3840.0   # portrait (almacenado)
WL, HL = 3840.0, 2160.0   # landscape (rot270 CCW)
TERR = 256.4


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def collect_detections(every: int, conf: float):
    model = YOLO(str(WEIGHTS))
    cap = cv2.VideoCapture(str(VIDEO))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dets = []
    idx = 0
    while idx < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, f = cap.read()
        if not ok or f is None:
            break
        f = cv2.rotate(f, cv2.ROTATE_90_COUNTERCLOCKWISE)
        r = model.predict(f, verbose=False, conf=conf, imgsz=1280)[0]
        if r.boxes is not None and len(r.boxes) > 0:
            b = max(r.boxes, key=lambda x: float(x.conf))
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
            # punto cabeza (top-center) en landscape
            u_l = (x1 + x2) / 2.0
            v_l = y1
            # a portrait: x_P = (W_P-1) - v_ccw ; y_P = u_ccw   (rotCCW inversa)
            u_p = (WP - 1.0) - v_l
            v_p = u_l
            dets.append({"frame_idx": idx, "u": u_p, "v": v_p,
                         "conf": float(b.conf),
                         "bbox_l": [x1, y1, x2, y2]})
        idx += every
    cap.release()
    return dets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--f-min", type=int, default=800)
    ap.add_argument("--f-max", type=int, default=2200)
    args = ap.parse_args()

    traj = list(csv.DictReader((OUT / "trajectory_m20_1rr.csv").open(encoding="utf-8")))
    tt = np.array([float(r["t_rel_s"]) for r in traj])
    cols = {k: np.array([float(r[k]) for r in traj]) for k in ("lat", "lon", "alt_msl", "yaw", "pitch", "roll")}
    fps = float(tt[1] - tt[0]) and (len(traj) - 1) / tt[-1]

    poles = {}
    for line in (OUT / "tower_ground_truth.csv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("id,") or not line.strip():
            continue
        p = line.split(",")
        poles[p[0]] = (float(p[1]), float(p[2]))
    P3 = poles["P3"]

    print(f"detectando (cada {args.every} frames, conf>={args.conf})...")
    dets = [d for d in collect_detections(args.every, args.conf) if args.f_min <= d["frame_idx"] <= args.f_max]
    print(f"detecciones: {len(dets)}")

    (OUT / "selfcalib_detections.json").write_text(json.dumps(dets, indent=1), encoding="utf-8")

    def pose_at(trel):
        return tuple(np.interp(trel, tt, cols[k]) for k in ("lat", "lon", "alt_msl", "yaw", "pitch", "roll"))

    def project(params, r_n, ypr):
        yaw_m, pitch_m, roll_m, fv = params
        fy = HP / (2 * math.tan(math.radians(fv) / 2))
        fh = 2 * math.degrees(math.atan((WP / HP) * math.tan(math.radians(fv) / 2)))
        fx = WP / (2 * math.tan(math.radians(fh) / 2))
        dy, dp, dr = ypr
        r_nb = rz(dy) @ ry(dp) @ rx(dr)
        r_m = rz(yaw_m) @ ry(pitch_m) @ rx(roll_m)
        r_c = A_BC.T @ r_m.T @ r_nb.T @ r_n
        if r_c[2] <= 1e-6:
            return None
        return np.array([fx * r_c[0] / r_c[2] + WP / 2, fy * r_c[1] / r_c[2] + HP / 2])

    def residuals(params):
        yaw_m, pitch_m, roll_m, fv, dt, dn, de, h = params
        out = []
        for d in dets:
            lat, lon, alt, yaw, pit, rol = pose_at(d["frame_idx"] / fps + dt)
            lat += math.degrees(dn / R_EARTH)
            lon += math.degrees(de / (R_EARTH * math.cos(math.radians(lat))))
            r_n = np.array([
                math.radians(P3[0] - lat) * R_EARTH,
                math.radians(P3[1] - lon) * R_EARTH * math.cos(math.radians(lat)),
                alt - (TERR + h),
            ])
            pr = project((yaw_m, pitch_m, roll_m, fv), r_n, (yaw, pit, rol))
            if pr is None:
                out.extend([1e3, 1e3])
            else:
                err = (pr - np.array([d["u"], d["v"]])) / 25.0  # escala px -> ~m
                out.extend(err.tolist())
        return np.array(out)

    best = None
    lb = np.array([-180.0, -75.0, -15.0, 50.0, -5.0, -8.0, -8.0, 8.0])
    ub = np.array([180.0, -10.0, 15.0, 110.0, 5.0, 8.0, 8.0, 14.0])
    for y0 in (0.0, -70.0, 90.0, 180.0, -90.0, 135.0):
        for p0 in (-55.0, -40.0, -30.0):
            for fv0 in (60.0, 75.0, 90.0):
                x0 = np.array([y0, p0, 0.0, fv0, 0.0, 0.0, 0.0, 11.0])
                x0 = np.minimum(np.maximum(x0, lb), ub)
                sol = least_squares(residuals, x0, loss="soft_l1", f_scale=2.0, method="trf",
                                    bounds=(lb, ub), max_nfev=40000)
                cost = float(np.mean(sol.fun ** 2))
                if best is None or cost < best[1]:
                    best = (sol, cost)
    sol, cost = best
    yaw_m, pitch_m, roll_m, fv, dt, dn, de, h = (float(v) for v in sol.x)
    yaw_m = (yaw_m + 180.0) % 360.0 - 180.0

    errs = []
    for d in dets:
        lat, lon, alt, yaw, pit, rol = pose_at(d["frame_idx"] / fps + dt)
        lat += math.degrees(dn / R_EARTH)
        lon += math.degrees(de / (R_EARTH * math.cos(math.radians(lat))))
        r_n = np.array([
            math.radians(P3[0] - lat) * R_EARTH,
            math.radians(P3[1] - lon) * R_EARTH * math.cos(math.radians(lat)),
            alt - (TERR + h),
        ])
        pr = project((yaw_m, pitch_m, roll_m, fv), r_n, (yaw, pit, rol))
        errs.append(float(np.hypot(*(pr - np.array([d["u"], d["v"]])))))
    errs = sorted(errs)
    n = len(errs)

    result = {
        "mount_yaw_deg": yaw_m,
        "mount_pitch_deg": pitch_m,
        "mount_roll_deg": roll_m,
        "fov_v_deg": fv,
        "dt_s": dt,
        "gps_offset_ne_m": [dn, de],
        "point_height_m": h,
        "n_detections": n,
        "reproj_px_mean": sum(errs) / n,
        "reproj_px_p50": errs[n // 2],
        "reproj_px_p95": errs[int(0.95 * (n - 1))],
        "img_w": WP,
        "img_h": HP,
        "orientation": "portrait (video tal cual; detector en rot270 + punto desrotado)",
    }
    (OUT / "camera_mount_selfcalib.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\n== auto-calibracion ==")
    print(f"yaw_m={yaw_m:.2f}  pitch_m={pitch_m:.2f}  roll_m={roll_m:.2f}  fov_v={fv:.2f}")
    print(f"dt={dt:+.3f}s  gps_offset=({dn:+.2f},{de:+.2f}) m  h={h:.2f} m")
    print(f"reproyeccion px: mean={result['reproj_px_mean']:.1f}  p50={result['reproj_px_p50']:.1f}  p95={result['reproj_px_p95']:.1f}  (n={n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
