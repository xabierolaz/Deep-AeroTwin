#!/usr/bin/env python3
"""Auto-calibracion del montaje de camara por registro de imagen (Pipeline B).

Alinea la ortofoto PNOA con un frame real optimizando (yaw_m, pitch_m, roll_m,
fov_v) para maximizar la coincidencia de bordes (chamfer simetrico entre mapas
de Canny). No requiere marcas manuales: usa carreteras, linces y bordes de
parcela como estructura.

Uso:
  python register_calib.py --frame-idx 1871
  python register_calib.py --frame-idx 1871 --yaw-m 167 --pitch-m -37 --roll-m 0 --fov 66 --no-opt
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
from scipy.optimize import minimize

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
W, H = 3840, 2160
SW, SH = 960, 540  # resolucion de trabajo para el objetivo (velocidad)


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame-idx", type=int, required=True)
    ap.add_argument("--yaw-m", type=float, default=167.0)
    ap.add_argument("--pitch-m", type=float, default=-37.0)
    ap.add_argument("--roll-m", type=float, default=0.0)
    ap.add_argument("--fov", type=float, default=66.0)
    ap.add_argument("--no-opt", action="store_true")
    ap.add_argument("--trajectory", type=Path, default=Path("out/trajectory_m20_1rr.csv"))
    ap.add_argument("--ortho", type=Path, default=Path("../../tmp/pnoa_flight_area.jpg"))
    ap.add_argument("--ortho-geo", type=Path, default=Path("../../tmp/pnoa_flight_area.geo.json"))
    ap.add_argument("--video", type=Path, default=Path("../../../papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"))
    ap.add_argument("--out-prefix", type=Path, default=Path("../../tmp/register_calib"))
    ap.add_argument("--terrain", type=float, default=256.4)
    args = ap.parse_args()

    traj = list(csv.DictReader(args.trajectory.open(encoding="utf-8")))
    row = traj[args.frame_idx]
    dlat, dlon, dalt = float(row["lat"]), float(row["lon"]), float(row["alt_msl"])
    dyaw, dpit, drol = float(row["yaw"]), float(row["pitch"]), float(row["roll"])

    geo = json.loads(args.ortho_geo.read_text())
    bbox = geo["bbox"]
    OW, OH = geo["width"], geo["height"]
    ortho = cv2.imread(str(args.ortho))
    ortho_small = cv2.resize(ortho, (OW // 2, OH // 2))
    ortho_edges = cv2.Canny(ortho_small, 60, 160)
    ows, ohs = ortho_small.shape[1], ortho_small.shape[0]

    cap = cv2.VideoCapture(str(args.video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("no frame")
    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    frame_small = cv2.resize(frame, (SW, SH))
    frame_edges = cv2.Canny(frame_small, 60, 160)

    # distancia al borde mas cercano (para chamfer)
    dt_frame = cv2.distanceTransform(255 - frame_edges, cv2.DIST_L2, 3)
    dt_ortho = cv2.distanceTransform(255 - ortho_edges, cv2.DIST_L2, 3)

    def warp_ortho_edges(params):
        yaw_m, pitch_m, roll_m, fv = params
        fy = H / (2 * math.tan(math.radians(fv) / 2))
        fh = 2 * math.degrees(math.atan((W / H) * math.tan(math.radians(fv) / 2)))
        fx = W / (2 * math.tan(math.radians(fh) / 2))
        r_nb = rz(dyaw) @ ry(dpit) @ rx(drol)
        r_m = rz(yaw_m) @ ry(pitch_m) @ rx(roll_m)
        M = np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]]) @ (r_nb @ r_m @ A_BC).T

        def g2p(lat, lon):
            n = math.radians(lat - dlat) * R_EARTH
            e = math.radians(lon - dlon) * R_EARTH * math.cos(math.radians(dlat))
            v = M @ np.array([n, e, dalt - args.terrain])
            if v[2] <= 1e-9:
                return None
            return (v[0] / v[2], v[1] / v[2])

        src, dst = [], []
        for flat in np.linspace(bbox[1] + 0.0003, bbox[3] - 0.0003, 10):
            for flon in np.linspace(bbox[0] + 0.0003, bbox[2] - 0.0003, 10):
                p = g2p(flat, flon)
                if p is None or not (-W < p[0] < 2 * W and -H < p[1] < 2 * H):
                    continue
                ox = (flon - bbox[0]) / (bbox[2] - bbox[0]) * ows
                oy = (bbox[3] - flat) / (bbox[3] - bbox[1]) * ohs
                src.append([ox, oy])
                dst.append([p[0] * SW / W, p[1] * SH / H])
        if len(src) < 8:
            return None
        Hmat, _ = cv2.findHomography(np.array(src, np.float32), np.array(dst, np.float32), 0)
        if Hmat is None:
            return None
        return cv2.warpPerspective(ortho_edges, Hmat, (SW, SH))

    def objective(params):
        warped = warp_ortho_edges(params)
        if warped is None:
            return 1e6
        wf = warped > 0
        n_w = int(wf.sum())
        if n_w < 200:
            return 1e6
        # distancia media de los bordes de la orto warpeada al borde real mas cercano
        return float(dt_frame[wf].mean())

    x0 = np.array([args.yaw_m, args.pitch_m, args.roll_m, args.fov])
    print(f"frame f{args.frame_idx} ypr=({dyaw:.0f},{dpit:.0f},{drol:.0f})  objetivo inicial ({x0.tolist()}): {objective(x0):.3f}")
    if args.no_opt:
        best = x0
    else:
        sol = minimize(objective, x0, method="Nelder-Mead",
                       options={"maxfev": 400, "xatol": 0.15, "fatol": 0.002})
        best = sol.x
        print(f"optimizado: yaw_m={best[0]:.2f} pitch_m={best[1]:.2f} roll_m={best[2]:.2f} fov={best[3]:.2f}  obj={sol.fun:.3f}")

    warped = warp_ortho_edges(best)
    vis = cv2.addWeighted(frame_small, 0.5, cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR), 0.5, 0)
    out_path = args.out_prefix.with_name(args.out_prefix.name + f"_f{args.frame_idx}.jpg")
    cv2.imwrite(str(out_path), vis, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"overlay bordes: {out_path}")
    print("RESULT " + json.dumps({"frame_idx": args.frame_idx, "yaw_m": float(best[0]),
                                  "pitch_m": float(best[1]), "roll_m": float(best[2]),
                                  "fov": float(best[3])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
