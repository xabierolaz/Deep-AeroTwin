#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import cv2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
Rule = Literal["union", "and"]


@dataclass(frozen=True)
class LabelLine:
    raw: str
    class_id: int
    xc: float
    yc: float
    w: float
    h: float


def _read_classes(path: Path) -> list[str]:
    classes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        classes.append(s)
    return classes


def _parse_label_line(raw: str) -> LabelLine | None:
    s = raw.strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) != 5:
        return None
    try:
        class_id = int(parts[0])
        xc = float(parts[1])
        yc = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
    except Exception:
        return None
    return LabelLine(raw=s, class_id=class_id, xc=xc, yc=yc, w=w, h=h)


def _iter_images(src_dir: Path) -> list[Path]:
    files = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    files.sort(key=lambda p: p.name.lower())
    return files


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prune extremely tiny YOLO label boxes (keeps original line formatting).")
    p.add_argument("--src", type=Path, default=(Path(__file__).resolve().parent / "source"))
    p.add_argument("--labels", type=Path, default=(Path(__file__).resolve().parent / "labels"))
    p.add_argument("--classes", type=Path, default=(Path(__file__).resolve().parent / "yolo_classes.txt"))
    p.add_argument("--min-dim", type=int, default=6, help="Remove if min(w_px, h_px) < this (pixels).")
    p.add_argument("--min-area", type=int, default=64, help="Remove if (w_px*h_px) < this (pixels^2).")
    p.add_argument("--rule", choices=["union", "and"], default="union", help="Combine min-dim and min-area.")
    p.add_argument("--dry-run", action="store_true", help="Do not modify files; just report.")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    src_dir: Path = args.src
    labels_dir: Path = args.labels
    classes_path: Path = args.classes
    min_dim: int = int(args.min_dim)
    min_area: int = int(args.min_area)
    rule: Rule = args.rule
    dry_run: bool = bool(args.dry_run)

    if not src_dir.exists():
        raise SystemExit(f"missing_source_dir:{src_dir}")
    if not labels_dir.exists():
        raise SystemExit(f"missing_labels_dir:{labels_dir}")
    if not classes_path.exists():
        raise SystemExit(f"missing_classes_file:{classes_path}")

    classes = _read_classes(classes_path)
    images = _iter_images(src_dir)
    if not images:
        raise SystemExit(f"no_images_found_in:{src_dir}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = labels_dir.parent / f"{labels_dir.name}_backup_{timestamp}"

    removed_total = 0
    removed_by_class: dict[str, int] = {}
    files_changed = 0
    files_missing = 0
    files_emptied = 0

    changed_files: list[Path] = []

    for img_path in images:
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            raise SystemExit(f"failed_to_read_image:{img_path}")
        h_img, w_img = img.shape[:2]

        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            files_missing += 1
            continue

        lines = label_path.read_text(encoding="utf-8", errors="replace").splitlines()
        parsed = [_parse_label_line(l) for l in lines]
        parsed_lines = [p for p in parsed if p is not None]

        kept_raw: list[str] = []
        removed_in_file = 0

        for p in parsed_lines:
            w_px = max(1, int(round(p.w * w_img)))
            h_px = max(1, int(round(p.h * h_img)))
            area_px = w_px * h_px

            cond_dim = min(w_px, h_px) < min_dim
            cond_area = area_px < min_area
            remove = (cond_dim or cond_area) if rule == "union" else (cond_dim and cond_area)

            if remove:
                removed_in_file += 1
                removed_total += 1
                cname = classes[p.class_id] if 0 <= p.class_id < len(classes) else f"class{p.class_id}"
                removed_by_class[cname] = removed_by_class.get(cname, 0) + 1
            else:
                kept_raw.append(p.raw)

        if removed_in_file == 0:
            continue

        files_changed += 1
        if not kept_raw:
            files_emptied += 1

        changed_files.append(label_path)

        if dry_run:
            continue

        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(label_path, backup_dir / label_path.name)
        label_path.write_text("\n".join(kept_raw) + ("\n" if kept_raw else ""), encoding="utf-8")

    print("src", str(src_dir))
    print("labels", str(labels_dir))
    print("min_dim_px", min_dim)
    print("min_area_px2", min_area)
    print("rule", rule)
    print("dry_run", dry_run)
    print("images_total", len(images))
    print("label_files_missing", files_missing)
    print("files_changed", files_changed)
    print("files_emptied", files_emptied)
    print("boxes_removed_total", removed_total)
    if removed_by_class:
        for k in sorted(removed_by_class.keys()):
            print(f"boxes_removed_{k}", removed_by_class[k])
    if dry_run:
        print("backup_dir", "(dry-run)")
    elif files_changed:
        print("backup_dir", str(backup_dir))

    if changed_files:
        print("changed_files_sample:")
        for p in changed_files[:20]:
            print(" ", p.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

