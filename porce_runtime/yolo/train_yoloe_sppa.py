from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
YOLO_DIR = Path(__file__).resolve().parent


def parse_batch(value: str) -> int | float:
    text = str(value).strip()
    if "." in text:
        return float(text)
    return int(text)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def dataset_counts(data_yaml: Path) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    base = (data_yaml.parent / str(data.get("path", "."))).resolve()
    counts: dict[str, Any] = {"yaml": rel(data_yaml), "base": rel(base), "names": data.get("names", {})}
    for split in ("train", "val", "test"):
        split_path = base / str(data.get(split, ""))
        counts[split] = {
            "path": rel(split_path),
            "exists": split_path.exists(),
            "images": len([p for p in split_path.glob("*") if p.is_file()]) if split_path.exists() else 0,
        }
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune YOLOE-26s as a bbox detector for SPPA Unreal classes. "
            "Use the official YOLOE detection trainer with weights transferred from yoloe-26s-seg.pt."
        )
    )
    parser.add_argument("--data", type=Path, default=YOLO_DIR / "dataset.yaml")
    parser.add_argument("--model-yaml", default="yoloe-26s.yaml")
    parser.add_argument("--pretrained", default=str(ROOT / "yoloe-26s-seg.pt"))
    parser.add_argument("--project", type=Path, default=YOLO_DIR / "runs")
    parser.add_argument("--name", default="yoloe26s_sppa_unreal_v1")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=parse_batch, default=-1)
    parser.add_argument("--device", default="0")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--save-period", type=int, default=10)
    parser.add_argument("--copy-best", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_yaml = args.data if args.data.is_absolute() else ROOT / args.data
    project = args.project if args.project.is_absolute() else ROOT / args.project
    pretrained = Path(args.pretrained)
    if not pretrained.is_absolute():
        pretrained = ROOT / pretrained

    if not data_yaml.exists():
        raise SystemExit(f"missing_data_yaml:{data_yaml}")
    if not pretrained.exists():
        raise SystemExit(f"missing_pretrained_weights:{pretrained}")

    summary = {
        "schema": "SPPA-YOLOE-FINETUNE-COMMAND-0.1",
        "task": "detect",
        "model_yaml": args.model_yaml,
        "pretrained": rel(pretrained),
        "data": dataset_counts(data_yaml),
        "train_args": {
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "patience": args.patience,
            "workers": args.workers,
            "project": rel(project),
            "name": args.name,
            "save_period": args.save_period,
        },
    }
    print(json.dumps(summary, indent=2))
    if args.dry_run:
        return 0

    from ultralytics import YOLOE
    from ultralytics.models.yolo.yoloe import YOLOEPETrainer

    model = YOLOE(args.model_yaml)
    model.load(str(pretrained))
    results = model.train(
        data=str(data_yaml),
        epochs=int(args.epochs),
        imgsz=int(args.imgsz),
        batch=args.batch,
        device=str(args.device),
        patience=int(args.patience),
        workers=int(args.workers),
        project=str(project),
        name=str(args.name),
        save_period=int(args.save_period),
        trainer=YOLOEPETrainer,
    )

    save_dir = Path(getattr(results, "save_dir", project / args.name))
    best = save_dir / "weights" / "best.pt"
    if args.copy_best and best.exists():
        weights_dir = YOLO_DIR / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        target = weights_dir / f"{args.name}_best.pt"
        shutil.copy2(best, target)
        print(json.dumps({"copied_best": rel(target)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
