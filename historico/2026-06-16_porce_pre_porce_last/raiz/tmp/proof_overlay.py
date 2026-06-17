"""Draw the logged YOLO boxes onto the pristine frame 5728 as a proof image,
plus a zoomed inset of the peloton cluster."""
import json
from pathlib import Path

import cv2
import numpy as np

RUN = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_233504")
FRAME = RUN / "vision" / "frames" / "yolo_005728.jpg"
OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\proof_yolo_overlay.png")

evt = json.load(open(r"/tmp/evt5728.json")) if Path("/tmp/evt5728.json").exists() else None
if evt is None:
    for l in (RUN / "vision" / "events.jsonl").read_text(errors="ignore").splitlines():
        try:
            e = json.loads(l)
        except Exception:
            continue
        if e.get("kind") == "vision_frame" and int(e.get("frame", -1)) == 5728:
            evt = e
            break

img = cv2.imread(str(FRAME))
boxes = [o for o in evt.get("outgoing", [])
         if str(o.get("type", "")).lower() in ("bike", "biker") and o.get("bbox")]

xs, ys = [], []
for o in boxes:
    b = o["bbox"]
    x1, y1, x2, y2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
    xs += [x1, x2]; ys += [y1, y2]
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 1)
    cv2.putText(img, f"{o.get('confidence', 0):.2f}", (x1, max(8, y1 - 2)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1, cv2.LINE_AA)

# zoomed inset of the cluster
pad = 25
x1 = max(0, min(xs) - pad); y1 = max(0, min(ys) - pad)
x2 = min(img.shape[1], max(xs) + pad); y2 = min(img.shape[0], max(ys) + pad)
crop = img[y1:y2, x1:x2]
zoom = cv2.resize(crop, (crop.shape[1] * 6, crop.shape[0] * 6), interpolation=cv2.INTER_NEAREST)

# stack: full frame on top, zoom below (match width)
W = img.shape[1]
zw = zoom.shape[1]
if zw > W:
    zoom = cv2.resize(zoom, (W, int(zoom.shape[0] * W / zw)))
elif zw < W:
    canvas = np.full((zoom.shape[0], W, 3), 30, np.uint8)
    off = (W - zoom.shape[1]) // 2
    canvas[:, off:off + zoom.shape[1]] = zoom
    zoom = canvas
sep = np.full((4, W, 3), 80, np.uint8)
out = np.vstack([img, sep, zoom])
cv2.imwrite(str(OUT), out)
print(f"boxes={len(boxes)} saved={OUT}")
