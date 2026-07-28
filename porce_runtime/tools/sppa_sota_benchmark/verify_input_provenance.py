from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_LABELS = ["car", "truck", "tractor", "biker", "cow", "tree"]


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_item(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    label = str(item.get("label", ""))
    image = str(item.get("image", ""))
    if not label:
        errors.append("item missing label")
    if not image:
        errors.append(f"{label}: missing image")
    elif not resolve_repo_path(image).exists():
        errors.append(f"{label}: image does not exist: {image}")
    if item.get("is_ground_truth") is True:
        has_reference = bool(item.get("has_mask") or item.get("has_reference_mesh"))
        if not has_reference:
            errors.append(f"{label}: marked ground truth without mask or reference mesh")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA comparison input provenance.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "input_provenance.json",
    )
    parser.add_argument("--require-gt", action="store_true", help="Fail unless every item is marked as ground truth.")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    items = list(manifest.get("items", []))
    labels = [str(item.get("label", "")) for item in items]
    errors: list[str] = []

    missing = [label for label in REQUIRED_LABELS if label not in labels]
    if missing:
        errors.append("missing labels: " + ", ".join(missing))
    duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
    if duplicate_labels:
        errors.append("duplicate labels: " + ", ".join(duplicate_labels))

    for item in items:
        errors.extend(validate_item(item))

    gt_count = sum(1 for item in items if item.get("is_ground_truth") is True)
    detector_count = sum(1 for item in items if item.get("source_type") == "detector_crop")
    proxy_count = sum(1 for item in items if item.get("source_type") == "synthetic_proxy_crop")
    if args.require_gt and gt_count != len(items):
        errors.append(f"require-gt requested, but {gt_count}/{len(items)} items are ground truth")

    print(
        json.dumps(
            {
                "manifest": str(args.manifest),
                "items": len(items),
                "ground_truth_items": gt_count,
                "detector_crop_items": detector_count,
                "synthetic_proxy_items": proxy_count,
                "can_label_first_row_as_ground_truth": gt_count == len(items) and len(items) > 0,
                "errors": errors,
            },
            indent=2,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
