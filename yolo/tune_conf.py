#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2


def _ensure_yolo_cfg_dir(repo_root: Path) -> None:
    # Ultralytics writes settings under %APPDATA% by default; override to repo logs.
    yolo_cfg = repo_root / "pipeline" / "logs"
    if "YOLO_CONFIG_DIR" not in os.environ:
        yolo_cfg.mkdir(parents=True, exist_ok=True)
        os.environ["YOLO_CONFIG_DIR"] = str(yolo_cfg)


@dataclass(frozen=True)
class Box:
    cls: int
    x1: float
    y1: float
    x2: float
    y2: float


def _iou(a: Box, b: Box) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    ua = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return float(inter / ua) if ua > 0.0 else 0.0


def _read_gt_labels(label_path: Path, w: int, h: int) -> list[Box]:
    if not label_path.exists():
        return []
    lines = [l.strip() for l in label_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    out: list[Box] = []
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            cls = int(parts[0])
            xc = float(parts[1]) * w
            yc = float(parts[2]) * h
            bw = float(parts[3]) * w
            bh = float(parts[4]) * h
        except Exception:
            continue
        x1 = max(0.0, xc - bw / 2.0)
        y1 = max(0.0, yc - bh / 2.0)
        x2 = min(float(w - 1), xc + bw / 2.0)
        y2 = min(float(h - 1), yc + bh / 2.0)
        if (x2 - x1) < 1.0 or (y2 - y1) < 1.0:
            continue
        out.append(Box(cls=cls, x1=x1, y1=y1, x2=x2, y2=y2))
    return out


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sweep confidence threshold to minimize false positives on negatives.")
    p.add_argument("--weights", type=Path, required=True, help="Path to trained weights (e.g. yolo/weights/final.pt).")
    p.add_argument("--dataset", type=Path, default=(Path(__file__).resolve().parent / "dataset"))
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", type=str, default="0")
    p.add_argument("--pred-batch", type=int, default=16, help="Batch size for model.predict (reduces NMS timeouts).")
    p.add_argument("--iou-match", type=float, default=0.5, help="IoU threshold for matching TP.")
    p.add_argument("--pred-iou", type=float, default=0.7, help="NMS IoU used during prediction.")
    p.add_argument("--min-conf", type=float, default=0.05)
    p.add_argument("--max-conf", type=float, default=0.95)
    p.add_argument("--step", type=float, default=0.05)
    p.add_argument("--splits", type=str, default="val,test", help="Comma-separated splits to evaluate (val,test).")
    p.add_argument("--strict-zero-fp", action="store_true", help="Select threshold with 0 images-with-FP on negatives.")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    weights: Path = args.weights
    dataset: Path = args.dataset

    repo_root = Path(__file__).resolve().parents[1]
    _ensure_yolo_cfg_dir(repo_root)

    if not weights.exists():
        raise SystemExit(f"missing_weights:{weights}")
    if not dataset.exists():
        raise SystemExit(f"missing_dataset_dir:{dataset}")

    splits = [s.strip() for s in str(args.splits).split(",") if s.strip()]
    if not splits:
        raise SystemExit("no_splits")

    # Build per-split image list + GT
    split_items: list[tuple[str, Path, list[Box], bool]] = []  # (split, img_path, gt, is_negative)
    for split in splits:
        img_dir = dataset / "images" / split
        lab_dir = dataset / "labels" / split
        if not img_dir.exists() or not lab_dir.exists():
            raise SystemExit(f"missing_split_dirs:{split}")

        img_paths = sorted([p for p in img_dir.iterdir() if p.is_file()], key=lambda p: p.name.lower())
        if not img_paths:
            continue
        for img_path in img_paths:
            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if img is None:
                raise SystemExit(f"failed_to_read_image:{img_path}")
            h, w = img.shape[:2]
            label_path = lab_dir / f"{img_path.stem}.txt"
            gt = _read_gt_labels(label_path, w=w, h=h)
            is_neg = len(gt) == 0
            split_items.append((split, img_path, gt, is_neg))

    if not split_items:
        raise SystemExit("no_images_in_splits")

    # Run a single low-conf prediction pass to collect candidate detections (then filter by conf).
    from ultralytics import YOLO

    model = YOLO(str(weights))
    img_paths_all = [p for _split, p, _gt, _neg in split_items]

    def chunks(seq: list[Path], n: int) -> list[list[Path]]:
        n = max(1, int(n))
        return [seq[i : i + n] for i in range(0, len(seq), n)]

    results = []
    for batch in chunks(img_paths_all, int(args.pred_batch)):
        # Note: conf is low to keep candidates, but NMS still applies.
        results.extend(
            model.predict(
                source=[str(p) for p in batch],
                imgsz=int(args.imgsz),
                conf=0.001,
                iou=float(args.pred_iou),
                device=str(args.device),
                max_det=300,
                verbose=False,
            )
        )

    # Index predictions by image
    preds: dict[str, list[tuple[int, float, Box]]] = {}
    for img_path, res in zip(img_paths_all, results):
        boxes = []
        if getattr(res, "boxes", None) is not None and res.boxes is not None and len(res.boxes) > 0:
            xyxy = res.boxes.xyxy.cpu().numpy()
            cls = res.boxes.cls.cpu().numpy()
            conf = res.boxes.conf.cpu().numpy()
            for (x1, y1, x2, y2), c, s in zip(xyxy, cls, conf):
                boxes.append((int(c), float(s), Box(cls=int(c), x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))))
        preds[str(img_path)] = boxes

    # Sweep thresholds
    confs: list[float] = []
    c = float(args.min_conf)
    while c <= float(args.max_conf) + 1e-9:
        confs.append(round(c, 3))
        c += float(args.step)

    def eval_at(conf_thr: float) -> dict[str, float]:
        tp = fp = fn = 0
        neg_images = 0
        neg_images_with_fp = 0
        neg_fp_boxes = 0

        for split, img_path, gt, is_neg in split_items:
            p_all = preds.get(str(img_path), [])
            p_keep = [p for p in p_all if p[1] >= conf_thr]
            p_keep.sort(key=lambda t: t[1], reverse=True)

            if is_neg:
                neg_images += 1
                if p_keep:
                    neg_images_with_fp += 1
                    neg_fp_boxes += len(p_keep)
                continue

            # Match by class with greedy IoU
            gt_unused = list(gt)
            for pc, ps, pb in p_keep:
                best_i = -1
                best_iou = 0.0
                for i, gb in enumerate(gt_unused):
                    if gb.cls != pc:
                        continue
                    v = _iou(gb, pb)
                    if v >= float(args.iou_match) and v > best_iou:
                        best_iou = v
                        best_i = i
                if best_i >= 0:
                    tp += 1
                    gt_unused.pop(best_i)
                else:
                    fp += 1
            fn += len(gt_unused)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        neg_fp_img_rate = (neg_images_with_fp / neg_images) if neg_images > 0 else 0.0
        neg_fp_boxes_per_img = (neg_fp_boxes / neg_images) if neg_images > 0 else 0.0
        return {
            "conf": conf_thr,
            "tp": float(tp),
            "fp": float(fp),
            "fn": float(fn),
            "precision": float(precision),
            "recall": float(recall),
            "neg_images": float(neg_images),
            "neg_images_with_fp": float(neg_images_with_fp),
            "neg_fp_img_rate": float(neg_fp_img_rate),
            "neg_fp_boxes_per_img": float(neg_fp_boxes_per_img),
        }

    rows = [eval_at(x) for x in confs]

    # Pick "sweet spot" for our goal: minimize FPs on negatives, then maximize recall.
    strict = bool(args.strict_zero_fp)
    candidates = rows
    if strict:
        z = [r for r in rows if int(r["neg_images_with_fp"]) == 0]
        if z:
            candidates = z

    candidates.sort(key=lambda r: (r["neg_images_with_fp"], -r["recall"], -r["precision"], r["conf"]))
    best = candidates[0]

    print("weights", str(weights))
    print("splits", ",".join(splits))
    print("images_total", len(split_items))
    neg_total = int(best["neg_images"])
    print("neg_images_total", neg_total)
    print("best_conf", best["conf"])
    print("best_precision", f"{best['precision']:.4f}")
    print("best_recall", f"{best['recall']:.4f}")
    print("best_neg_images_with_fp", int(best["neg_images_with_fp"]))
    print("best_neg_fp_img_rate", f"{best['neg_fp_img_rate']:.4f}")
    print("best_neg_fp_boxes_per_img", f"{best['neg_fp_boxes_per_img']:.4f}")
    print("")
    print("recommend_pipeline_env:")
    print(f"  set PORCE_VISION_DET_CONF={best['conf']}")
    print(f"  set PORCE_VISION_PUBLISH_CONF={best['conf']}")
    print("  set PORCE_VISION_MIN_SEEN_TO_PUBLISH=2")

    print("")
    print("sweep_summary (top 10 by (neg_fp_images asc, recall desc)):")
    top = sorted(rows, key=lambda r: (r['neg_images_with_fp'], -r['recall'], -r['precision'], r['conf']))[:10]
    for r in top:
        print(
            f"  conf={r['conf']:.2f} prec={r['precision']:.3f} rec={r['recall']:.3f} neg_fp_imgs={int(r['neg_images_with_fp'])}/{int(r['neg_images'])}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
