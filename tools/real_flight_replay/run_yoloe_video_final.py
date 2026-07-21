# -*- coding: utf-8 -*-
"""YOLOE-26s detection over every frame of rea_flight_data/video_final.mp4
(239 frames, 1280x960, 10 fps, real flight video cut by the user from M_20_1RR).

Writes experiments/sppa_detection_reference/20260721_video_final_yoloe26s/detections.jsonl
(one row per frame with bbox/conf/class per detection) plus annotated crops
of the best tower frames for QA. Same universal prompt set and thresholds as
the 20260703/20260721 references.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test")
VIDEO = ROOT / "rea_flight_data/video_final.mp4"
OUT_DIR = ROOT / "experiments/sppa_detection_reference/20260721_video_final_yoloe26s"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CLASSES = ["power transmission tower", "electric pylon", "utility pole", "antenna tower",
           "cow", "cattle", "horse", "person", "cyclist", "bicycle", "motorcycle",
           "vehicle", "car", "truck", "tractor", "agricultural vehicle"]
IMG_SIZE = 1280
CONF = 0.05

model = YOLO(str(ROOT / "yoloe-26s-seg.pt"), task="segment")
model.set_classes(CLASSES)

cap = cv2.VideoCapture(str(VIDEO))
rows = []
best_tower = {"conf": -1.0, "frame": -1}
k = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    res = model.predict(frame, imgsz=IMG_SIZE, conf=CONF, max_det=50, verbose=False)[0]
    dets = []
    if res.boxes is not None:
        for i in range(len(res.boxes)):
            b = res.boxes[i]
            cls_id = int(b.cls[0])
            dets.append({
                "class_id": cls_id,
                "class_name": CLASSES[cls_id],
                "confidence": float(b.conf[0]),
                "xyxy": [float(v) for v in b.xyxy[0]],
            })
    rows.append({"frame": k, "detections": dets})
    for d in dets:
        if d["class_name"] in ("power transmission tower", "electric pylon") and d["confidence"] > best_tower["conf"]:
            best_tower = {"conf": d["confidence"], "frame": k, "det": d}
    k += 1
cap.release()

with (OUT_DIR / "detections.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

# annotated QA frame of the best tower detection
if best_tower["frame"] >= 0:
    cap = cv2.VideoCapture(str(VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, best_tower["frame"])
    ok, frame = cap.read()
    cap.release()
    if ok:
        res = model.predict(frame, imgsz=IMG_SIZE, conf=CONF, max_det=50, verbose=False)[0]
        img = res.plot()
        cv2.imwrite(str(OUT_DIR / f"annotated_frame_{best_tower['frame']:04d}.png"), img)

n_det = sum(len(r["detections"]) for r in rows)
print(json.dumps({"frames": k, "detections_total": n_det,
                  "best_tower": best_tower}, indent=1))
