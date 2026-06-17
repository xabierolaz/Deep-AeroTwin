"""YOLO check on a native-scale 640x640 crop centered on the peloton."""
import json
from pathlib import Path

from PIL import Image
from ultralytics import YOLO

OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_yolo3_results.json")
WEIGHTS = r"D:\Deep-AeroTwin-UE57-Test\yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"
IMG = r"D:\Deep-AeroTwin-UE57-Test\Unreal\Saved\Screenshots\precheck_ciclista_v0.png"
CROP_PATH = r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_crop640.png"

im = Image.open(IMG)
# peloton cluster around x~740-930, y~300-440 in full-res -> center crop on it
cx, cy = 835, 400
x1 = max(0, cx - 320)
y1 = max(0, cy - 320)
crop = im.crop((x1, y1, x1 + 640, y1 + 640))
crop.save(CROP_PATH)

model = YOLO(WEIGHTS)
res = model.predict(source=CROP_PATH, conf=0.10, imgsz=640, verbose=False)[0]
dets = []
for box in res.boxes:
    dets.append(
        {
            "class": model.names.get(int(box.cls.item())),
            "conf": round(float(box.conf.item()), 3),
            "xyxy": [round(v, 1) for v in box.xyxy[0].tolist()],
        }
    )
dets.sort(key=lambda d: -d["conf"])
OUT.write_text(json.dumps({"crop": CROP_PATH, "detections": dets}, indent=2), encoding="utf-8")
print(json.dumps(dets, indent=2)[:1200])
