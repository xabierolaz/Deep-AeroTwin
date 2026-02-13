#!/usr/bin/env python3
"""
Train a YOLO detector on the synthetic 3D dataset (biker/cow/tower).

This script is intentionally Windows-friendly:
- sets `workers=0` by default to avoid multiprocessing dataloader issues.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import torch
from ultralytics import YOLO


THIS_DIR = Path(__file__).resolve().parent


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train YOLO on 3d_to_dataset_xabi synthetic dataset.")
    p.add_argument("--data", type=Path, default=(THIS_DIR / "dataset.yaml"))
    p.add_argument("--model", type=str, default="yolo11n.pt", help="Base model / pretrained weights.")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--device", type=str, default="0")
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--name", type=str, default="yolo_3d_dome")
    p.add_argument("--project", type=Path, default=(THIS_DIR / "runs"))
    return p.parse_args(list(argv) if argv is not None else None)


def _print_env() -> None:
    if torch.cuda.is_available():
        print(f"[train] gpu={torch.cuda.get_device_name(0)}")
        print(f"[train] torch={torch.__version__} cuda={torch.version.cuda}")
    else:
        print("[train] WARNING: CUDA not available, training will be slow.")


def _print_metrics(tag: str, metrics) -> None:
    # Ultralytics returns a metrics object with .box.map and friends.
    try:
        m50 = float(getattr(metrics.box, "map50", float("nan")))
        m = float(getattr(metrics.box, "map", float("nan")))
        print(f"[train] {tag}: mAP50={m50:.4f} mAP50-95={m:.4f}")
    except Exception:
        print(f"[train] {tag}: metrics={metrics}")


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    _print_env()

    data_path = args.data
    if not data_path.exists():
        raise SystemExit(f"missing_data_yaml:{data_path}")

    # Resolve project/name paths to keep runs under 3d_to_dataset_xabi/.
    project_dir = args.project
    project_dir.mkdir(parents=True, exist_ok=True)

    # Allow users to force deterministic behavior if desired.
    os.environ.setdefault("PYTHONHASHSEED", str(int(args.seed)))

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=int(args.epochs),
        imgsz=int(args.imgsz),
        batch=int(args.batch),
        device=str(args.device),
        workers=int(args.workers),
        patience=int(args.patience),
        seed=int(args.seed),
        project=str(project_dir),
        name=str(args.name),
    )

    # Evaluate on val/test (if present).
    try:
        metrics_val = model.val(
            data=str(data_path),
            split="val",
            project=str(project_dir),
            name=f"{args.name}_val",
        )
        _print_metrics("val", metrics_val)
    except Exception as e:
        print(f"[train] val: failed: {e}")

    try:
        metrics_test = model.val(
            data=str(data_path),
            split="test",
            project=str(project_dir),
            name=f"{args.name}_test",
        )
        _print_metrics("test", metrics_test)
    except Exception as e:
        print(f"[train] test: skipped/failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
