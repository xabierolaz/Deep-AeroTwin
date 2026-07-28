from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

CASES = [
    ("person", (0.55, 0.55, 1.75), "person", "exact_class", {"rider_clothing"}),
    ("bicycle", (1.70, 0.45, 1.15), "bicycle", "exact_class", {"bike_frame"}),
    ("cyclist", (1.85, 0.65, 2.10), "biker", "exact_class", {"bike_frame", "rider_clothing"}),
    ("motorcycle", (2.05, 0.72, 1.25), "motorcycle", "exact_class", {"vehicle_body"}),
    ("bus", (9.80, 2.55, 3.20), "bus", "exact_class", {"vehicle_body", "vehicle_window"}),
    ("light_vehicle", (4.40, 1.90, 1.55), "light_vehicle", "exact_class", {"vehicle_body", "vehicle_window"}),
    ("heavy_vehicle", (7.40, 2.45, 3.10), "heavy_vehicle", "exact_class", {"vehicle_body", "vehicle_cab"}),
    ("generic_vehicle", (6.20, 2.35, 2.60), "heavy_vehicle", "exact_class", {"vehicle_body", "vehicle_cab"}),
    ("farm_vehicle", (4.80, 2.20, 2.70), "farm_vehicle", "exact_class", {"vehicle_body", "vehicle_tire"}),
    ("articulated_vehicle", (12.00, 2.50, 3.30), "articulated_vehicle", "exact_class", {"vehicle_cab", "vehicle_tire", "vehicle_metal_or_hub", "container_body"}),
    ("tractor_trailer", (7.60, 2.15, 2.70), "tractor_trailer", "exact_class", {"vehicle_body", "vehicle_attachment", "container_body"}),
    ("vehicle with trailer", (12.00, 2.50, 3.30), "articulated_vehicle", "keyword_archetype", {"vehicle_cab", "vehicle_tire", "container_body"}),
    ("tractor pulling trailer", (8.10, 2.20, 2.80), "tractor_trailer", "keyword_archetype", {"vehicle_body", "vehicle_attachment", "container_body"}),
    ("delivery van", (5.40, 2.10, 2.30), "van", "keyword_archetype", {"vehicle_body", "vehicle_window"}),
    ("pickup truck", (5.60, 2.10, 1.95), "pickup", "keyword_archetype", {"vehicle_cab", "vehicle_body"}),
    ("two_wheeled_rider", (1.85, 0.65, 2.10), "biker", "exact_class", {"bike_frame", "rider_clothing"}),
    ("dog", (1.10, 0.35, 0.65), "quadruped", "exact_class", {"animal_body", "animal_limb"}),
    ("quadruped", (1.10, 0.35, 0.65), "quadruped", "exact_class", {"animal_body", "animal_limb"}),
    ("radio mast", (1.80, 1.80, 8.0), "vertical_structure", "keyword_archetype", {"vertical_structure_metal"}),
    ("vertical_structure", (1.80, 1.80, 8.0), "vertical_structure", "exact_class", {"vertical_structure_metal"}),
    ("power_tower", (1.80, 1.80, 8.0), "vertical_structure", "exact_class", {"vertical_structure_metal"}),
    ("building", (8.00, 6.00, 4.50), "built_structure", "exact_class", {"built_structure_body", "built_structure_roof", "built_structure_window"}),
    ("built_structure", (8.00, 6.00, 4.50), "built_structure", "exact_class", {"built_structure_body", "built_structure_roof"}),
    ("field warehouse", (18.00, 12.00, 7.00), "built_structure", "keyword_archetype", {"built_structure_body", "built_structure_roof", "built_structure_window"}),
    ("tree", (2.50, 2.50, 4.50), "tree", "exact_class", {"vegetation_trunk", "vegetation_canopy"}),
    ("vegetation", (2.50, 2.50, 4.50), "vegetation", "exact_class", {"vegetation_trunk", "vegetation_canopy"}),
    ("forklift", (3.20, 1.35, 2.20), "forklift", "open_label_verified_recipe", {"vehicle_body", "vehicle_cab", "vehicle_tire", "vehicle_attachment"}),
    ("traffic cone", (0.55, 0.55, 0.75), "traffic_cone", "open_label_verified_recipe", {"safety_marker", "container_detail"}),
    ("water tank", (3.00, 1.40, 1.60), "water_tank", "open_label_verified_recipe", {"container_body", "container_detail"}),
    ("barrel", (0.70, 0.70, 1.00), "barrel", "open_label_verified_recipe", {"container_body", "container_detail"}),
    ("shipping container", (12.20, 2.45, 2.60), "shipping_container", "open_label_verified_recipe", {"container_body", "container_detail"}),
    ("drone", (0.90, 0.90, 0.22), "quadcopter", "open_label_verified_recipe", {"aircraft_body", "aircraft_rotor"}),
    ("hay bale", (1.50, 1.50, 1.20), "hay_bale", "open_label_verified_recipe", {"agricultural_bale", "agricultural_binding"}),
    ("dog statue", (1.10, 0.35, 0.65), "unknown", "fallback_visual_artifact_context", {"unknown_conservative_volume", "unknown_footprint"}),
    ("toy tractor", (4.80, 2.20, 2.70), "unknown", "fallback_visual_artifact_context", {"unknown_conservative_volume", "unknown_footprint"}),
    ("worker helmet", (0.30, 0.25, 0.20), "unknown", "fallback_object_part_or_equipment_context", {"unknown_conservative_volume", "unknown_footprint"}),
    ("cow silhouette", (1.70, 0.55, 1.35), "unknown", "fallback_visual_artifact_context", {"unknown_conservative_volume", "unknown_footprint"}),
    ("unlisted object", (1.20, 0.70, 0.90), "unknown", "fallback_unknown_label", {"unknown_conservative_volume", "unknown_footprint"}),
]


