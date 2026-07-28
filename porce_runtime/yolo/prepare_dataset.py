#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
GroupMode = Literal["auto", "none", "mp4_prefix", "paren_prefix"]


@dataclass(frozen=True)
class Item:
    image: Path
    label: Path
    group: str


def _read_classes(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"missing_classes_file:{path}")
    classes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        classes.append(s)
    if not classes:
        raise SystemExit(f"empty_classes_file:{path}")
    return classes


def _extract_int(s: str) -> int | None:
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None


def _group_key(stem: str, mode: GroupMode, bucket_size: int) -> str:
    if mode == "none":
        return stem

    def mp4_key() -> str | None:
        # e.g. 0001-8765.mp40033 -> 0001-8765.mp4
        if "mp4" in stem:
            pre, _post = stem.split("mp4", 1)
            base = f"{pre}mp4"
            n = _extract_int(_post)
            if n is None:
                return base
            return f"{base}_b{(n // max(1, int(bucket_size))):04d}"
        return None

    def paren_key() -> str | None:
        # e.g. "1 (66)" -> "1"
        if "(" in stem:
            base = stem.split("(", 1)[0].strip() or stem
            inside = stem.split("(", 1)[1].split(")", 1)[0]
            n = _extract_int(inside)
            if n is None:
                return base
            return f"{base}_b{(n // max(1, int(bucket_size))):04d}"
        return None

    if mode == "mp4_prefix":
        return mp4_key() or stem
    if mode == "paren_prefix":
        return paren_key() or stem

    # auto: prefer mp4 grouping, then paren grouping, else stem.
    return mp4_key() or paren_key() or stem


def _safe_hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except Exception:
        shutil.copy2(src, dst)


def _write_yaml(path: Path, dataset_dir: Path, classes: list[str]) -> None:
    # YAML path is expected to be stable (repo-local); keep 'path' relative to this YAML file.
    rel_dataset = os.path.relpath(dataset_dir, start=path.parent).replace("\\", "/")
    lines = [
        f"path: {rel_dataset}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        "names:",
    ]
    for i, name in enumerate(classes):
        lines.append(f"  {i}: {name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare a YOLO dataset folder from yolo/source + yolo/labels.")
    p.add_argument("--src", type=Path, default=(Path(__file__).resolve().parent / "source"))
    p.add_argument("--labels", type=Path, default=(Path(__file__).resolve().parent / "labels"))
    p.add_argument("--out", type=Path, default=(Path(__file__).resolve().parent / "dataset"))
    p.add_argument("--classes", type=Path, default=(Path(__file__).resolve().parent / "yolo_classes.txt"))
    p.add_argument("--yaml-out", type=Path, default=(Path(__file__).resolve().parent / "dataset.yaml"))
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--val", type=float, default=0.15)
    p.add_argument("--test", type=float, default=0.15)
    p.add_argument("--group-mode", choices=["auto", "none", "mp4_prefix", "paren_prefix"], default="auto")
    p.add_argument("--bucket-size", type=int, default=25, help="Sequence bucket size for group-aware splitting.")
    p.add_argument("--clean", action="store_true", help="Delete output dataset dir before writing.")
    return p.parse_args(list(argv) if argv is not None else None)


def _is_label_nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(path.read_text(encoding="utf-8", errors="replace").strip())


