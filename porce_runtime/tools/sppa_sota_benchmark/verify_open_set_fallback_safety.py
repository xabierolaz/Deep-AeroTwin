from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


CASES = [
    {
        "label": "toy truck",
        "expect_archetype": "unknown",
        "expect_status": "fallback_visual_artifact_context",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "vehicle shadow",
        "expect_archetype": "unknown",
        "expect_status": "fallback_visual_artifact_context",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "dog statue",
        "expect_archetype": "unknown",
        "expect_status": "fallback_visual_artifact_context",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "person poster",
        "expect_archetype": "unknown",
        "expect_status": "fallback_visual_artifact_context",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "worker helmet",
        "expect_archetype": "unknown",
        "expect_status": "fallback_object_part_or_equipment_context",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "construction cone",
        "expect_archetype": "unknown",
        "expect_status": "fallback_unknown_label",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "satellite dish",
        "expect_archetype": "unknown",
        "expect_status": "fallback_unknown_label",
        "expect_unknown": True,
        "required_roles": {"unknown_conservative_volume", "unknown_footprint", "uncertainty_marker"},
    },
    {
        "label": "animal feed trailer",
        "expect_archetype": "heavy_vehicle",
        "expect_status": "keyword_archetype",
        "expect_unknown": False,
        "required_roles": {"vehicle_body", "vehicle_cab", "vehicle_tire"},
    },
    {
        "label": "horse trailer",
        "expect_archetype": "heavy_vehicle",
        "expect_status": "keyword_archetype",
        "expect_unknown": False,
        "required_roles": {"vehicle_body", "vehicle_cab", "vehicle_tire"},
    },
    {
        "label": "emergency vehicle",
        "expect_archetype": "light_vehicle",
        "expect_status": "keyword_archetype",
        "expect_unknown": False,
        "required_roles": {"vehicle_body", "vehicle_cab", "vehicle_tire"},
    },
    {
        "label": "road sign",
        "expect_archetype": "vertical_structure",
        "expect_status": "keyword_archetype",
        "expect_unknown": False,
        "required_roles": {"vertical_structure_metal"},
    },
    {
        "label": "field worker",
        "expect_archetype": "person",
        "expect_status": "keyword_archetype",
        "expect_unknown": False,
        "required_roles": {"rider_clothing", "rider_skin"},
    },
]


def load_generator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def part_material_roles(parts: list[dict[str, Any]]) -> set[str]:
    roles: set[str] = set()
    for part in parts:
        for key in ("material_role", "role"):
            value = part.get(key)
            if value:
                roles.add(str(value))
        meta = part.get("meta")
        if isinstance(meta, dict):
            value = meta.get("material_role")
            if value:
                roles.add(str(value))
    return roles


def run_case(module: Any, case: dict[str, Any]) -> dict[str, Any]:
    label = str(case["label"])
    mesh = module.Mesh()
    dims_m = {"length": 4.0, "width": 2.0, "height": 2.0}
    meta = module.build_label_parametric(mesh, label, dims_m)
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.44 if case["expect_unknown"] else 0.78,
        bbox={"x": 10, "y": 20, "w": 80, "h": 40},
        dims_m=dims_m,
        observed_color=[255, 0, 0],
        track_id=f"adv-{label.replace(' ', '-')}",
    )
    roles = part_material_roles(descriptor.get("parts") or [])
    failures: list[str] = []

    semantic = descriptor.get("semantic") or {}
    resolver = descriptor.get("resolver") or {}
    material = descriptor.get("material") or {}
    uncertainty = descriptor.get("uncertainty") or {}

    if semantic.get("archetype") != case["expect_archetype"]:
        failures.append(f"archetype={semantic.get('archetype')} expected={case['expect_archetype']}")
    if semantic.get("resolution_status") != case["expect_status"]:
        failures.append(f"resolution_status={semantic.get('resolution_status')} expected={case['expect_status']}")
    if semantic.get("unknown_label") is not case["expect_unknown"]:
        failures.append(f"unknown_label={semantic.get('unknown_label')} expected={case['expect_unknown']}")
    if resolver.get("runtime_llm_used") is not False:
        failures.append("runtime_llm_used must be false")
    if not set(case["required_roles"]).issubset(roles):
        failures.append(f"missing_roles={sorted(set(case['required_roles']) - roles)}")
    if case["expect_unknown"]:
        if semantic.get("match_type") != "fallback_unknown":
            failures.append(f"fallback match_type={semantic.get('match_type')}")
        if not semantic.get("fallback_reason"):
            failures.append("fallback_reason missing")
        if material.get("material_source") != "fallback_unknown":
            failures.append(f"material_source={material.get('material_source')}")
        if material.get("observed_color_applied") is not False:
            failures.append("observed color must not be applied to fallback unknown")
        if uncertainty.get("fallback_unknown") is not True:
            failures.append("uncertainty fallback_unknown must be true")
        if uncertainty.get("shape_low_confidence") is not True:
            failures.append("fallback test confidence should mark shape_low_confidence")
    else:
        if semantic.get("match_type") != "keyword":
            failures.append(f"non-exact adversarial cases should remain keyword, got {semantic.get('match_type')}")
        if uncertainty.get("fallback_unknown") is not False:
            failures.append("non-fallback case marked fallback_unknown")

    return {
        "label": label,
        "expected_archetype": case["expect_archetype"],
        "expected_status": case["expect_status"],
        "meta": meta,
        "semantic": semantic,
        "resolver": resolver,
        "uncertainty": uncertainty,
        "roles": sorted(roles),
        "part_count": len(descriptor.get("parts") or []),
        "triangles": descriptor.get("mesh", {}).get("triangles"),
        "status": "ok" if not failures else "failed",
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit SPPA open-set fallback and false-confidence guard cases.")
    parser.add_argument("--generator", default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"))
    parser.add_argument("--output", default="experiments/sppa_open_label_smoke/latest/open_set_fallback_safety.json")
    args = parser.parse_args()

    module = load_generator(Path(args.generator))
    rows = [run_case(module, case) for case in CASES]
    result = {
        "generator": str(Path(args.generator)),
        "scope": (
            "Adversarial label-resolution contract. Passing means selected visual-artifact/equipment labels "
            "fall back to unknown and selected compound labels resolve only to reviewed family archetypes; "
            "it is not a human-factors validation."
        ),
        "total": len(rows),
        "failed": sum(1 for row in rows if row["status"] != "ok"),
        "rows": rows,
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
