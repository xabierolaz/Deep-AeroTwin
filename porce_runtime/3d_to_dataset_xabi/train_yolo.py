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
import yaml

# Ultralytics writes settings under %APPDATA% by default, which can be locked down
# in some Windows environments. It honors YOLO_CONFIG_DIR as an override.
_repo_root = Path(__file__).resolve().parents[1]
_default_yolo_cfg = _repo_root / "pipeline" / "logs"
if "YOLO_CONFIG_DIR" not in os.environ:
    _default_yolo_cfg.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(_default_yolo_cfg)

from ultralytics import YOLO


def _patch_ultralytics_threadpool_for_windows() -> None:
    """
    Some locked-down Windows environments deny the OS primitives used by
    multiprocessing.pool.ThreadPool (even though it's a thread pool).
    Ultralytics uses ThreadPool for label caching; replace it with the
    lightweight multiprocessing.dummy Pool (threads, no pipes).
    """
    if os.name != "nt":
        return
    try:
        from concurrent.futures import ThreadPoolExecutor

        import ultralytics.data.dataset as uds

        class _NoPipeThreadPool:
            def __init__(self, processes=None, initializer=None, initargs=()):
                _ = initializer, initargs
                self._executor = ThreadPoolExecutor(max_workers=int(processes) if processes else None)

            def imap(self, func, iterable, chunksize=1):
                _ = chunksize
                return self._executor.map(func, iterable)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self._executor.shutdown(wait=True)
                return False

        uds.ThreadPool = _NoPipeThreadPool  # type: ignore[attr-defined]
    except Exception:
        # Best-effort; training may still work depending on local policies.
        return


THIS_DIR = Path(__file__).resolve().parent


def _resolve_ultralytics_data_yaml(data_yaml: Path, out_dir: Path) -> Path:
    """
    Ultralytics resolves relative 'path:' entries against its global datasets_dir setting,
    not against the YAML file location. To make training reproducible with repo-local datasets,
    we rewrite the YAML with an absolute 'path:' if needed.
    """
    data_yaml = Path(data_yaml)
    if not data_yaml.exists():
        raise SystemExit(f"missing_data_yaml:{data_yaml}")

    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"invalid_data_yaml:{data_yaml}")

    base = data_yaml.parent
    path_value = raw.get("path", None)
    if path_value is None:
        # Default to the YAML directory (common YOLO convention).
        raw["path"] = str(base.resolve())
    else:
        p = Path(str(path_value))
        if not p.is_absolute():
            raw["path"] = str((base / p).resolve())

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{data_yaml.stem}.abs.yaml"
    out_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return out_path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train YOLO on 3d_to_dataset_xabi synthetic dataset.")
    p.add_argument("--data", type=Path, default=(THIS_DIR / "dataset.yaml"))
    p.add_argument("--model", type=str, default="yolo11n.pt", help="Base model / pretrained weights.")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--device", type=str, default="0")
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--save-period", type=int, default=0, help="Save checkpoints every N epochs (0 disables).")
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
    _patch_ultralytics_threadpool_for_windows()

    data_path = args.data
    if not data_path.exists():
        raise SystemExit(f"missing_data_yaml:{data_path}")

    # Resolve project/name paths to keep runs under 3d_to_dataset_xabi/.
    project_dir = args.project
    project_dir.mkdir(parents=True, exist_ok=True)

    # Rewrite data YAML to make 'path:' absolute if needed (Ultralytics quirk).
    data_yaml_abs = _resolve_ultralytics_data_yaml(data_path, out_dir=project_dir)
    print(f"[train] data_yaml_abs={data_yaml_abs}")

    # Allow users to force deterministic behavior if desired.
    os.environ.setdefault("PYTHONHASHSEED", str(int(args.seed)))

    model = YOLO(args.model)
    model.train(
        data=str(data_yaml_abs),
        epochs=int(args.epochs),
        imgsz=int(args.imgsz),
        batch=int(args.batch),
        device=str(args.device),
        workers=int(args.workers),
        patience=int(args.patience),
        save_period=int(args.save_period),
        seed=int(args.seed),
        project=str(project_dir),
        name=str(args.name),
    )

    # Evaluate on val/test (if present).
    try:
        metrics_val = model.val(
            data=str(data_yaml_abs),
            split="val",
            workers=0,
            project=str(project_dir),
            name=f"{args.name}_val",
        )
        _print_metrics("val", metrics_val)
    except Exception as e:
        print(f"[train] val: failed: {e}")

    try:
        metrics_test = model.val(
            data=str(data_yaml_abs),
            split="test",
            workers=0,
            project=str(project_dir),
            name=f"{args.name}_test",
        )
        _print_metrics("test", metrics_test)
    except Exception as e:
        print(f"[train] test: skipped/failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
