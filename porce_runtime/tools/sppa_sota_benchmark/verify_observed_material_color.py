from __future__ import annotations

import argparse
import importlib.util
import json
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


def build_descriptor(module, label: str, dims_m, observed_color):
    mesh = module.Mesh()
    meta = module.build_label_parametric(mesh, label, dims_m)
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.87,
        dims_m=dims_m,
        observed_color=observed_color,
        track_id=f"observed-material-{label.replace(' ', '-')}",
        timestamp="2026-07-02T00:00:00Z",
        frame_id="f0001",
    )
    manifest = module.build_material_manifest(mesh, meta, 0.87, module.normalize_observed_color(observed_color))
    return descriptor, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify optional observed-color material evidence in SPPA descriptors.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    module = load_generator()
    observed = {"rgb255": [200, 80, 32], "source": "synthetic_crop_median", "confidence": 0.74}
    vehicle_descriptor, vehicle_manifest = build_descriptor(
        module,
        "delivery van",
        {"length": 5.4, "width": 2.1, "height": 2.3},
        observed,
    )
    unknown_descriptor, unknown_manifest = build_descriptor(
        module,
        "unlisted object",
        {"length": 1.2, "width": 0.7, "height": 0.9},
        observed,
    )

    failures: list[str] = []
    expected_rgb = [round(v / 255.0, 6) for v in [200, 80, 32]]
    vehicle_parts = vehicle_descriptor["parts"]
    observed_parts = [p for p in vehicle_parts if p.get("evidence_source") == "observed_color_input"]
    tire_parts = [p for p in vehicle_parts if p.get("material_role") == "vehicle_tire"]
    window_parts = [p for p in vehicle_parts if p.get("material_role") == "vehicle_window"]

    if vehicle_descriptor["material"]["material_source"] != "observed_color_input":
        failures.append("vehicle_descriptor_material_source_not_observed")
    if not vehicle_descriptor["uncertainty"]["material_from_observation"]:
        failures.append("vehicle_uncertainty_material_from_observation_false")
    if not vehicle_descriptor["uncertainty"]["material_from_prior"]:
        failures.append("vehicle_material_from_prior_should_remain_true")
    if not observed_parts:
        failures.append("no_parts_marked_observed_color_input")
    if vehicle_descriptor["material"]["observed_color"]["rgb"] != expected_rgb:
        failures.append("descriptor_global_observed_rgb_mismatch")
    if any(p.get("observed_color_ref") != "material.observed_color" for p in observed_parts):
        failures.append("observed_part_ref_mismatch")
    if any(p.get("evidence_source") == "observed_color_input" for p in tire_parts):
        failures.append("vehicle_tires_should_remain_semantic_prior")
    if any(p.get("evidence_source") == "observed_color_input" for p in window_parts):
        failures.append("vehicle_windows_should_remain_semantic_prior")
    if unknown_descriptor["material"]["material_source"] != "fallback_unknown":
        failures.append("unknown_descriptor_material_source_not_fallback")
    if unknown_descriptor["material"]["observed_color_applied"]:
        failures.append("unknown_descriptor_should_not_apply_observed_color")
    if any(p.get("evidence_source") == "observed_color_input" for p in unknown_descriptor["parts"]):
        failures.append("unknown_parts_should_not_use_observed_color")

    manifest_observed = [
        m for m in vehicle_manifest["materials"] if m.get("evidence_source") == "observed_color_input"
    ]
    if not manifest_observed:
        failures.append("vehicle_manifest_missing_observed_material")
    if unknown_manifest["observed_color"] is None:
        failures.append("unknown_manifest_should_record_supplied_color_as_evidence")

    result = {
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "expected_rgb": expected_rgb,
        "vehicle": {
            "material_source": vehicle_descriptor["material"]["material_source"],
            "observed_color_applied": vehicle_descriptor["material"]["observed_color_applied"],
            "observed_part_count": len(observed_parts),
            "tire_part_count": len(tire_parts),
            "window_part_count": len(window_parts),
            "manifest_observed_material_count": len(manifest_observed),
            "descriptor_bytes": vehicle_descriptor["cost"]["descriptor_bytes"],
        },
        "unknown": {
            "material_source": unknown_descriptor["material"]["material_source"],
            "observed_color_applied": unknown_descriptor["material"]["observed_color_applied"],
            "observed_part_count": sum(1 for p in unknown_descriptor["parts"] if p.get("evidence_source") == "observed_color_input"),
            "descriptor_bytes": unknown_descriptor["cost"]["descriptor_bytes"],
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
