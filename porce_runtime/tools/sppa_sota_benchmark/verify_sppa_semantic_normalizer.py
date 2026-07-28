from __future__ import annotations

import json
from pathlib import Path

from sppa_semantic_normalizer import (
    normalize_detection_set,
    normalize_runtime_detection,
    refine_normalized_with_observation,
)

ROOT = Path(__file__).resolve().parents[2]


CASES = [
    {
        "name": "cyclist_from_person_plus_motorcycle",
        "detections": [
            {"class_name": "motorcycle", "confidence": 0.42},
            {"class_name": "person", "confidence": 0.12},
        ],
        "expect_sppa_tag": "two_wheeled_rider",
        "expect_runtime_archetype": "biker",
        "expect_conservative": False,
    },
    {
        "name": "power_tower_from_electric_pylon",
        "detections": [{"class_name": "electric pylon", "confidence": 0.46}],
        "expect_sppa_tag": "power_tower",
        "expect_runtime_archetype": "vertical_structure",
        "expect_conservative": False,
    },
    {
        "name": "farm_vehicle_from_agricultural_vehicle",
        "detections": [{"class_name": "agricultural vehicle", "confidence": 0.52}],
        "expect_sppa_tag": "farm_vehicle",
        "expect_runtime_archetype": "farm_vehicle",
        "expect_conservative": False,
    },
    {
        "name": "generic_vehicle_conservative_proxy",
        "detections": [{"class_name": "vehicle", "confidence": 0.47}],
        "expect_sppa_tag": "generic_vehicle",
        "expect_runtime_archetype": "heavy_vehicle",
        "expect_conservative": True,
    },
    {
        "name": "specific_car_stays_light_vehicle",
        "detections": [{"class_name": "car", "confidence": 0.70}],
        "expect_sppa_tag": "light_vehicle",
        "expect_runtime_archetype": "light_vehicle",
        "expect_conservative": False,
    },
    {
        "name": "trailer_is_heavy_vehicle",
        "detections": [{"class_name": "trailer", "confidence": 0.33}],
        "expect_sppa_tag": "heavy_vehicle",
        "expect_runtime_archetype": "heavy_vehicle",
        "expect_conservative": True,
    },
    {
        "name": "excavator_is_heavy_vehicle",
        "detections": [{"class_name": "excavator", "confidence": 0.39}],
        "expect_sppa_tag": "heavy_vehicle",
        "expect_runtime_archetype": "heavy_vehicle",
        "expect_conservative": True,
    },
    {
        "name": "crane_is_vertical_structure",
        "detections": [{"class_name": "crane", "confidence": 0.36}],
        "expect_sppa_tag": "vertical_structure",
        "expect_runtime_archetype": "vertical_structure",
        "expect_conservative": True,
    },
    {
        "name": "antenna_is_vertical_structure",
        "detections": [{"class_name": "antenna", "confidence": 0.35}],
        "expect_sppa_tag": "vertical_structure",
        "expect_runtime_archetype": "vertical_structure",
        "expect_conservative": False,
    },
    {
        "name": "road_sign_is_vertical_structure",
        "detections": [{"class_name": "road sign", "confidence": 0.35}],
        "expect_sppa_tag": "vertical_structure",
        "expect_runtime_archetype": "vertical_structure",
        "expect_conservative": False,
    },
    {
        "name": "forklift_is_open_label_industrial_vehicle",
        "detections": [{"class_name": "forklift", "confidence": 0.35}],
        "expect_sppa_tag": "industrial_vehicle",
        "expect_runtime_archetype": "forklift",
        "expect_conservative": True,
    },
    {
        "name": "traffic_cone_is_open_label_safety_marker",
        "detections": [{"class_name": "traffic cone", "confidence": 0.35}],
        "expect_sppa_tag": "safety_marker",
        "expect_runtime_archetype": "traffic_cone",
        "expect_conservative": True,
    },
    {
        "name": "water_tank_is_open_label_storage_container",
        "detections": [{"class_name": "water tank", "confidence": 0.35}],
        "expect_sppa_tag": "storage_container",
        "expect_runtime_archetype": "water_tank",
        "expect_conservative": True,
    },
    {
        "name": "barrel_is_open_label_storage_container",
        "detections": [{"class_name": "barrel", "confidence": 0.35}],
        "expect_sppa_tag": "storage_container",
        "expect_runtime_archetype": "barrel",
        "expect_conservative": True,
    },
    {
        "name": "shipping_container_is_open_label_storage_container",
        "detections": [{"class_name": "shipping container", "confidence": 0.35}],
        "expect_sppa_tag": "storage_container",
        "expect_runtime_archetype": "shipping_container",
        "expect_conservative": True,
    },
    {
        "name": "drone_is_open_label_uav_aircraft",
        "detections": [{"class_name": "drone", "confidence": 0.35}],
        "expect_sppa_tag": "uav_aircraft",
        "expect_runtime_archetype": "quadcopter",
        "expect_conservative": True,
    },
    {
        "name": "hay_bale_is_open_label_agricultural_bale",
        "detections": [{"class_name": "hay bale", "confidence": 0.35}],
        "expect_sppa_tag": "agricultural_bale",
        "expect_runtime_archetype": "hay_bale",
        "expect_conservative": True,
    },
    {
        "name": "building_is_reviewed_structure",
        "detections": [{"class_name": "building", "confidence": 0.61}],
        "expect_sppa_tag": "built_structure",
        "expect_runtime_archetype": "built_structure",
        "expect_conservative": False,
    },
    {
        "name": "tree_is_vegetation_family",
        "detections": [{"class_name": "tree", "confidence": 0.58}],
        "expect_sppa_tag": "vegetation",
        "expect_runtime_archetype": "vegetation",
        "expect_conservative": False,
    },
    {
        "name": "unknown_label_remains_conservative",
        "detections": [{"class_name": "satellite dish", "confidence": 0.44}],
        "expect_sppa_tag": "unknown",
        "expect_runtime_archetype": "unknown",
        "expect_conservative": True,
    },
    {
        "name": "toy_tractor_stays_fallback",
        "detections": [{"class_name": "toy tractor", "confidence": 0.44}],
        "expect_sppa_tag": "unknown",
        "expect_runtime_archetype": "unknown",
        "expect_conservative": True,
    },
    {
        "name": "worker_helmet_stays_fallback",
        "detections": [{"class_name": "worker helmet", "confidence": 0.44}],
        "expect_sppa_tag": "unknown",
        "expect_runtime_archetype": "unknown",
        "expect_conservative": True,
    },
    {
        "name": "cow_silhouette_stays_fallback",
        "detections": [{"class_name": "cow silhouette", "confidence": 0.44}],
        "expect_sppa_tag": "unknown",
        "expect_runtime_archetype": "unknown",
        "expect_conservative": True,
    },
]

