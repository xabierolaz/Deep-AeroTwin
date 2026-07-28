#!/usr/bin/env python3
"""Render video_final frames with YOLOE detections overlaid (to out/v2_frames/)."""
import json, os
import cv2

OUT = "tools/real_flight_replay/out"
os.makedirs(f"{OUT}/v2_frames", exist_ok=True)

dets = {}
for line in open("experiments/sppa_detection_reference/20260721_video_final_yoloe26s/detections.jsonl"):
    d = json.loads(line)
    if d["detections"]:
        dets[d["frame"]] = d["detections"]

cap = cv2.VideoCapture("../../../papers/pipeline_a_telemetry/data/video_final.mp4")
frames_want = [0, 10, 20, 30, 40, 50, 60, 70, 80, 100, 120, 140, 160, 180, 200, 220, 231, 236]
for fi in frames_want:
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
    ok, fr = cap.read()
    if not ok:
        continue
    for det in dets.get(fi, []):
        x1, y1, x2, y2 = [int(v) for v in det["xyxy"]]
        cv2.rectangle(fr, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(fr, f"{det['class_name'][:12]} {det['confidence']:.2f}", (x1, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        # center-x line and bottom-center marker
        cx = (x1 + x2) // 2
        cv2.line(fr, (cx, y1), (cx, y2), (255, 0, 255), 1)
        cv2.drawMarker(fr, (cx, y2), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 20, 2)
    cv2.imwrite(f"{OUT}/v2_frames/f{fi:03d}.png", fr)
cap.release()
print("done", len(frames_want))
