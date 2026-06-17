"""Compose a route video from pristine archived frames + logged YOLO boxes.

Whole D1 run, boxes drawn per published track (color by class), with a HUD
showing the archived frame index and elapsed time so the user can pick a moment.
"""
import json
from pathlib import Path

import cv2
import numpy as np

RUN = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_233504")
FRAMES = RUN / "vision" / "frames"
OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_route_yolo.mp4")
FPS = 20

CLASS_COLOR = {  # BGR
    "biker": (60, 60, 230),
    "bike": (60, 60, 230),
    "cow": (40, 170, 240),
    "tower": (210, 140, 40),
}

# index events by frame number
events = {}
t0 = None
for line in (RUN / "vision" / "events.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        e = json.loads(line)
    except Exception:
        continue
    if e.get("kind") != "vision_frame":
        continue
    fn = int(e.get("frame", -1))
    events[fn] = e
    if t0 is None:
        t0 = float(e["ts"])

frame_files = sorted(FRAMES.glob("yolo_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
if not frame_files:
    raise SystemExit("no frames")

h, w = cv2.imread(str(frame_files[0])).shape[:2]
writer = cv2.VideoWriter(str(OUT), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))

n_written = 0
for fp in frame_files:
    idx = int(fp.stem.split("_")[1])
    img = cv2.imread(str(fp))
    if img is None:
        continue
    evt = events.get(idx)
    n_bik = n_cow = n_tow = 0
    t_rel = None
    if evt is not None:
        t_rel = float(evt["ts"]) - t0 if t0 else None
        for o in evt.get("outgoing", []) or []:
            if not isinstance(o, dict) or not o.get("bbox"):
                continue
            cls = str(o.get("type", "")).lower()
            color = CLASS_COLOR.get(cls, (200, 200, 200))
            b = o["bbox"]
            x1, y1, x2, y2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
            cv2.putText(img, f"{o.get('confidence', 0):.2f}", (x1, max(8, y1 - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)
            if cls in ("biker", "bike"):
                n_bik += 1
            elif cls == "cow":
                n_cow += 1
            elif cls == "tower":
                n_tow += 1
    # HUD bar
    bar = img.copy()
    cv2.rectangle(bar, (0, 0), (w, 22), (0, 0, 0), -1)
    img = cv2.addWeighted(bar, 0.45, img, 0.55, 0)
    tt = f"t={t_rel:6.1f}s" if t_rel is not None else "t=  n/a"
    hud = f"frame {idx:6d}  {tt}   biker:{n_bik}  cow:{n_cow}  tower:{n_tow}"
    cv2.putText(img, hud, (6, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
    writer.write(img)
    n_written += 1

writer.release()
print(f"frames_written={n_written} duration_s={n_written / FPS:.1f} out={OUT}")
