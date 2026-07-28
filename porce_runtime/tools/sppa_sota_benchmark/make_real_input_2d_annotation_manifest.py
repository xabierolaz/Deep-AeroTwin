#!/usr/bin/env python
"""Create a manifest for manually reviewed 2D boxes on the real user inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_real_input_annotations"
OUT_PATH = OUT_DIR / "real_input_2d_annotations.json"

PROBES = [
    {
        "label": "biker",
        "probe": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_cyclist" / "cyclist_road_yolo_probe.json",
        "reviewed_semantic_tag": "biker",
        "review_reason": "User supplied cyclist image; repository YOLO did not produce a valid biker/cyclist detection in the intended ROI.",
    },
    {
        "label": "tower",
        "probe": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tower" / "tower_mountain_yolo_probe.json",
        "reviewed_semantic_tag": "tower",
        "review_reason": "User supplied electrical-tower image; repository YOLO produced no valid tower/pylon detection in the intended ROI.",
    },
    {
        "label": "tractor",
        "probe": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tractor" / "tractor_mountain_yolo_probe.json",
        "reviewed_semantic_tag": "tractor",
        "review_reason": "User supplied tractor image; repository YOLO produced no valid tractor/vehicle detection in the intended ROI.",
    },
    {
        "label": "tractor_trailer",
        "probe": ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_user_tractor_trailer"
        / "tractor_trailer_mountain_yolo_probe.json",
        "reviewed_semantic_tag": "tractor",
        "review_reason": "User supplied tractor-with-trailer image; repository YOLO produced no valid tractor/trailer detection in the intended ROI.",
    },
]


def as_repo_path(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_probe(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_item(spec: dict[str, Any]) -> dict[str, Any]:
    probe_path = spec["probe"]
    probe = load_probe(probe_path)
    image = str(probe.get("image", "")).replace("\\", "/")
    outputs = probe.get("outputs", {})
    manual_roi = probe.get("manual_roi_xyxy")
    if not manual_roi:
        raise ValueError(f"{probe_path} does not contain manual_roi_xyxy")
    return {
        "label": spec["label"],
        "image": image,
        "probe_json": as_repo_path(probe_path),
        "image_size": probe.get("image_size"),
        "manual_bbox_xyxy": manual_roi,
        "crop_bbox_xyxy": outputs.get("crop_bbox_xyxy"),
        "crop_source": outputs.get("crop_source"),
        "image_to_3d_crop": str(outputs.get("image_to_3d_input_crop", "")).replace("\\", "/"),
        "image_to_3d_crop_512": str(outputs.get("image_to_3d_input_crop_512", "")).replace("\\", "/"),
        "reviewed_semantic_tag": spec["reviewed_semantic_tag"],
        "review_reason": spec["review_reason"],
        "is_ground_truth_2d_bbox": True,
        "is_ground_truth_3d": False,
        "has_mask": False,
        "has_reference_mesh": False,
        "bbox_source": "manual_reviewer_roi_not_detector_output",
        "semantic_tag_source": "reviewed_user_expected_tag_not_detector_output",
        "detector_valid_target_hit": False,
        "claim_boundary": (
            "This item has a manually reviewed 2D bounding box for input/crop provenance. "
            "It is not a segmentation mask, not a 3D reference mesh, and not evidence that the detector produced the semantic tag."
        ),
    }


def main() -> None:
    items = [build_item(spec) for spec in PROBES]
    manifest = {
        "schema": "SPPA-REAL-INPUT-2D-ANNOTATIONS-0.1",
        "created_utc": "2026-07-03T00:00:00Z",
        "purpose": "Record manually reviewed 2D boxes for real user-supplied inputs without promoting them to 3D ground truth.",
        "global_claim": (
            "These annotations can support detector/input provenance and crop reproducibility. "
            "They cannot support an image-to-3D SOTA ranking or a ground-truth first row for 3D quality metrics."
        ),
        "items": items,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(OUT_PATH), "items": len(items)}, indent=2))


if __name__ == "__main__":
    main()
