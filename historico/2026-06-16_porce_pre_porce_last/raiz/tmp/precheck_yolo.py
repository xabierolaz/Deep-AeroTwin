"""YOLO pre-check: run pipeline weights on editor screenshots of the UE5.7 peloton."""
import json
from pathlib import Path

OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_yolo_results.json")
WEIGHTS = r"D:\Deep-AeroTwin-UE57-Test\yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"
SHOTS = sorted(Path(r"D:\Deep-AeroTwin-UE57-Test\Unreal\Saved\Screenshots").glob("precheck_v*.png"))

from ultralytics import YOLO  # noqa: E402

model = YOLO(WEIGHTS)
report = {"weights": WEIGHTS, "class_names": model.names, "images": []}
for shot in SHOTS:
    res = model.predict(source=str(shot), conf=0.10, imgsz=640, verbose=False)[0]
    dets = []
    for box in res.boxes:
        cls_id = int(box.cls.item())
        dets.append(
            {
                "class": model.names.get(cls_id, str(cls_id)),
                "conf": round(float(box.conf.item()), 3),
                "xyxy": [round(v, 1) for v in box.xyxy[0].tolist()],
            }
        )
    dets.sort(key=lambda d: -d["conf"])
    report["images"].append({"image": shot.name, "detections": dets})

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2)[:2000])
