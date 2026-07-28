from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def load_generator() -> Any:
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
    return [
        [
            cx + sx * length * 0.5 * ux[0] + sy * width * 0.5 * uy[0],
            cy + sx * length * 0.5 * ux[1] + sy * width * 0.5 * uy[1],
        ]
        for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    ]


def parts_by_role(parts: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return [part for part in parts if part.get("role") == role]


def rounded_scale(part: dict[str, Any]) -> tuple[float, ...]:
    return tuple(round(float(value), 6) for value in part["scale"])


def unique_scales(parts: list[dict[str, Any]], role: str) -> list[tuple[float, ...]]:
    return sorted({rounded_scale(part) for part in parts_by_role(parts, role)})


def cargo_length(parts: list[dict[str, Any]]) -> float:
    cargos = [
        part
        for part in parts
        if part.get("primitive") == "box" and part.get("material") == "vehicle_neutral_body_prior"
    ]
    if len(cargos) != 1:
        raise AssertionError(f"Expected one truck cargo box, found {len(cargos)}")
    return float(cargos[0]["scale"][0])


def build_case(module: Any, case_id: str, mask_length_px: float, mask_width_px: float, meters_per_pixel: float) -> dict[str, Any]:
    mask = rotated_rectangle(320.0, 240.0, mask_length_px, mask_width_px, 27.5)
    scale = {
        "meters_per_pixel": meters_per_pixel,
        "source": "synthetic_ground_sample_distance",
        "confidence": 1.0,
    }
    mesh = module.Mesh()
    meta = module.build_label_observed(
        mesh,
        "truck",
        mask=mask,
        metric_scale=scale,
        height_m=2.7,
    )
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.91,
        mask=mask,
        dims_m=meta.get("effective_dims_m"),
        image_width=640,
        image_height=480,
        track_id=f"calibrated-mask-{case_id}",
        frame_id=case_id,
        timestamp="2026-07-03T00:00:00Z",
    )
    return {
        "case_id": case_id,
        "mask_length_px": mask_length_px,
        "mask_width_px": mask_width_px,
        "meters_per_pixel": meters_per_pixel,
        "expected_length_m": mask_length_px * meters_per_pixel,
        "expected_width_m": mask_width_px * meters_per_pixel,
        "meta": meta,
        "descriptor": descriptor,
        "parts": mesh.parts,
    }


def verify() -> dict[str, Any]:
    module = load_generator()
    short = build_case(module, "short", 120.0, 40.0, 0.05)
    long = build_case(module, "long", 180.0, 40.0, 0.05)

    no_calibration_mesh = module.Mesh()
    no_calibration_meta = module.build_label_observed(
        no_calibration_mesh,
        "truck",
        mask=rotated_rectangle(320.0, 240.0, 180.0, 40.0, 27.5),
        height_m=2.7,
    )

    failures: list[str] = []
    for case in (short, long):
        meta = case["meta"]
        descriptor = case["descriptor"]
        dims = meta.get("effective_dims_m") or {}
        if meta.get("shape_policy") != "semantic_part_layout_from_metric_dims":
            failures.append(f"{case['case_id']}_not_parametric")
        if meta.get("metric_dims_source") != "calibrated_mask_oriented_footprint":
            failures.append(f"{case['case_id']}_wrong_metric_dims_source")
        if descriptor.get("scale", {}).get("scale_source") != "calibrated_mask_oriented_footprint":
            failures.append(f"{case['case_id']}_descriptor_scale_source_wrong")
        if not descriptor.get("uncertainty", {}).get("scale_from_calibrated_footprint"):
            failures.append(f"{case['case_id']}_descriptor_missing_calibrated_flag")
        if abs(float(dims.get("length", 0.0)) - float(case["expected_length_m"])) > 1e-6:
            failures.append(f"{case['case_id']}_length_mismatch")
        if abs(float(dims.get("width", 0.0)) - float(case["expected_width_m"])) > 1e-6:
            failures.append(f"{case['case_id']}_width_mismatch")
        if descriptor.get("pose", {}).get("yaw_source") != "mask_pca_axial":
            failures.append(f"{case['case_id']}_yaw_not_from_mask")
        if not descriptor.get("pose", {}).get("yaw_ambiguous"):
            failures.append(f"{case['case_id']}_yaw_not_marked_ambiguous")

    short_parts = short["parts"]
    long_parts = long["parts"]
    if unique_scales(short_parts, "vehicle_cab") != unique_scales(long_parts, "vehicle_cab"):
        failures.append("cab_scale_changed_between_calibrated_masks")
    if unique_scales(short_parts, "vehicle_tire") != unique_scales(long_parts, "vehicle_tire"):
        failures.append("tire_scale_changed_between_calibrated_masks")
    short_cargo = cargo_length(short_parts)
    long_cargo = cargo_length(long_parts)
    if long_cargo <= short_cargo:
        failures.append("cargo_length_not_increased_by_longer_mask")
    if len(parts_by_role(long_parts, "vehicle_tire")) < len(parts_by_role(short_parts, "vehicle_tire")):
        failures.append("long_mask_lost_tires")
    if no_calibration_meta.get("shape_policy") != "template_prior":
        failures.append("mask_without_metric_scale_changed_geometry")
    if no_calibration_meta.get("metric_dims_source") is not None:
        failures.append("mask_without_metric_scale_reported_metric_source")

    result = {
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "short_effective_dims_m": short["meta"].get("effective_dims_m"),
        "long_effective_dims_m": long["meta"].get("effective_dims_m"),
        "short_cargo_length_m": round(short_cargo, 6),
        "long_cargo_length_m": round(long_cargo, 6),
        "cargo_length_delta_m": round(long_cargo - short_cargo, 6),
        "short_cab_scales": [list(value) for value in unique_scales(short_parts, "vehicle_cab")],
        "long_cab_scales": [list(value) for value in unique_scales(long_parts, "vehicle_cab")],
        "short_tire_scales": [list(value) for value in unique_scales(short_parts, "vehicle_tire")],
        "long_tire_scales": [list(value) for value in unique_scales(long_parts, "vehicle_tire")],
        "short_tire_count": len(parts_by_role(short_parts, "vehicle_tire")),
        "long_tire_count": len(parts_by_role(long_parts, "vehicle_tire")),
        "no_calibration_shape_policy": no_calibration_meta.get("shape_policy"),
        "descriptor_scale_sources": {
            "short": short["descriptor"].get("scale", {}).get("scale_source"),
            "long": long["descriptor"].get("scale", {}).get("scale_source"),
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify calibrated mask footprint adaptation reaches SPPA geometry without root-scale deformation."
    )
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = verify()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
