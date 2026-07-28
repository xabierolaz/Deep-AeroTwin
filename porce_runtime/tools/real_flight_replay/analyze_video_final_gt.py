# -*- coding: utf-8 -*-
"""video_final (239 real frames) metric study vs PNOA tower ground truth.

Per frame with a tower-class YOLOE detection: project the bbox bottom-center
through the canonical GeoProjector (pipeline/geo_projector.py, Pipeline A motor)
and intersect the terrain plane. Error = horizontal distance to the nearest PNOA
pole (P1-P4, ~1-2 m accuracy). Real telemetry per frame (trajectory_video_final.csv).

Camera model: GeoProjector derives intrinsics from camera_vfov_deg=37.4
(coherent with the previous fx=fy=1421 px crop window 2160x1620 -> 1280x960).
Mount: yaw=21, pitch=-30 (recalibrated 2026-07-23 against the correct video
offset; the legacy camera_mount_fit.json yaw=155/pitch=-37 was calibrated with
the wrong offset and is deprecated). Terrain MSL 256.38 m.

Exploratory post-hoc. Read-only on all inputs.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test")
sys.path.insert(0, str(ROOT / "pipeline"))
from geo_projector import GeoProjector  # canonical Pipeline A projection motor

RFR = ROOT / "tools/real_flight_replay"
TRAJ = RFR / "out/trajectory_video_final.csv"
DETS = ROOT / "experiments/sppa_detection_reference/20260721_video_final_yoloe26s/detections.jsonl"
POLES = RFR / "out/tower_ground_truth.csv"
OUT = ROOT / "experiments/sppa_real_stream_wave/20260721_video_final_gt_study"
TERRAIN_MSL = 256.38
# Mount recalibrado 2026-07-23 (ver camera_mount_fit.json v3). Coherente con
# infer_tower_position.py. El mount legacy yaw=155/pitch=-37 esta deprecado.
MOUNT_YAW_DEG = 21.0
MOUNT_PITCH_DEG = -30.0
MOUNT_ROLL_DEG = 0.0
# FOV vertical coherente con fx=1421 px sobre 1280x960: 2*atan(480/1421)=37.4 deg.
CAMERA_VFOV_DEG = 37.4
MAX_RANGE_M = 300.0
IMG_W, IMG_H = 1280, 960
TOWER_CLASSES = {"power transmission tower", "electric pylon", "utility pole", "antenna tower"}
R_EARTH = 6371000.0
ORIGIN = {"lat": 42.14413817655726, "lon": -1.5882846555030494}  # trajectory centroid


def ll_to_ne(lat, lon):
    x = math.radians(lon - ORIGIN["lon"]) * math.cos(math.radians(ORIGIN["lat"])) * R_EARTH
    y = math.radians(lat - ORIGIN["lat"]) * R_EARTH
    return x, y


def ne_to_ll(x, y):
    lat = ORIGIN["lat"] + math.degrees(y / R_EARTH)
    lon = ORIGIN["lon"] + math.degrees(x / (math.cos(math.radians(ORIGIN["lat"])) * R_EARTH))
    return lat, lon


def main() -> None:
    poles = []
    for line in POLES.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("id,"):
            continue
        pid, lat, lon = line.split(",")[:3]
        poles.append({"id": pid.strip(), "lat": float(lat), "lon": float(lon)})
    for p in poles:
        p["x"], p["y"] = ll_to_ne(p["lat"], p["lon"])

    traj = {}
    with TRAJ.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            traj[int(r["vf_frame"])] = {k: float(r[k]) for k in ("t_unix", "lat", "lon", "alt_msl", "rel_alt", "roll", "pitch", "yaw")}

    rows = []
    for line in DETS.open(encoding="utf-8"):
        ev = json.loads(line)
        k = ev["frame"]
        tel = traj.get(k)
        if tel is None:
            continue
        towers = [d for d in ev["detections"] if d["class_name"] in TOWER_CLASSES]
        if not towers:
            continue
        alt_agl = tel["alt_msl"] - TERRAIN_MSL
        for d in towers:
            b = d["xyxy"]
            x1, y1, x2, y2 = b
            # bottom-center: centro horizontal + borde inferior del bbox (contacto base)
            u = (x1 + x2) / 2.0
            v = y2
            offset = GeoProjector.pixel_to_ground_offset_m(
                v, u,
                image_height=IMG_H, image_width=IMG_W,
                drone_yaw_deg=tel["yaw"], drone_pitch_deg=tel["pitch"], drone_roll_deg=tel["roll"],
                alt_agl_m=alt_agl, camera_vfov_deg=CAMERA_VFOV_DEG,
                mount_roll_deg=MOUNT_ROLL_DEG, mount_pitch_deg=MOUNT_PITCH_DEG, mount_yaw_deg=MOUNT_YAW_DEG,
                max_range_m=MAX_RANGE_M,
            )
            if offset is None:
                continue
            dN, dE = offset["north_m"], offset["east_m"]
            dn_e, dn_n = ll_to_ne(tel["lat"], tel["lon"])
            # ll_to_ne devuelve (x=east, y=north); sumar ejes coherentes
            px, py = dn_e + dE, dn_n + dN
            dists = [(math.hypot(px - p["x"], py - p["y"]), p["id"]) for p in poles]
            err, pid = min(dists)
            rows.append({"frame": k, "cls": d["class_name"], "conf": round(d["confidence"], 3),
                         "proj_latlon": ne_to_ll(px, py), "pole": pid, "err_m": round(err, 2),
                         "u": round(u, 1), "v": round(v, 1)})

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rows.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    errs = [r["err_m"] for r in rows]
    confs = [r["conf"] for r in rows]
    frames_with_tower = len({r["frame"] for r in rows})
    summary = {
        "frames_total": 239,
        "frames_with_tower_detection": frames_with_tower,
        "tower_detections": len(rows),
        "err_median_m": float(np.median(errs)) if errs else None,
        "err_p25_p75_m": [float(np.percentile(errs, 25)), float(np.percentile(errs, 75))] if errs else None,
        "err_min_m": min(errs) if errs else None,
        "conf_median": float(np.median(confs)) if confs else None,
        "poles_used": sorted({r["pole"] for r in rows}),
        "projection_engine": "GeoProjector (pipeline/geo_projector.py)",
        "camera": {"camera_vfov_deg": CAMERA_VFOV_DEG, "mount_yaw": MOUNT_YAW_DEG, "mount_pitch": MOUNT_PITCH_DEG},
        "claim_boundary": ("Exploratory post-hoc. Mount angles recalibrated 2026-07-23 against the "
                           "correct video offset (the legacy camera_mount_fit.json mount was calibrated "
                           "with the wrong offset). Errors bound the pipeline's practical position "
                           "stability on real data, not a calibrated survey."),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
