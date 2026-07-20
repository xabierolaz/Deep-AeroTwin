"""E11 "Oblique Twin Wave" - step 1: batch detection (real YOLO on twin frames).

Runs the real detector (same weights and settings as E7: conf=0.10, imgsz=640)
over the 308 manifest frames and writes detections.jsonl (one row per
detection). Everything is kept (no filtering beyond conf); wrong tokens are
the natural condition and are flagged downstream, never cleaned.

Run:  python run_e11_detect.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

E11_ROOT = Path(__file__).resolve().parent
WEIGHTS_NAME = "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"


def _find_weights() -> Path:
    # paper_semantic_proxy_3d is a junction -> resolve() escapes the repo root,
    # so search upward from the UNRESOLVED absolute path, then fall back to the
    # known repo root (same convention as e7_common.PIPELINE_ROOT).
    candidates = [Path(__file__).absolute()]
    for start in candidates:
        for parent in [start.parent, *start.parents]:
            cand = parent / "yolo" / "weights" / WEIGHTS_NAME
            if cand.exists():
                return cand
    fallback = Path(r"D:\Deep-AeroTwin-UE57-Test") / "yolo" / "weights" / WEIGHTS_NAME
    if fallback.exists():
        return fallback
    raise FileNotFoundError(WEIGHTS_NAME)


WEIGHTS = _find_weights()
MANIFEST = E11_ROOT / "manifest.jsonl"
OUT = E11_ROOT / "detections.jsonl"
CONF = 0.10
IMGSZ = 640


def main() -> int:
    from ultralytics import YOLO

    frames = [json.loads(line) for line in MANIFEST.open("r", encoding="utf-8")]
    frames = [f for f in frames if f.get("ok") and (E11_ROOT / "frames" / f"{f['frame_id']}.png").exists()]
    print(f"frames={len(frames)} weights={WEIGHTS.name} conf={CONF} imgsz={IMGSZ}")

    model = YOLO(str(WEIGHTS))
    t0 = time.perf_counter()
    n_det = 0
    per_class: dict[str, int] = {}
    with OUT.open("w", encoding="utf-8") as handle:
        for i, frame in enumerate(frames):
            png = E11_ROOT / "frames" / f"{frame['frame_id']}.png"
            results = model.predict(str(png), conf=CONF, imgsz=IMGSZ, verbose=False)
            det_index = 0
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls = result.names[int(box.cls[0])]
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                    row = {
                        "frame_id": frame["frame_id"],
                        "det_index": det_index,
                        "class": cls,
                        "confidence": float(box.conf[0]),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    }
                    handle.write(json.dumps(row) + "\n")
                    det_index += 1
                    n_det += 1
                    per_class[cls] = per_class.get(cls, 0) + 1
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(frames)} frames, {n_det} dets ({time.perf_counter() - t0:.0f}s)")
    seconds = time.perf_counter() - t0
    print(f"wrote {n_det} detections -> {OUT} ({seconds:.0f}s)")
    print(f"per-class counts: {per_class}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