def _split_group_keys(group_keys: list[str], rng: random.Random, val_frac: float, test_frac: float) -> tuple[set[str], set[str], set[str]]:
    """
    Split group keys into train/val/test. Guarantees non-empty splits when possible.
    Returns (train_keys, val_keys, test_keys).
    """
    keys = list(group_keys)
    rng.shuffle(keys)
    n = len(keys)
    if n >= 3:
        n_test = max(1, int(round(n * test_frac)))
        n_val = max(1, int(round(n * val_frac)))
        n_train = max(1, n - n_val - n_test)
        if n_train + n_val + n_test != n:
            n_train = n - n_val - n_test
            if n_train <= 0:
                n_train = 1
                if n_val > 1:
                    n_val -= 1
                else:
                    n_test = max(1, n_test - 1)
        # Safety: clamp slices
        n_train = max(1, min(n - 2, n_train))
        n_val = max(1, min(n - n_train - 1, n_val))
        n_test = n - n_train - n_val
    elif n == 2:
        n_train, n_val, n_test = 1, 1, 0
    else:
        n_train, n_val, n_test = 1, 0, 0

    train = set(keys[:n_train])
    val = set(keys[n_train : n_train + n_val])
    test = set(keys[n_train + n_val :])
    return train, val, test


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    src_dir: Path = args.src
    labels_dir: Path = args.labels
    out_dir: Path = args.out
    classes_path: Path = args.classes
    yaml_out: Path = args.yaml_out
    seed: int = int(args.seed)
    val_frac: float = float(args.val)
    test_frac: float = float(args.test)
    group_mode: GroupMode = args.group_mode
    bucket_size: int = int(args.bucket_size)
    clean: bool = bool(args.clean)

    if not src_dir.exists():
        raise SystemExit(f"missing_source_dir:{src_dir}")
    if not labels_dir.exists():
        raise SystemExit(f"missing_labels_dir:{labels_dir}")
    classes = _read_classes(classes_path)

    images = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    images.sort(key=lambda p: p.name.lower())
    if not images:
        raise SystemExit(f"no_images_found_in:{src_dir}")

    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    items: list[Item] = []
    missing_label = 0
    empty_label = 0
    for img in images:
        label = labels_dir / f"{img.stem}.txt"
        if not label.exists():
            missing_label += 1
        else:
            txt = label.read_text(encoding="utf-8", errors="replace").strip()
            if not txt:
                empty_label += 1
        items.append(Item(image=img, label=label, group=_group_key(img.stem, group_mode, bucket_size)))

    # Group-aware split (avoid train/val leakage by sequence)
    groups: dict[str, list[Item]] = {}
    for it in items:
        groups.setdefault(it.group, []).append(it)

    rng = random.Random(seed)
    # Split positives/negatives separately so val/test can contain negatives (needed for FP evaluation).
    pos_groups: list[str] = []
    neg_groups: list[str] = []
    for gk, gitems in groups.items():
        has_obj = any(_is_label_nonempty(it.label) for it in gitems)
        (pos_groups if has_obj else neg_groups).append(gk)

    train_pos, val_pos, test_pos = _split_group_keys(pos_groups, rng, val_frac=val_frac, test_frac=test_frac)
    train_neg, val_neg, test_neg = _split_group_keys(neg_groups, rng, val_frac=val_frac, test_frac=test_frac) if neg_groups else (set(), set(), set())

    train_keys = set(train_pos) | set(train_neg)
    val_keys = set(val_pos) | set(val_neg)
    test_keys = set(test_pos) | set(test_neg)

    def split_of(group: str) -> str:
        if group in train_keys:
            return "train"
        if group in val_keys:
            return "val"
        return "test"

    wrote_images = 0
    wrote_labels = 0
    created_empty_labels = 0

    for it in items:
        split = split_of(it.group)
        out_img = out_dir / "images" / split / it.image.name
        out_lab = out_dir / "labels" / split / f"{it.image.stem}.txt"

        _safe_hardlink_or_copy(it.image, out_img)
        wrote_images += 1

        out_lab.parent.mkdir(parents=True, exist_ok=True)
        if it.label.exists():
            if not out_lab.exists():
                shutil.copy2(it.label, out_lab)
            wrote_labels += 1
        else:
            if not out_lab.exists():
                out_lab.write_text("", encoding="utf-8")
            created_empty_labels += 1

    _write_yaml(yaml_out, out_dir, classes)

    # Summary
    counts = {"train": 0, "val": 0, "test": 0}
    for k in groups.keys():
        counts[split_of(k)] += len(groups[k])

    print("src", str(src_dir))
    print("labels", str(labels_dir))
    print("out", str(out_dir))
    print("yaml", str(yaml_out))
    print("classes", ", ".join([f"{i}:{c}" for i, c in enumerate(classes)]))
    print("group_mode", group_mode)
    print("bucket_size", bucket_size)
    print("seed", seed)
    print("split_images", counts)
    print("missing_label_files", missing_label)
    print("empty_label_files", empty_label)
    print("created_empty_labels", created_empty_labels)
    print("wrote_images", wrote_images)
    print("wrote_labels", wrote_labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
