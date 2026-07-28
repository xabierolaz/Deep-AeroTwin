#!/usr/bin/env python3
"""Overlay de diagnostico: proyecta la ortofoto PNOA en un frame real con un
montaje de camara candidato (modelo del pipeline), para calibrar visualmente.

Uso:
  python overlay_calib.py --frame-idx 1871 --yaw-m 180 --pitch-m -45 --roll-m 0 --fov 60
Salida: tmp/overlay_calib.jpg (frame real arriba, overlay orto abajo o mezcla)
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

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
PORTRAIT = "--portrait" in sys.argv
W, H = (2160, 3840) if PORTRAIT else (3840, 2160)
for _i, _a in enumerate(sys.argv):
    if _a == "--w" and _i + 1 < len(sys.argv):
        W = int(sys.argv[_i + 1])
    if _a == "--h" and _i + 1 < len(sys.argv):
        H = int(sys.argv[_i + 1])
NATIVE = "--native" in sys.argv


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
    ap.add_argument("--yaw-m", type=float, required=True)
    ap.add_argument("--pitch-m", type=float, required=True)
    ap.add_argument("--roll-m", type=float, default=0.0)
    ap.add_argument("--fov", type=float, required=True)
    ap.add_argument("--gimbal", action="store_true", help="usar solo yaw del dron (modelo gimbal)")
    ap.add_argument("--trajectory", type=Path, default=Path("out/trajectory_m20_1rr.csv"))
    ap.add_argument("--ortho", type=Path, default=Path("../../tmp/pnoa_flight_area.jpg"))
    ap.add_argument("--ortho-geo", type=Path, default=Path("../../tmp/pnoa_flight_area.geo.json"))
    ap.add_argument("--video", type=Path, default=Path("../../../papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"))
    ap.add_argument("--out", type=Path, default=Path("../../tmp/overlay_calib.jpg"))
    ap.add_argument("--w", type=int, default=0)
    ap.add_argument("--h", type=int, default=0)
    ap.add_argument("--native", action="store_true", help="video nativo: no rotar el frame al leerlo")
    ap.add_argument("--portrait", action="store_true", help="video portrait tal cual (2160x3840, sin rotar)")
    ap.add_argument("--dt-s", type=float, default=0.0, help="offset temporal video->pose (s); pose = t_frame + dt")
    ap.add_argument("--terrain", type=float, default=256.4)
    args = ap.parse_args()

    traj = list(csv.DictReader(args.trajectory.open(encoding="utf-8")))
    row = traj[args.frame_idx]
    if abs(args.dt_s) > 1e-9:
        # pose desplazada: interpola la fila en t_frame + dt usando t_rel_s
        import numpy as _np
        tt = _np.array([float(r["t_rel_s"]) for r in traj])
        target = float(row["t_rel_s"]) + float(args.dt_s)
        keys = ("lat", "lon", "alt_msl", "rel_alt", "roll", "pitch", "yaw")
        row = dict(row)
        for k in keys:
            col = _np.array([float(r[k]) for r in traj])
            row[k] = f"{float(_np.interp(target, tt, col)):.8f}"
    dlat, dlon, dalt = float(row["lat"]), float(row["lon"]), float(row["alt_msl"])
    dyaw, dpit, drol = float(row["yaw"]), float(row["pitch"]), float(row["roll"])
    if args.gimbal:
        dpit, drol = 0.0, 0.0

    fv = args.fov
    fy = H / (2 * math.tan(math.radians(fv) / 2))
    fh = 2 * math.degrees(math.atan((W / H) * math.tan(math.radians(fv) / 2)))
    fx = W / (2 * math.tan(math.radians(fh) / 2))
    K = np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]], dtype=float)

    r_nb = rz(dyaw) @ ry(dpit) @ rx(drol)
    r_m = rz(args.yaw_m) @ ry(args.pitch_m) @ rx(args.roll_m)
    # cam->NED rotation para rayos: r_n = R r_c ; R = r_nb r_m A_bc
    R = r_nb @ r_m @ A_BC

    # Homografia suelo->imagen: para cada punto del suelo (N,E,terrain),
    # r_n = [N-n0, E-e0, terr-alt]; pix = K * R^-1 * r_n (escala libre)
    geo = json.loads(args.ortho_geo.read_text())
    bbox = geo["bbox"]; OW, OH = geo["width"], geo["height"]
    terr = args.terrain

    R_inv = R.T
    M = K @ R_inv  # 3x3 que aplica a [dN,dE,dD]

    def ground_to_pix(lat, lon):
        n = math.radians(lat - dlat) * R_EARTH
        e = math.radians(lon - dlon) * R_EARTH * math.cos(math.radians(dlat))
        d = dalt - terr  # NED down positivo: el suelo esta DEBAJO del dron
        v = M @ np.array([n, e, d])
        if v[2] <= 1e-9:
            return None
        return (v[0] / v[2], v[1] / v[2])

    # warp de la orto: malla destino imagen -> para cada celda, homografia inversa
    # construir homografia orto->imagen con 4+ puntos de control
    src, dst = [], []
    for fy_ in np.linspace(bbox[1] + 0.0003, bbox[3] - 0.0003, 8):
        for fx_ in np.linspace(bbox[0] + 0.0003, bbox[2] - 0.0003, 8):
            p = ground_to_pix(fy_, fx_)
            if p is None or not (-W < p[0] < 2 * W and -H < p[1] < 2 * H):
                continue
            ox = (fx_ - bbox[0]) / (bbox[2] - bbox[0]) * OW
            oy = (bbox[3] - fy_) / (bbox[3] - bbox[1]) * OH
            src.append([ox, oy])
            dst.append([p[0], p[1]])
    src = np.array(src, np.float32)
    dst = np.array(dst, np.float32)
    print(f"puntos de control: {len(src)}")

    cap = cv2.VideoCapture(str(args.video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("no frame")
    frame = frame if (PORTRAIT or NATIVE) else cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    ortho = cv2.imread(str(args.ortho))
    Hmat, mask = cv2.findHomography(src, dst, 0)
    warped = cv2.warpPerspective(ortho, Hmat, (W, H))
    blend = cv2.addWeighted(frame, 0.45, warped, 0.55, 0)

    # marcar apoyos GT si existen
    poles_path = Path("out/tower_ground_truth.csv")
    if poles_path.exists():
        for line in poles_path.read_text().splitlines():
            if line.startswith("#") or line.startswith("id,") or not line.strip():
                continue
            parts = line.split(",")
            plat, plon = float(parts[1]), float(parts[2])
            p = ground_to_pix(plat, plon)
            if p is not None:
                cv2.drawMarker(blend, (int(p[0]), int(p[1])), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 60, 4)
                cv2.putText(blend, parts[0], (int(p[0]) + 35, int(p[1]) - 35), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 4)

    small = cv2.resize(blend, (1920, 1080))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out), small, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"frame f{args.frame_idx} t={float(row.get('t_rel_s', row.get('t_unix', 0))):.1f}s dron=({dlat:.6f},{dlon:.6f},{dalt:.0f}) ypr=({dyaw:.0f},{dpit:.0f},{drol:.0f})")
    print(f"mount=({args.yaw_m},{args.pitch_m},{args.roll_m}) fov={fv} gimbal={args.gimbal} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
