from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from sppa_observation import build_sppa_observation_contract, descriptor_kwargs_from_observation  # noqa: E402
from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402


OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_geometric_projection" / "20260704_sppa_observation_contract"


def assert_close(name: str, value: float, expected: float, tol: float, failures: list[str]) -> None:
    if not math.isfinite(float(value)) or abs(float(value) - float(expected)) > float(tol):
        failures.append(f"{name}: got {value}, expected {expected} +/- {tol}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    flight = {
        "image_height": 1000,
        "image_width": 1000,
        "drone_yaw_deg": 0.0,
        "drone_pitch_deg": 0.0,
        "drone_roll_deg": 0.0,
        "alt_agl_m": 10.0,
        "camera_vfov_deg": 90.0,
        "mount_roll_deg": 0.0,
        "mount_pitch_deg": -90.0,
        "mount_yaw_deg": 0.0,
        "max_range_m": 100.0,
    }
    observation = build_sppa_observation_contract(
        label="vehicle",
        confidence=0.84,
        bbox={"x1": 400, "y1": 450, "x2": 600, "y2": 550},
        image_width=1000,
        image_height=1000,
        flight=flight,
        height_prior_m=1.6,
        track_id="sppa-observation-vehicle-01",
        frame_id=7,
        timestamp="2026-07-04T00:00:00Z",
        telemetry_measured=False,
        metric_ground_truth=False,
        source="synthetic_declared_flight_regression",
    )
    if observation.get("status") != "metric_observation_ready":
        failures.append(f"observation_status:{observation.get('status')}:{observation.get('failures')}")

    metric = observation.get("metric") or {}
    dims = metric.get("metric_dims_m") or {}
    world = metric.get("world_m") or {}
    assert_close("obs_length_m", float(dims.get("length", -1.0)), 4.0, 0.05, failures)
    assert_close("obs_width_m", float(dims.get("width", -1.0)), 2.0, 0.05, failures)
    assert_close("obs_height_m", float(dims.get("height", -1.0)), 1.6, 1e-6, failures)
    assert_close("obs_world_north", float(world.get("north", 999.0)), 0.0, 1e-5, failures)
    assert_close("obs_world_east", float(world.get("east", 999.0)), 0.0, 1e-5, failures)
    if metric.get("metric_ground_truth") is not False:
        failures.append("observation_should_not_mark_metric_ground_truth")

    uncertainty = observation.get("uncertainty") or {}
    covariance = uncertainty.get("covariance_local_enu_m2")
    if not (isinstance(covariance, list) and len(covariance) == 3 and all(len(row) == 3 for row in covariance)):
        failures.append("observation_covariance_not_3x3")
    if float(uncertainty.get("position_sigma_m", 0.0)) <= 0.0:
        failures.append("position_sigma_m_not_positive")
    if uncertainty.get("visual_policy") != "covariance_envelope_from_metric_observation":
        failures.append(f"unexpected_visual_policy:{uncertainty.get('visual_policy')}")

    descriptor_payload = build_sppa_descriptor_payload(
        label="vehicle",
        confidence=0.84,
        max_descriptor_bytes=100000,
        **descriptor_kwargs_from_observation(observation),
    )
    descriptor_json = descriptor_payload.get("sppa_descriptor_json")
    if not descriptor_json:
        failures.append(f"descriptor_json_missing:{descriptor_payload.get('sppa_descriptor_error')}")
        descriptor = {}
    else:
        descriptor = json.loads(descriptor_json)
        desc_uncertainty = descriptor.get("uncertainty") or {}
        desc_evidence = descriptor.get("evidence") or {}
        if desc_evidence.get("observation_contract", {}).get("observation_id") != observation.get("observation_id"):
            failures.append("descriptor_missing_observation_contract_id")
        assert_close("desc_length_m", float(descriptor.get("scale", {}).get("effective_dims_m", {}).get("length", -1.0)), 4.0, 0.05, failures)
        assert_close("desc_width_m", float(descriptor.get("scale", {}).get("effective_dims_m", {}).get("width", -1.0)), 2.0, 0.05, failures)
        if desc_uncertainty.get("covariance_local_enu_m2") != covariance:
            failures.append("descriptor_covariance_not_preserved")
        if desc_uncertainty.get("visual_policy") != "covariance_envelope_from_metric_observation":
            failures.append("descriptor_visual_policy_not_preserved")
        if desc_uncertainty.get("telemetry_measured") is not False:
            failures.append("descriptor_telemetry_measured_boundary_not_preserved")

    tag_only = build_sppa_observation_contract(
        label="kangaroo",
        confidence=0.42,
        telemetry_measured=False,
        metric_ground_truth=False,
        source="tag_only_regression",
    )
    if tag_only.get("status") != "tag_or_partial_observation":
        failures.append(f"tag_only_status:{tag_only.get('status')}")
    if tag_only.get("metric", {}).get("metric_dims_m") is not None:
        failures.append("tag_only_should_not_claim_metric_dims")
    if tag_only.get("uncertainty", {}).get("visual_policy") != "tag_only_conservative_uncertainty_envelope":
        failures.append("tag_only_uncertainty_policy_wrong")

    tower_observation = build_sppa_observation_contract(
        label="tower",
        confidence=0.88,
        bbox={"x1": 490, "y1": 220, "x2": 530, "y2": 640},
        image_width=1000,
        image_height=1000,
        flight=flight,
        height_prior_m=28.0,
        height_source="declared_vertical_structure_height_prior",
        track_id="sppa-observation-tower-height-01",
        frame_id=8,
        timestamp="2026-07-04T00:00:01Z",
        telemetry_measured=False,
        metric_ground_truth=False,
        source="synthetic_vertical_structure_height_regression",
    )
    tower_payload = build_sppa_descriptor_payload(
        label="tower",
        confidence=0.88,
        max_descriptor_bytes=100000,
        **descriptor_kwargs_from_observation(tower_observation),
    )
    tower_descriptor = json.loads(tower_payload.get("sppa_descriptor_json", "{}"))
    tower_dims = tower_descriptor.get("scale", {}).get("effective_dims_m") or {}
    assert_close("tower_descriptor_height_m", float(tower_dims.get("height", -1.0)), 28.0, 1e-6, failures)

    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "observation": observation,
        "descriptor_payload_keys": sorted(descriptor_payload.keys()),
        "descriptor_id": descriptor.get("descriptor_id"),
        "descriptor_effective_dims_m": descriptor.get("scale", {}).get("effective_dims_m"),
        "descriptor_uncertainty": descriptor.get("uncertainty"),
        "tag_only_observation": tag_only,
        "tower_descriptor_effective_dims_m": tower_dims,
        "claim_boundary": (
            "Synthetic SPPA observation-contract regression. It verifies metric-evidence plumbing and "
            "covariance preservation, not real-flight calibration or detector accuracy."
        ),
    }
    (OUT_DIR / "sppa_observation_contract_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "sppa_observation_contract_summary.md").write_text(
        "\n".join(
            [
                "# SPPA Observation Contract",
                "",
                f"- Status: {report['status']}",
                f"- Observation id: {observation.get('observation_id')}",
                f"- Descriptor id: {report['descriptor_id']}",
                f"- Effective dims: {report['descriptor_effective_dims_m']}",
                f"- Tower effective dims: {report['tower_descriptor_effective_dims_m']}",
                f"- Position sigma m: {uncertainty.get('position_sigma_m')}",
                "",
                "Boundary: synthetic regression only; not real-flight validation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "failures": failures, "out_dir": str(OUT_DIR)}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