RUNTIME_CASES = [
    {
        "name": "runtime_reviewed_cyclist_stays_biker",
        "detection": {"class_name": "cyclist", "confidence": 0.42},
        "canonical_label": "biker",
        "expect_runtime_label": "biker",
        "expect_sppa_tag": "two_wheeled_rider",
    },
    {
        "name": "runtime_reviewed_tower_stays_tower",
        "detection": {"class_name": "electric pylon", "confidence": 0.46},
        "canonical_label": "tower",
        "expect_runtime_label": "tower",
        "expect_sppa_tag": "power_tower",
    },
    {
        "name": "runtime_farm_vehicle_is_family_proxy",
        "detection": {"class_name": "agricultural vehicle", "confidence": 0.52},
        "canonical_label": "agricultural vehicle",
        "expect_runtime_label": "farm_vehicle",
        "expect_sppa_tag": "farm_vehicle",
    },
    {
        "name": "runtime_generic_vehicle_is_conservative_heavy",
        "detection": {"class_name": "vehicle", "confidence": 0.47},
        "canonical_label": "vehicle",
        "expect_runtime_label": "heavy_vehicle",
        "expect_sppa_tag": "generic_vehicle",
    },
]

OBSERVATION_REFINEMENT_CASES = [
    {
        "name": "generic_vehicle_long_footprint_refines_to_articulated",
        "detection": {"class_name": "vehicle", "confidence": 0.47},
        "metric_dims_m": {"length": 16.85, "width": 6.21, "height": 3.40},
        "uncertainty": {"shape_low_confidence": True},
        "expect_sppa_tag": "articulated_vehicle",
        "expect_runtime_archetype": "articulated_vehicle",
        "expect_applied": True,
    },
    {
        "name": "generic_vehicle_short_footprint_stays_heavy",
        "detection": {"class_name": "vehicle", "confidence": 0.47},
        "metric_dims_m": {"length": 4.8, "width": 2.0, "height": 1.8},
        "uncertainty": {"shape_low_confidence": False},
        "expect_sppa_tag": "generic_vehicle",
        "expect_runtime_archetype": "heavy_vehicle",
        "expect_applied": False,
    },
]


