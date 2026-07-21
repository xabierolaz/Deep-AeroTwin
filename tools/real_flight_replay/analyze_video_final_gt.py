# -*- coding: utf-8 -*-
"""video_final (239 real frames) metric study vs PNOA tower ground truth.

Per frame with a tower-class YOLOE detection: ray from the bbox bottom-center
through the camera model (crop window measured: full-width 2160x1620 at
(0,1200) of the original portrait frame -> fx=fy=1421 px, pp=(640,480) in
video_final pixels; mount from tools/real_flight_replay/camera_mount_fit.json
with roll clamped to 0, declared approximate) and intersect the terrain plane
(256.38 m MSL). Error = horizontal distance to the nearest PNOA pole (P1-P4,
~1-2 m accuracy). Real telemetry per frame (trajectory_video_final.csv).

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
RFR = ROOT / "tools/real_flight_replay"
TRAJ = RFR / "out/trajectory_video_final.csv"
DETS = ROOT / "experiments/sppa_detection_reference/20260721_video_final_yoloe26s/detections.jsonl"
POLES = RFR / "out/tower_ground_truth.csv"
OUT = ROOT / "experiments/sppa_real_stream_wave/20260721_video_final_gt_study"
TERRAIN_MSL = 256.38
MOUNT = {"yaw_deg": 155.77337067452754, "pitch_deg": -36.82426613750975, "roll_deg": 0.0}
FX = FY = 1421.0  # crop window (0,1200,2160,1620) -> 1280x960, square pixels
CX, CY = 640.0, 480.0
TOWER_CLASSES = {"power transmission tower", "electric pylon", "utility pole", "antenna tower"}
R_EARTH = 6371000.0
ORIGIN = {"lat": 42.14413817655726, "lon": -1.5882846555030494}  # trajectory centroid


def rot_x(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def ned_from_body(yaw, pitch, roll):
    """Body (FRD) -> NED rotation, same convention as GeoProjector._ned_from_body."""
    return rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)


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

    A = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    R_mount = rot_z(MOUNT["yaw_deg"]) @ rot_y(MOUNT["pitch_deg"]) @ rot_x(MOUNT["roll_deg"])

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
        R_ned_body = ned_from_body(tel["yaw"], tel["pitch"], tel["roll"])
        dn_e, dn_n = ll_to_ne(tel["lat"], tel["lon"])
        for d in towers:
            b = d["xyxy"]
            u, v = (b[0] + b[2]) / 2.0, b[3]  # bbox bottom-center
            ray_cam = np.array([(u - CX) / FX, (v - CY) / FY, 1.0])
            ray_world = R_ned_body @ (R_mount @ (A @ ray_cam))
            if ray_world[2] <= 1e-6:
                continue
            t = (tel["alt_msl"] - TERRAIN_MSL) / ray_world[2]
            px, py = dn_e + t * ray_world[0], dn_n + t * ray_world[1]
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
        "mount_declared": MOUNT,
        "claim_boundary": ("Exploratory post-hoc. Mount angles from the toolkit fit with roll clamped to 0 "
                           "(declared approximate; the 4-point fit RMS is 277 px, so errors bound the "
                           "pipeline's practical position stability on real data, not a calibrated survey)."),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
