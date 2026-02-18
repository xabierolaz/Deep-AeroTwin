#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class Imported:
    src: Path
    dst_img: Path
    dst_label: Path


def _is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXTS


def _safe_hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except Exception:
        shutil.copy2(src, dst)


def _unique_name(target_dir: Path, preferred_name: str) -> str:
    base = Path(preferred_name).stem
    ext = Path(preferred_name).suffix
    candidate = preferred_name
    i = 2
    while (target_dir / candidate).exists():
        candidate = f"{base}_{i}{ext}"
        i += 1
    return candidate


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import negative images and create empty YOLO label files.")
    p.add_argument("--from-dir", type=Path, required=True, help="Directory containing negative images.")
    p.add_argument("--to-source", type=Path, default=(Path(__file__).resolve().parent / "source"))
    p.add_argument("--to-labels", type=Path, default=(Path(__file__).resolve().parent / "labels"))
    p.add_argument("--prefix", type=str, default="neg_", help="Prefix to avoid filename collisions.")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    from_dir: Path = args.from_dir
    to_source: Path = args.to_source
    to_labels: Path = args.to_labels
    prefix: str = str(args.prefix)
    dry_run: bool = bool(args.dry_run)

    if not from_dir.exists():
        raise SystemExit(f"missing_from_dir:{from_dir}")

    images = [p for p in from_dir.iterdir() if _is_image(p)]
    images.sort(key=lambda p: p.name.lower())
    if not images:
        raise SystemExit(f"no_images_found_in:{from_dir}")

    to_source.mkdir(parents=True, exist_ok=True)
    to_labels.mkdir(parents=True, exist_ok=True)

    imported: list[Imported] = []
    for src in images:
        preferred = f"{prefix}{src.name}"
        unique = _unique_name(to_source, preferred)
        dst_img = to_source / unique
        dst_label = to_labels / f"{Path(unique).stem}.txt"

        imported.append(Imported(src=src, dst_img=dst_img, dst_label=dst_label))

        if dry_run:
            continue

        _safe_hardlink_or_copy(src, dst_img)
        if not dst_label.exists():
            dst_label.write_text("", encoding="utf-8")

    print("from_dir", str(from_dir))
    print("to_source", str(to_source))
    print("to_labels", str(to_labels))
    print("prefix", prefix)
    print("dry_run", dry_run)
    print("images_found", len(images))
    print("imported", len(imported))
    print("sample:")
    for it in imported[:10]:
        print(" ", it.src.name, "->", it.dst_img.name, "+", it.dst_label.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