def main() -> None:
    rows = []
    runtime_rows = []
    failures = []
    for case in CASES:
        selected = normalize_detection_set(case["detections"])
        row = {"case": case["name"], "selected": selected, "status": "ok", "failures": []}
        if selected is None:
            row["status"] = "failed"
            row["failures"].append("no_selection")
        else:
            checks = [
                ("sppa_tag", case["expect_sppa_tag"]),
                ("runtime_archetype_id", case["expect_runtime_archetype"]),
                ("conservative", case["expect_conservative"]),
            ]
            for key, expected in checks:
                if selected.get(key) != expected:
                    row["failures"].append(f"{key}={selected.get(key)} expected={expected}")
            if row["failures"]:
                row["status"] = "failed"
        failures.extend(f"{case['name']}:{failure}" for failure in row["failures"])
        rows.append(row)

    for case in RUNTIME_CASES:
        selected = normalize_runtime_detection(case["detection"], case["canonical_label"])
        row = {"case": case["name"], "selected": selected, "status": "ok", "failures": []}
        for key, expected in (
            ("runtime_label", case["expect_runtime_label"]),
            ("sppa_tag", case["expect_sppa_tag"]),
        ):
            if selected.get(key) != expected:
                row["failures"].append(f"{key}={selected.get(key)} expected={expected}")
        if row["failures"]:
            row["status"] = "failed"
        failures.extend(f"{case['name']}:{failure}" for failure in row["failures"])
        runtime_rows.append(row)

    refinement_rows = []
    for case in OBSERVATION_REFINEMENT_CASES:
        base = normalize_detection_set([case["detection"]])
        selected = refine_normalized_with_observation(base, case["metric_dims_m"], case["uncertainty"])
        row = {"case": case["name"], "selected": selected, "status": "ok", "failures": []}
        if selected is None:
            row["status"] = "failed"
            row["failures"].append("no_selection")
        else:
            refinement = selected.get("observation_refinement") or {}
            for key, expected in (
                ("sppa_tag", case["expect_sppa_tag"]),
                ("runtime_archetype_id", case["expect_runtime_archetype"]),
            ):
                if selected.get(key) != expected:
                    row["failures"].append(f"{key}={selected.get(key)} expected={expected}")
            if bool(refinement.get("applied")) != bool(case["expect_applied"]):
                row["failures"].append(f"applied={refinement.get('applied')} expected={case['expect_applied']}")
            if row["failures"]:
                row["status"] = "failed"
        failures.extend(f"{case['name']}:{failure}" for failure in row["failures"])
        refinement_rows.append(row)

    result = {
        "schema": "SPPA-SEMANTIC-NORMALIZER-VERIFY-0.1",
        "scope": "Verifies hierarchical detector-label to SPPA-proxy normalization for paper-facing YOLOE probes.",
        "total": len(rows) + len(runtime_rows) + len(refinement_rows),
        "failed": len(failures),
        "failures": failures,
        "rows": rows,
        "runtime_rows": runtime_rows,
        "observation_refinement_rows": refinement_rows,
    }
    out_path = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_yoloe26s_open_vocab" / "sppa_semantic_normalizer_verify.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
