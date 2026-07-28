#!/usr/bin/env python3
"""Fine-tuning YOLO para apoyos reales (Pipeline B, vuelo M_20_1RR).

Entrena yolo11n sobre el dataset auto-etiquetado por proyeccion
(autolabel_towers.py). Hold-out temporal: train = t<50 s, val = t>=50 s
(pierna de vuelta; vistas distintas de las de entrenamiento).

Uso:
  python train_tower_yolo.py [--epochs 50] [--imgsz 1280] [--model yolo11n.pt]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ultralytics import YOLO

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
REPO = ROOT.parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--model", type=str, default=str(REPO / "yolo11n.pt"))
    ap.add_argument("--data", type=str, default=str(OUT / "dataset" / "dataset.yaml"))
    ap.add_argument("--name", type=str, default="tower_v1")
    args = ap.parse_args()

    data_yaml = Path(args.data)
    if not data_yaml.exists():
        raise SystemExit(f"dataset no encontrado: {data_yaml} (ejecuta autolabel_towers.py antes)")

    model = YOLO(args.model)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        project=str(OUT / "runs"),
        name=args.name,
        exist_ok=True,
        verbose=True,
    )
    best = OUT / "runs" / args.name / "weights" / "best.pt"
    dst = OUT / f"yolo_tower_real_{args.name}.pt"
    if best.exists():
        shutil.copy2(best, dst)
        print(f"pesos copiados a: {dst}")
    metrics = model.val(data=str(data_yaml), split="val", imgsz=args.imgsz)
    print(f"mAP50-95: {metrics.box.map:.4f}  mAP50: {metrics.box.map50:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
