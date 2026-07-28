from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rotated_rectangle(cx: float, cy: float, length: float, width: float, angle_deg: float) -> list[list[float]]:
    theta = math.radians(angle_deg)
    ux = (math.cos(theta), math.sin(theta))
    uy = (-math.sin(theta), math.cos(theta))
    corners = []
    for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
        x = cx + sx * length * 0.5 * ux[0] + sy * width * 0.5 * uy[0]
        y = cy + sx * length * 0.5 * ux[1] + sy * width * 0.5 * uy[1]
        corners.append([x, y])
    return corners


def axial_angle_error_deg(a: float, b: float) -> float:
    diff = abs((a - b) % 180.0)
    return min(diff, 180.0 - diff)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify mask PCA oriented footprint in SPPA descriptors.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    module = load_generator()
    target_length = 120.0
    target_width = 40.0
    target_angle = 33.0
    mask = rotated_rectangle(300.0, 220.0, target_length, target_width, target_angle)

    mesh = module.Mesh()
    meta = module.build_label_parametric(mesh, "truck")
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.86,
        mask=mask,
        image_width=640,
        image_height=480,
        track_id="mask-footprint-check",
        frame_id="f0001",
        timestamp="2026-07-02T00:00:00Z",
    )

    mask_meta = descriptor["evidence"]["mask_ref_or_polygon"]
    oriented = mask_meta.get("oriented_footprint_px")
    bbox = mask_meta.get("bbox_px")
    scale_footprint = descriptor["scale"]["footprint_px"]
    yaw = descriptor["pose"]

    failures = []
    if not oriented:
        failures.append("missing_oriented_footprint")
    else:
        if oriented.get("source") != "mask_oriented_pca":
            failures.append("oriented_source_not_mask_pca")
        if abs(oriented["length"] - target_length) > 0.75:
            failures.append("oriented_length_error_gt_0.75px")
        if abs(oriented["width"] - target_width) > 0.75:
            failures.append("oriented_width_error_gt_0.75px")
        if axial_angle_error_deg(oriented["orientation_deg_axial"], target_angle) > 0.75:
            failures.append("oriented_angle_error_gt_0.75deg")
        if oriented.get("fill_ratio") is None or oriented["fill_ratio"] < 0.98:
            failures.append("fill_ratio_lt_0.98")
    if scale_footprint.get("source") != "mask_oriented_pca":
        failures.append("descriptor_scale_not_using_oriented_mask")
    if yaw.get("yaw_source") != "mask_pca_axial" or not yaw.get("yaw_ambiguous"):
        failures.append("mask_yaw_not_axial_ambiguous")
    if bbox and oriented:
        bbox_error = abs(bbox["w"] - target_length) + abs(bbox["h"] - target_width)
        oriented_error = abs(oriented["length"] - target_length) + abs(oriented["width"] - target_width)
        if oriented_error >= bbox_error:
            failures.append("oriented_not_better_than_aabb_for_rotated_rectangle")

    result = {
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "target": {"length": target_length, "width": target_width, "angle_deg_axial": target_angle},
        "mask_bbox_px": bbox,
        "oriented_footprint_px": oriented,
        "descriptor_scale_footprint_px": scale_footprint,
        "pose_yaw": {
            "yaw_source": yaw.get("yaw_source"),
            "yaw_modulo": yaw.get("yaw_modulo"),
            "yaw_ambiguous": yaw.get("yaw_ambiguous"),
            "yaw_deg": yaw.get("yaw_deg"),
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
