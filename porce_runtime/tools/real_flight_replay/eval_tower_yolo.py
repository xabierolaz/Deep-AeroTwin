#!/usr/bin/env python3
"""Evaluacion visual del detector de apoyos sobre frames del video real.

Ejecuta el modelo entrenado sobre frames muestreados del video M_20_1RR,
guarda imagenes anotadas y resume detecciones (confianzas, posiciones).

Uso:
  python eval_tower_yolo.py --weights out/yolo_tower_real_tower_v1.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VIDEO = ROOT.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--conf", type=float, default=0.20)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--times", type=str, default="5,10,15,20,25,28,32,36,40,45,50,55,60,65,68")
    args = ap.parse_args()

    model = YOLO(str(args.weights))
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out_dir = OUT / "eval_frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for t in [float(x) for x in args.times.split(",")]:
        fi = int(t * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        r = model.predict(frame, verbose=False, conf=args.conf, imgsz=args.imgsz)[0]
        dets = []
        vis = cv2.resize(frame, (1920, 1080)).copy()
        s = 1920 / frame.shape[1]
        if r.boxes is not None:
            for b in r.boxes:
                conf = float(b.conf)
                x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
                dets.append({"conf": round(conf, 3), "xyxy": [x1, y1, x2, y2]})
                cv2.rectangle(vis, (int(x1 * s), int(y1 * s)), (int(x2 * s), int(y2 * s)), (0, 0, 255), 2)
                cv2.putText(vis, f"{conf:.2f}", (int(x1 * s), int(y1 * s) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        summary[f"t{t:g}"] = dets
        cv2.imwrite(str(out_dir / f"eval_t{t:02g}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"t={t:5.1f}s: {len(dets)} det -> {[d['conf'] for d in dets]}")
    cap.release()
    (out_dir / "eval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nimagenes en {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
