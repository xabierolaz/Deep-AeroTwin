"""YOLO check on the ciclista-mode screenshot."""
import json
from pathlib import Path

OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_yolo2_results.json")
WEIGHTS = r"D:\Deep-AeroTwin-UE57-Test\yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"
IMG = r"D:\Deep-AeroTwin-UE57-Test\Unreal\Saved\Screenshots\precheck_ciclista_v0.png"

from ultralytics import YOLO  # noqa: E402

model = YOLO(WEIGHTS)
res = model.predict(source=IMG, conf=0.10, imgsz=640, verbose=False)[0]
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
OUT.write_text(json.dumps({"image": IMG, "detections": dets}, indent=2), encoding="utf-8")
print(json.dumps(dets, indent=2)[:1500])
