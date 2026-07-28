#!/usr/bin/env python
"""Verify manually reviewed 2D annotations for real SPPA input probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_real_input_annotations" / "real_input_2d_annotations.json"


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def bbox_valid(bbox: list[Any], width: int, height: int) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    try:
        x0, y0, x1, y1 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return False
    return 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height


def verify(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return {
            "manifest": str(path),
            "exists": False,
            "items": 0,
            "errors": ["manifest_missing"],
            "warnings": [],
            "bbox_gt_2d_items": 0,
            "gt_3d_items": 0,
            "can_support_3d_sota_gt": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.get("items", []))
    for item in items:
        label = item.get("label", "unknown")
        image_path = resolve_path(str(item.get("image", "")))
        crop_path = resolve_path(str(item.get("image_to_3d_crop", "")))
        crop_512_path = resolve_path(str(item.get("image_to_3d_crop_512", "")))
        if not image_path.exists():
            errors.append(f"{label}:image_missing")
            continue
        try:
            image = Image.open(image_path)
            width, height = image.size
        except Exception as exc:
            errors.append(f"{label}:image_unreadable:{exc}")
            continue
        if not bbox_valid(item.get("manual_bbox_xyxy"), width, height):
            errors.append(f"{label}:manual_bbox_out_of_bounds")
        if item.get("crop_bbox_xyxy") and not bbox_valid(item.get("crop_bbox_xyxy"), width, height):
            errors.append(f"{label}:crop_bbox_out_of_bounds")
        if not crop_path.exists():
            errors.append(f"{label}:crop_missing")
        if not crop_512_path.exists():
            errors.append(f"{label}:crop_512_missing")
        if item.get("is_ground_truth_2d_bbox") is not True:
            errors.append(f"{label}:not_marked_2d_bbox_gt")
        if item.get("is_ground_truth_3d") is True:
            errors.append(f"{label}:incorrectly_marked_3d_gt")
        if item.get("has_reference_mesh") is True:
            errors.append(f"{label}:incorrectly_marked_reference_mesh")
        if item.get("has_mask") is True:
            warnings.append(f"{label}:mask_marked_true_verify_mask_artifact")
        if item.get("detector_valid_target_hit") is True:
            warnings.append(f"{label}:detector_valid_hit_true_verify_probe")
    bbox_gt_2d_items = sum(1 for item in items if item.get("is_ground_truth_2d_bbox") is True)
    gt_3d_items = sum(1 for item in items if item.get("is_ground_truth_3d") is True)
    return {
        "manifest": str(path),
        "exists": True,
        "items": len(items),
        "errors": errors,
        "warnings": warnings,
        "bbox_gt_2d_items": bbox_gt_2d_items,
        "gt_3d_items": gt_3d_items,
        "can_support_3d_sota_gt": False,
        "claim_boundary": data.get("global_claim"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if verification fails.")
    args = parser.parse_args()
    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    report = verify(manifest)
    print(json.dumps(report, indent=2))
    if args.strict and report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
