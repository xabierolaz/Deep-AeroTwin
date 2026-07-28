#!/usr/bin/env python3
"""Calibracion del montaje de camara real (Pipeline B, vuelo M_20_1RR).

Ajusta (mount_yaw, mount_pitch, mount_roll, fov_vertical) minimizando el error
de reproyeccion de apoyos con posicion conocida (ortofoto PNOA) sobre pixels
marcados manualmente en frames con pose conocida (trayectoria del .bin).

NOTA SOBRE UNIFICACION: este script hace REPROYECCION INVERSA (world->pixel),
la operacion opuesta a GeoProjector (pixel->world). GeoProjector no expone el
sentido inverso (ray_ned_to_pixel), por lo que este script mantiene sus propias
primitivas geometricas. Las rotaciones y la matriz de alineacion A_BC son
IDENTICAS a las de GeoProjector (pipeline/geo_projector.py: _rot_x/_rot_y/_rot_z
y R_body_cam_align) para garantizar coherencia de convencion. R_EARTH alineado
a 6371000.0 (mismo valor que GeoProjector y constants.py:EARTH_RADIUS_M).

Uso:
  python fit_camera_mount.py \
      --trajectory out/trajectory_m20_1rr.csv \
      --poles out/tower_ground_truth.csv \
      --correspondences correspondences_m20_1rr.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

# Importar las primitivas canonicas de GeoProjector para no duplicar convencion.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
from geo_projector import GeoProjector  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# R_EARTH alineado con GeoProjector/constants.py (antes 6378137.0; la diferencia
# ~0.1% es despreciable para offsets <1 km pero se unifica por coherencia).
R_EARTH = 6371000.0
IMG_W, IMG_H = 3840.0, 2160.0  # tras rotacion 270 del clip 2160x3840

# Matriz de alineacion camara->body, IDENTICA a GeoProjector.R_body_cam_align.
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)


def intrinsics_from_fov(fv_deg: float):
    fy = IMG_H / (2.0 * math.tan(math.radians(fv_deg) / 2.0))
    fh = 2.0 * math.degrees(math.atan((IMG_W / IMG_H) * math.tan(math.radians(fv_deg) / 2.0)))
    fx = IMG_W / (2.0 * math.tan(math.radians(fh) / 2.0))
    return fx, fy, fh


def ned_vector(lat0, lon0, alt0, lat1, lon1, alt1):
    n = math.radians(lat1 - lat0) * R_EARTH
    e = math.radians(lon1 - lon0) * R_EARTH * math.cos(math.radians(lat0))
    d = alt1 - alt0
    return np.array([n, e, -d])  # NED: down positivo -> z = -(alt1-alt0)


def project(params, r_n: np.ndarray, drone_ypr):
    """Reproyeccion world->pixel (sentido inverso a GeoProjector)."""
    yaw_m, pitch_m, roll_m, fv = params
    fx, fy, _ = intrinsics_from_fov(fv)
    cx, cy = IMG_W / 2.0, IMG_H / 2.0
    dy, dp, dr = drone_ypr
    # Rotaciones canonicas de GeoProjector (no duplicadas, delegadas).
    r_nb = GeoProjector._rot_z(dy) @ GeoProjector._rot_y(dp) @ GeoProjector._rot_x(dr)
    r_m = GeoProjector._rot_z(yaw_m) @ GeoProjector._rot_y(pitch_m) @ GeoProjector._rot_x(roll_m)
    r_c = A_BC.T @ r_m.T @ r_nb.T @ r_n
    if r_c[2] <= 1e-6:
        return None
    u = fx * r_c[0] / r_c[2] + cx
    v = fy * r_c[1] / r_c[2] + cy
    return np.array([u, v])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectory", required=True, type=Path)
    ap.add_argument("--poles", required=True, type=Path)
    ap.add_argument("--correspondences", required=True, type=Path,
                    help='JSON: [{"frame_idx":int,"pole_id":"P3","u":px,"v":px}, ...]')
    ap.add_argument("--terrain-msl", type=float, default=None,
                    help="Altitud MSL del suelo en los apoyos (defecto: del meta de la trayectoria o 256.4)")
    args = ap.parse_args()

    traj = list(csv.DictReader(args.trajectory.open(encoding="utf-8")))
    poles = {}
    for line in args.poles.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("id,"):
            continue
        pid, lat, lon = line.split(",")[:3]
        poles[pid.strip()] = (float(lat), float(lon))
    corr_raw = json.loads(args.correspondences.read_text(encoding="utf-8"))
    global IMG_W, IMG_H
    if isinstance(corr_raw, dict):
        IMG_W = float(corr_raw.get("img_w", IMG_W))
        IMG_H = float(corr_raw.get("img_h", IMG_H))
        corr = corr_raw["points"]
    else:
        corr = corr_raw

    terrain = args.terrain_msl
    if terrain is None:
        meta_path = args.trajectory.with_suffix(".meta.json")
        terrain = 256.4
        if meta_path.exists():
            terrain = float(json.loads(meta_path.read_text(encoding="utf-8"))["terrain_ref_msl"])

    samples = []
    for c in corr:
        fi = int(c["frame_idx"])
        row = traj[fi]
        plat, plon = poles[c["pole_id"]]
        dlat, dlon, dalt = float(row["lat"]), float(row["lon"]), float(row["alt_msl"])
        h_m = float(c.get("h_m", 0.0))
        r_n = ned_vector(dlat, dlon, dalt, plat, plon, terrain + h_m)
        ypr = (float(row["yaw"]), float(row["pitch"]), float(row["roll"]))
        samples.append((r_n, ypr, np.array([float(c["u"]), float(c["v"])]), c))
    print(f"muestras: {len(samples)}  apoyos: {sorted({c['pole_id'] for _,_,_,c in samples})}  terreno: {terrain:.1f} m MSL  imagen: {IMG_W:.0f}x{IMG_H:.0f}")

    def residuals(params):
        out = []
        for r_n, ypr, obs, _ in samples:
            pred = project(params, r_n, ypr)
            if pred is None:
                out.extend([1e4, 1e4])
            else:
                out.extend((pred - obs).tolist())
        return np.array(out)

    best = None
    for yaw0 in (0.0, 90.0, 180.0, 270.0, -90.0):
        for pitch0 in (-90.0, -60.0, -45.0, -30.0, -15.0, 0.0):
            x0 = np.array([yaw0, pitch0, 0.0, 75.0])
            sol = least_squares(residuals, x0, method="lm", max_nfev=20000)
            cost = float(np.sum(sol.fun ** 2))
            if best is None or cost < best[1]:
                best = (sol, cost)
    sol, cost = best
    yaw_m, pitch_m, roll_m, fv = (float(v) for v in sol.x)
    yaw_m = (yaw_m + 180.0) % 360.0 - 180.0
    fx, fy, fh = intrinsics_from_fov(fv)
    rms = math.sqrt(cost / (2 * len(samples)))
    print("\n== ajuste ==")
    print(f"mount_yaw   = {yaw_m:8.2f} deg")
    print(f"mount_pitch = {pitch_m:8.2f} deg")
    print(f"mount_roll  = {roll_m:8.2f} deg")
    print(f"fov_v       = {fv:8.2f} deg   (fov_h = {fh:.1f} deg, fx={fx:.0f}px, fy={fy:.0f}px)")
    print(f"RMS reproyeccion = {rms:.1f} px")
    print("\nresiduos por correspondencia:")
    params = sol.x.copy()
    for r_n, ypr, obs, c in samples:
        pred = project(params, r_n, ypr)
        if pred is None:
            print(f"  {c['pole_id']} f{c['frame_idx']}: FUERA DE CAMARA (obs={obs.tolist()})")
        else:
            err = pred - obs
            print(f"  {c['pole_id']} f{c['frame_idx']}: err=({err[0]:+.1f},{err[1]:+.1f}) px  obs={obs.tolist()} pred=({pred[0]:.0f},{pred[1]:.0f})")

    out = {
        "mount_yaw_deg": yaw_m,
        "mount_pitch_deg": pitch_m,
        "mount_roll_deg": roll_m,
        "fov_v_deg": fv,
        "fov_h_deg": fh,
        "rms_px": rms,
        "img_w": IMG_W,
        "img_h": IMG_H,
        "terrain_msl": terrain,
        "n_samples": len(samples),
    }
    out_path = args.correspondences.with_name("camera_mount_fit.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nescrito: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