def load_generator(path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def part_roles(mesh: Any) -> set[str]:
    roles = set()
    for part in mesh.parts:
        role = str(part.get("role") or part.get("material_role") or "")
        if role:
            roles.add(role)
    return roles


def run_case(module: Any, label: str, dims: tuple[float, float, float], expected_archetype: str, expected_status: str, required_roles: set[str]) -> dict[str, Any]:
    mesh = module.Mesh()
    meta = module.build_label_parametric(
        mesh,
        label,
        {"length": dims[0], "width": dims[1], "height": dims[2]},
    )
    roles = part_roles(mesh)
    failures = []
    if meta.get("archetype") != expected_archetype:
        failures.append(f"archetype={meta.get('archetype')} expected={expected_archetype}")
    if meta.get("resolution_status") != expected_status:
        failures.append(f"resolution_status={meta.get('resolution_status')} expected={expected_status}")
    if not required_roles.issubset(roles):
        failures.append(f"missing_roles={sorted(required_roles - roles)}")
    if expected_status == "open_label_verified_recipe" and meta.get("shape_policy") != "verified_open_label_part_layout_from_metric_dims":
        failures.append(f"shape_policy={meta.get('shape_policy')}")
    elif meta.get("archetype") != "unknown" and expected_status != "open_label_verified_recipe" and meta.get("shape_policy") != "semantic_part_layout_from_metric_dims":
        failures.append(f"shape_policy={meta.get('shape_policy')}")
    if meta.get("archetype") == "unknown" and meta.get("shape_policy") != "fallback_conservative_volume_from_metric_dims":
        failures.append(f"unknown_shape_policy={meta.get('shape_policy')}")
    return {
        "label": label,
        "dims_m": dims,
        "meta": meta,
        "part_count": len(mesh.parts),
        "triangles": module.mesh_triangle_count(mesh),
        "roles": sorted(roles),
        "status": "ok" if not failures else "failed",
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA semantic resolver coverage for common UAV labels.")
    parser.add_argument("--generator", default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"))
    parser.add_argument("--output", default="experiments/sppa_open_label_smoke/latest/semantic_resolver_coverage.json")
    args = parser.parse_args()

    module = load_generator(Path(args.generator))
    rows = [run_case(module, *case) for case in CASES]
    result = {
        "generator": args.generator,
        "total": len(rows),
        "failed": sum(1 for row in rows if row["status"] != "ok"),
        "rows": rows,
    }
    out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
