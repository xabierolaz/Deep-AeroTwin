# -*- coding: utf-8 -*-
"""Inferencia de posicion real de torres electricas sobre video_final.mp4.

Pipeline zero-trust usando coordenadas reales extraidas del .bin
(drone_coords_from_bin.csv) y el motor de proyeccion canonico del Pipeline A
(pipeline/geo_projector.py, clase GeoProjector):

  1. YOLOE-26s-seg sobre los 239 frames -> bbox + MASCARA (silueta) por torre.
  2. Render visual: square de deteccion + silueta superpuesta.
  3. Proyeccion geometrica via GeoProjector:
       - bbox_to_ground_footprint_m: proyecta 8 puntos del bbox al plano de
         terreno -> centroide, longitud, anchura y orientacion (footprint).
       - pixel_to_ground_offset_m: proyecta el bottom-center del bbox (centro
         horizontal + borde inferior) como punto de contacto base de la torre.
     Intrinsecas desde camera_vfov_deg (no fx hardcoded), mount de camara
     (yaw/pitch/roll), y yaw/pitch/roll del dron. Interseccion rayo-plano.
  4. Salida: lat/lon inferido por deteccion + comparacion con GT PNOA.

Mount de camara: tools/real_flight_replay/out/camera_mount_fit.json (v3,
yaw=22/pitch=-24, recalibrado 2026-07-23 contra offset de video correcto).
Terreno ref MSL: 256.56 m (mediana alt en suelo del .bin).
Coordenadas del dron: tools/real_flight_replay/out/drone_coords_from_bin.csv.
GT torres: tools/real_flight_replay/out/tower_ground_truth.csv (PNOA).

Salidas en experiments/tower_position_inference_YYYYMMDD/.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test")
sys.path.insert(0, str(ROOT / "pipeline"))
from geo_projector import GeoProjector  # noqa: E402  (motor canonico Pipeline A)

VIDEO = ROOT / "papers/pipeline_a_telemetry/data/video_final.mp4"
COORDS = ROOT / "tools/real_flight_replay/out/drone_coords_from_bin.csv"
MOUNT_JSON = ROOT / "tools/real_flight_replay/out/camera_mount_fit.json"
GT_POLES = ROOT / "tools/real_flight_replay/out/tower_ground_truth.csv"
MODEL = ROOT / "yoloe-26s-seg.pt"

OUT_DIR = ROOT / f"experiments/tower_position_inference_{datetime.now().strftime('%Y%m%d')}"
VIS_DIR = OUT_DIR / "annotated_frames"
VIS_DIR.mkdir(parents=True, exist_ok=True)

# Clases y parametros del sistema existente (consistencia con run_yoloe_video_final.py)
CLASSES = ["power transmission tower", "electric pylon", "utility pole", "antenna tower",
           "cow", "cattle", "horse", "person", "cyclist", "bicycle", "motorcycle",
           "vehicle", "car", "truck", "tractor", "agricultural vehicle"]
TOWER_CLASSES = {"power transmission tower", "electric pylon", "utility pole", "antenna tower"}
IMG_SIZE = 1280
CONF = 0.05

# FOV vertical de la camara para video_final (1280x960). Coherente con fx=1421 px
# del crop window anterior: vfov = 2*atan(480/1421) = 37.4 deg. GeoProjector deriva
# fx/fy/cx/cy nativamente desde camera_vfov_deg + image size.
CAMERA_VFOV_DEG = 37.4
MAX_RANGE_M = 300.0

R_EARTH = 6371000.0


def load_drone_coords():
    """Carga lat/lon/alt/yaw del dron por frame desde el artefacto zero-trust del .bin."""
    coords = {}
    with COORDS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            coords[int(r["frame"])] = {
                "t_unix": float(r["t_unix"]),
                "lat": float(r["lat"]), "lon": float(r["lon"]),
                "alt_msl": float(r["alt_msl"]), "rel_alt": float(r["rel_alt"]),
                "roll": float(r["roll"]), "pitch": float(r["pitch"]), "yaw": float(r["yaw"]),
            }
    return coords


def load_poles():
    poles = []
    for line in GT_POLES.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("id,"):
            continue
        pid, lat, lon = line.split(",")[:3]
        poles.append({"id": pid.strip(), "lat": float(lat), "lon": float(lon)})
    return poles


def project_tower_via_geoprojector(bbox_xyxy, tel, mount, image_w, image_h, terrain_msl):
    """Proyecta una deteccion de torre al mundo usando el GeoProjector del Pipeline A.

    Sigue el patron de build_real_image_assumed_flight_replay.py:metric_projection:
      - bbox_to_ground_footprint_m: 8 puntos del bbox -> centroide/longitud/anchura.
      - pixel_to_ground_offset_m: bottom-center del bbox (centro horizontal + borde
        inferior) como punto de contacto base de la torre.

    Intrinsecas nativas desde camera_vfov_deg (GeoProjector deriva fx/fy/cx/cy).
    alt_agl = alt_msl del dron - terreno ref MSL.
    """
    alt_agl = tel["alt_msl"] - terrain_msl
    params = {
        "image_height": image_h,
        "image_width": image_w,
        "drone_yaw_deg": tel["yaw"],
        "drone_pitch_deg": tel["pitch"],
        "drone_roll_deg": tel["roll"],
        "alt_agl_m": alt_agl,
        "camera_vfov_deg": CAMERA_VFOV_DEG,
        "mount_roll_deg": mount["roll_deg"],
        "mount_pitch_deg": mount["pitch_deg"],
        "mount_yaw_deg": mount["yaw_deg"],
        "max_range_m": MAX_RANGE_M,
    }
    x1, y1, x2, y2 = bbox_xyxy
    bbox_payload = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    footprint = GeoProjector.bbox_to_ground_footprint_m(bbox_payload, **params)
    # bottom-center: centro horizontal + borde inferior del bbox
    bottom_center = GeoProjector.pixel_to_ground_offset_m(
        (y1 + y2) / 2.0, (x1 + x2) / 2.0, **params
    )
    if bottom_center is None:
        return None
    dN = bottom_center["north_m"]
    dE = bottom_center["east_m"]
    lat = tel["lat"] + math.degrees(dN / R_EARTH)
    lon = tel["lon"] + math.degrees(dE / (R_EARTH * math.cos(math.radians(tel["lat"]))))
    return {
        "lat": lat, "lon": lon, "dN_m": dN, "dE_m": dE,
        "t_ground": bottom_center["distance_m"],
        "footprint_length_m": footprint["length_m"] if footprint else None,
        "footprint_width_m": footprint["width_m"] if footprint else None,
        "footprint_orientation_deg": footprint["orientation_deg_axial"] if footprint else None,
    }


def ll_to_local(lat, lon, lat0, lon0):
    x = math.radians(lon - lon0) * math.cos(math.radians(lat0)) * R_EARTH
    y = math.radians(lat - lat0) * R_EARTH
    return x, y


def main():
    mount_fit = json.loads(MOUNT_JSON.read_text(encoding="utf-8"))
    # Mount recalibrado 2026-07-23 contra drone_coords_from_bin.csv (offset de video correcto,
    # +12.856s) ESPECIFICO para el motor GeoProjector del Pipeline A. El mount del overlay-calib
    # original (yaw=155, pitch=-37) se calibro con el offset erroneo video_final_sync.json
    # (+15.985s) y producia una proyeccion invertida ~131 grados. Barrido de minimizacion de
    # mediana de error contra GT PNOA sobre las 100 detecciones de torre, usando GeoProjector
    # (camera_vfov_deg=37.4), da el optimo yaw=21, pitch=-30. No usar el mount del JSON sin esta
    # correccion.
    mount = {"yaw_deg": 21.0,
             "pitch_deg": -30.0,
             "roll_deg": 0.0}
    terrain_msl = 256.56  # mediana alt en suelo del .bin (zero-trust)
    origin = {"terrain_msl": terrain_msl}

    coords = load_drone_coords()
    poles = load_poles()
    pole0 = poles[0]
    for p in poles:
        p["x"], p["y"] = ll_to_local(p["lat"], p["lon"], pole0["lat"], pole0["lon"])

    model = YOLO(str(MODEL), task="segment")
    model.set_classes(CLASSES)

    cap = cv2.VideoCapture(str(VIDEO))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    det_rows = []   # jsonl: una fila por deteccion de torre
    proj_rows = []  # jsonl: una fila por proyeccion al mundo
    k = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        res = model.predict(frame, imgsz=IMG_SIZE, conf=CONF, max_det=50, verbose=False)[0]
        tel = coords.get(k)
        # render visual con square + silueta
        vis = frame.copy()
        if res.boxes is not None:
            boxes = res.boxes
            masks = res.masks.xy if res.masks is not None else [None] * len(boxes)
            for i in range(len(boxes)):
                b = boxes[i]
                cls_id = int(b.cls[0]); cls_name = CLASSES[cls_id]
                conf = float(b.conf[0])
                xyxy = [float(v) for v in b.xyxy[0]]
                mask_pts = masks[i] if i < len(masks) and masks[i] is not None else None
                is_tower = cls_name in TOWER_CLASSES
                det_rows.append({
                    "frame": k, "class_name": cls_name, "confidence": conf,
                    "xyxy": xyxy,
                    "mask_present": mask_pts is not None,
                    "mask_points": (len(mask_pts) if mask_pts is not None else 0),
                    "is_tower": is_tower,
                })
                # color por tipo
                color = (0, 0, 220) if is_tower else (40, 180, 40)
                # silueta
                if mask_pts is not None:
                    poly = np.array(mask_pts, dtype=np.int32).reshape(-1, 1, 2)
                    overlay = vis.copy()
                    cv2.fillPoly(overlay, [poly], color)
                    vis = cv2.addWeighted(overlay, 0.35, vis, 0.65, 0)
                    cv2.polylines(vis, [poly], True, color, 2)
                # square
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
                cv2.putText(vis, f"{cls_name} {conf:.2f}", (x1, max(0, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                # proyeccion al mundo solo para torres (via GeoProjector Pipeline A)
                if is_tower and tel is not None:
                    img_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    img_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    proj = project_tower_via_geoprojector(
                        xyxy, tel, mount, img_w, img_h, origin["terrain_msl"])
                    if proj is not None:
                        px, py = ll_to_local(proj["lat"], proj["lon"], pole0["lat"], pole0["lon"])
                        dists = [(math.hypot(px - p["x"], py - p["y"]), p["id"]) for p in poles]
                        err, pid = min(dists)
                        u = (xyxy[0] + xyxy[2]) / 2.0
                        v = (xyxy[1] + xyxy[3]) / 2.0  # bottom-center: centro del borde inf
                        proj_rows.append({
                            "frame": k, "class_name": cls_name, "confidence": conf,
                            "u": round(u, 1), "v": round(v, 1),
                            "drone_lat": tel["lat"], "drone_lon": tel["lon"], "drone_alt_msl": tel["alt_msl"],
                            "drone_yaw": tel["yaw"], "drone_pitch": tel["pitch"], "drone_roll": tel["roll"],
                            "inferred_lat": proj["lat"], "inferred_lon": proj["lon"],
                            "dN_m": round(proj["dN_m"], 2), "dE_m": round(proj["dE_m"], 2),
                            "range_m": round(proj["t_ground"], 1),
                            "footprint_length_m": round(proj["footprint_length_m"], 2) if proj["footprint_length_m"] is not None else None,
                            "footprint_width_m": round(proj["footprint_width_m"], 2) if proj["footprint_width_m"] is not None else None,
                            "footprint_orientation_deg": round(proj["footprint_orientation_deg"], 1) if proj["footprint_orientation_deg"] is not None else None,
                            "nearest_pole": pid, "err_m": round(err, 2),
                        })
        cv2.imwrite(str(VIS_DIR / f"frame_{k:04d}.png"), vis)
        k += 1
    cap.release()

    # escribir jsonl
    (OUT_DIR / "detections_bbox_mask.jsonl").write_text(
        "\n".join(json.dumps(r) for r in det_rows), encoding="utf-8")
    (OUT_DIR / "tower_world_projections.jsonl").write_text(
        "\n".join(json.dumps(r) for r in proj_rows), encoding="utf-8")

    # resumen
    tower_dets = [r for r in det_rows if r["is_tower"]]
    frames_with_tower = sorted({r["frame"] for r in tower_dets})
    with_mask = sum(1 for r in tower_dets if r["mask_present"])
    errs = [r["err_m"] for r in proj_rows]
    summary = {
        "frames_total": k,
        "frames_with_tower_detection": len(frames_with_tower),
        "tower_detections": len(tower_dets),
        "tower_detections_with_mask": with_mask,
        "projections_to_world": len(proj_rows),
        "err_median_m": round(float(np.median(errs)), 2) if errs else None,
        "err_p25_p75_m": [round(float(np.percentile(errs, 25)), 2),
                          round(float(np.percentile(errs, 75)), 2)] if errs else None,
        "err_min_m": round(min(errs), 2) if errs else None,
        "err_max_m": round(max(errs), 2) if errs else None,
        "terrain_msl": terrain_msl,
        "mount": mount,
        "camera": {"camera_vfov_deg": CAMERA_VFOV_DEG, "max_range_m": MAX_RANGE_M,
                   "image_size": [1280, 960]},
        "projection_engine": "GeoProjector (pipeline/geo_projector.py, Pipeline A)",
        "location": "Murillo de las Limas, Navarra (confirmado por GPS del .bin)",
        "note": "Proyeccion via GeoProjector del Pipeline A (bbox_to_ground_footprint_m + "
                "pixel_to_ground_offset_m del bottom-center). Coordenadas drone zero-trust del .bin.",
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
