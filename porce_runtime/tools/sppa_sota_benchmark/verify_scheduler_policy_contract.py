from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from validate_sppa_contract import validate


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
DESC_SCHEMA = ROOT / "tools" / "sppa_sota_benchmark" / "sppa_descriptor_schema_v02.json"
UPD_SCHEMA = ROOT / "tools" / "sppa_sota_benchmark" / "sppa_update_packet_schema_v02.json"
OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_descriptor_update" / "20260703_scheduler_policy_contract"


def load_generator():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_truck_descriptor(module, length_m: float, thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    mesh = module.Mesh()
    meta = module.build_label_observed(
        mesh,
        "truck",
        dims_m={"length": length_m, "width": 2.35, "height": 2.8},
    )
    return module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.82,
        dims_m={"length": length_m, "width": 2.35, "height": 2.8},
        track_id="scheduler_policy_truck",
        frame_id=0,
        timestamp="2026-07-03T00:00:00Z",
        thresholds=thresholds,
    )


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    module = load_generator()
    failures: list[str] = []

    default_desc = build_truck_descriptor(module, 6.0)
    default_policy = default_desc["runtime_policy"]["scheduler_policy"]
    require(default_policy["policy_id"] == module.SCHEDULER_POLICY_ID, "default policy id mismatch", failures)
    require(default_policy["thresholds"] == module.DEFAULT_SCHEDULER_THRESHOLDS, "default thresholds mismatch", failures)
    require(
        default_policy["geometry_fitting_objective"]["weights"] == module.DEFAULT_GEOMETRY_FITTING_WEIGHTS,
        "default geometry fitting weights mismatch",
        failures,
    )
    require(
        default_policy["geometry_fitting_objective"]["limits"] == module.DEFAULT_GEOMETRY_FITTING_LIMITS,
        "default geometry fitting limits mismatch",
        failures,
    )

    override = {"shape_ratio": 0.10, "confidence_bucket_step": 0.10, "velocity_min_delta_m": 0.25}
    prev_desc = build_truck_descriptor(module, 6.0, override)
    curr_desc = build_truck_descriptor(module, 6.75, override)
    decision = module.schedule_descriptor_update(prev_desc, curr_desc, override)
    module.apply_schedule_to_descriptor(curr_desc, decision)
    packet = module.build_runtime_update_packet(curr_desc, decision)
    require(decision["action"] == "shape_param_update", "override should trigger shape_param_update", failures)
    require(decision["thresholds"] == override, "decision thresholds should preserve override", failures)
    require(curr_desc["runtime_policy"]["scheduler_policy"]["thresholds"] == override, "descriptor override policy mismatch", failures)
    require(packet["scheduler_policy"]["thresholds"] == override, "packet override policy mismatch", failures)
    require(packet["thresholds"] == override, "packet thresholds mismatch", failures)

    bad_threshold_errors: dict[str, str] = {}
    for name, bad in {
        "unknown_key": {"shape_ratio": 0.2, "not_a_threshold": 1.0},
        "shape_ratio_low": {"shape_ratio": 0.0},
        "confidence_bucket_high": {"confidence_bucket_step": 0.75},
        "velocity_negative": {"velocity_min_delta_m": -0.01},
    }.items():
        try:
            module.normalize_scheduler_thresholds(bad)
        except Exception as exc:
            bad_threshold_errors[name] = str(exc)
        else:
            failures.append(f"{name} override unexpectedly accepted")

    desc_schema = json.loads(DESC_SCHEMA.read_text(encoding="utf-8"))
    upd_schema = json.loads(UPD_SCHEMA.read_text(encoding="utf-8"))
    descriptor_schema_errors = validate(curr_desc, desc_schema)
    packet_schema_errors = validate(packet, upd_schema)
    require(not descriptor_schema_errors, f"descriptor schema errors: {descriptor_schema_errors}", failures)
    require(not packet_schema_errors, f"packet schema errors: {packet_schema_errors}", failures)

    (OUT_DIR / "scheduler_policy_descriptor.json").write_text(json.dumps(curr_desc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "scheduler_policy_update_packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "default_policy_id": default_policy["policy_id"],
        "default_thresholds": default_policy["thresholds"],
        "override_thresholds": override,
        "decision": decision,
        "bad_threshold_errors": bad_threshold_errors,
        "descriptor_schema_errors": descriptor_schema_errors,
        "packet_schema_errors": packet_schema_errors,
        "artifacts": {
            "descriptor": str(OUT_DIR / "scheduler_policy_descriptor.json"),
            "update_packet": str(OUT_DIR / "scheduler_policy_update_packet.json"),
        },
    }
    (OUT_DIR / "scheduler_policy_contract.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
