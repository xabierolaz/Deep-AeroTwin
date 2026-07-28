from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from sppa_observation import build_sppa_observation_contract, descriptor_kwargs_from_observation  # noqa: E402
from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402

GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
DEFAULT_OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_contract" / "20260704_metric_observation_vs_prior"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_generator() -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rotated_rectangle(cx: float, cy: float, length_px: float, width_px: float, angle_deg: float) -> list[list[float]]:
    theta = math.radians(angle_deg)
    ux = (math.cos(theta), math.sin(theta))
    uy = (-math.sin(theta), math.cos(theta))
    return [
        [
            cx + sx * length_px * 0.5 * ux[0] + sy * width_px * 0.5 * uy[0],
            cy + sx * length_px * 0.5 * ux[1] + sy * width_px * 0.5 * uy[1],
        ]
        for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    ]


def dim_error(dims: dict[str, Any], target: dict[str, float]) -> dict[str, float]:
    length_error = abs(float(dims.get("length", 0.0)) - float(target["length"]))
    width_error = abs(float(dims.get("width", 0.0)) - float(target["width"]))
    height_error = abs(float(dims.get("height", 0.0)) - float(target["height"]))
    return {
        "length_error_m": length_error,
        "width_error_m": width_error,
        "height_error_m": height_error,
        "sum_dim_error_m": length_error + width_error + height_error,
    }


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil((p / 100.0) * len(ordered))) - 1))
    return float(ordered[idx])


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0, "min": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "n": len(values),
        "min": min(values),
        "mean": statistics.fmean(values),
        "p50": pct(values, 50),
        "p95": pct(values, 95),
        "max": max(values),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_v1_prior_dims(module: Any, label: str) -> tuple[dict[str, float], str, str]:
    mesh = module.Mesh()
    meta = module.build_label(mesh, label)
    archetype = str(meta.get("archetype") or "unknown")
    dims = module.archetype_default_dims(label, archetype)
    return dims, archetype, str(meta.get("shape_policy") or "template_prior")


def run_case(module: Any, case: dict[str, Any]) -> dict[str, Any]:
    meters_per_pixel = 0.02
    target = case["target_dims_m"]
    mask = rotated_rectangle(
        500.0,
        500.0,
        target["length"] / meters_per_pixel,
        target["width"] / meters_per_pixel,
        float(case["angle_deg"]),
    )
    flight = {
        "drone_yaw_deg": float(case.get("drone_yaw_deg", 0.0)),
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
        label=case["label"],
        confidence=float(case["confidence"]),
        mask=mask,
        image_width=1000,
        image_height=1000,
        flight=flight,
        height_prior_m=target["height"],
        height_source="synthetic_case_height_prior_for_controlled_benchmark",
        track_id=f"sppa-{case['case_id']}",
        frame_id=case["case_id"],
        timestamp="2026-07-04T00:00:00Z",
        telemetry_measured=False,
        metric_ground_truth=False,
        source="synthetic_metric_observation_benchmark",
    )
    descriptor_payload = build_sppa_descriptor_payload(
        label=case["label"],
        confidence=float(case["confidence"]),
        max_descriptor_bytes=100000,
        **descriptor_kwargs_from_observation(observation),
    )
    descriptor = json.loads(descriptor_payload["sppa_descriptor_json"])
    v1_dims, archetype, v1_shape_policy = build_v1_prior_dims(module, case["label"])
    v2_dims = descriptor.get("scale", {}).get("effective_dims_m") or {}
    v1_error = dim_error(v1_dims, target)
    v2_error = dim_error(v2_dims, target)
    improvement = v1_error["sum_dim_error_m"] - v2_error["sum_dim_error_m"]
    uncertainty = descriptor.get("uncertainty") or {}
    return {
        "case_id": case["case_id"],
        "label": case["label"],
        "archetype": archetype,
        "target_length_m": target["length"],
        "target_width_m": target["width"],
        "target_height_m": target["height"],
        "angle_deg": case["angle_deg"],
        "v1_shape_policy": v1_shape_policy,
        "v1_length_m": v1_dims["length"],
        "v1_width_m": v1_dims["width"],
        "v1_height_m": v1_dims["height"],
        "v1_sum_dim_error_m": v1_error["sum_dim_error_m"],
        "v2_shape_policy": descriptor.get("scale", {}).get("shape_policy"),
        "v2_scale_source": descriptor.get("scale", {}).get("scale_source"),
        "v2_length_m": v2_dims.get("length"),
        "v2_width_m": v2_dims.get("width"),
        "v2_height_m": v2_dims.get("height"),
        "v2_sum_dim_error_m": v2_error["sum_dim_error_m"],
        "dim_error_improvement_m": improvement,
        "v2_better_than_v1": improvement > 1e-6,
        "descriptor_build_cpu_us": descriptor.get("cost", {}).get("descriptor_build_cpu_us"),
        "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
        "triangles": descriptor.get("mesh", {}).get("triangles"),
        "observation_status": observation.get("status"),
        "observation_id": observation.get("observation_id"),
        "position_sigma_m": uncertainty.get("position_sigma_m"),
        "scale_sigma_m": uncertainty.get("scale_sigma_m"),
        "yaw_sigma_deg": uncertainty.get("yaw_sigma_deg"),
        "uncertainty_visual_policy": uncertainty.get("visual_policy"),
        "claim_boundary": "synthetic metric observation; scenario-relative, not measured flight ground truth",
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    overall = report["overall"]
    lines = [
        "# SPPA Observation Contract Benchmark",
        "",
        "Controlled synthetic benchmark comparing the SPPA semantic prior against the SPPA metric-observation path. This is not real-flight ground truth; it verifies whether the contract can consume metric evidence and improve scale alignment without neural mesh generation.",
        "",
        "## Summary",
        "",
        f"- Cases: {overall['cases']}",
        f"- v1 sum-dimension error P50/P95: {overall['v1_sum_dim_error_m']['p50']:.3f}/{overall['v1_sum_dim_error_m']['p95']:.3f} m",
        f"- v2 sum-dimension error P50/P95: {overall['v2_sum_dim_error_m']['p50']:.3f}/{overall['v2_sum_dim_error_m']['p95']:.3f} m",
        f"- Mean improvement: {overall['dim_error_improvement_m']['mean']:.3f} m",
        f"- v2 better rate: {100.0 * overall['v2_better_rate']:.1f}%",
        f"- Descriptor build P50/P95: {overall['descriptor_build_cpu_us']['p50']:.1f}/{overall['descriptor_build_cpu_us']['p95']:.1f} us",
        "",
        "## Cases",
        "",
        "| Case | Label | Target L/W/H | v1 err | v2 err | Improve | v2 source |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['label']}` | "
            f"{row['target_length_m']:.2f}/{row['target_width_m']:.2f}/{row['target_height_m']:.2f} | "
            f"{row['v1_sum_dim_error_m']:.3f} | {row['v2_sum_dim_error_m']:.3f} | "
            f"{row['dim_error_improvement_m']:.3f} | `{row['v2_scale_source']}` |"
        )
    lines += [
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare SPPA semantic priors with SPPA metric-observation descriptors.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    if out_dir.exists() and any(out_dir.iterdir()) and not args.allow_existing:
        raise SystemExit(f"Output directory is not empty: {out_dir}; pass --allow-existing to overwrite.")
    out_dir.mkdir(parents=True, exist_ok=True)
    module = load_generator()
    cases = [
        {"case_id": "cyclist_long_view", "label": "cyclist", "confidence": 0.82, "angle_deg": 22.5, "target_dims_m": {"length": 2.05, "width": 0.72, "height": 1.85}},
        {"case_id": "tower_tall_proxy", "label": "electric pylon", "confidence": 0.88, "angle_deg": 40.0, "target_dims_m": {"length": 2.60, "width": 1.70, "height": 18.0}},
        {"case_id": "tractor_wide", "label": "agricultural vehicle", "confidence": 0.78, "angle_deg": 32.0, "target_dims_m": {"length": 5.60, "width": 2.55, "height": 2.70}},
        {"case_id": "truck_trailer_long", "label": "truck", "confidence": 0.80, "angle_deg": 15.0, "target_dims_m": {"length": 8.40, "width": 2.45, "height": 3.20}},
        {"case_id": "cow_close", "label": "cow", "confidence": 0.86, "angle_deg": 65.0, "target_dims_m": {"length": 2.85, "width": 0.95, "height": 1.55}},
        {"case_id": "car_small", "label": "car", "confidence": 0.91, "angle_deg": 10.0, "target_dims_m": {"length": 3.70, "width": 1.65, "height": 1.45}},
    ]
    rows = [run_case(module, case) for case in cases]
    report = {
        "schema": "SPPA-CONTRACT-BENCHMARK-0.1",
        "created_utc": utc_now(),
        "generator": str(GENERATOR),
        "cases": cases,
        "overall": {
            "cases": len(rows),
            "v1_sum_dim_error_m": summarize([float(row["v1_sum_dim_error_m"]) for row in rows]),
            "v2_sum_dim_error_m": summarize([float(row["v2_sum_dim_error_m"]) for row in rows]),
            "dim_error_improvement_m": summarize([float(row["dim_error_improvement_m"]) for row in rows]),
            "descriptor_build_cpu_us": summarize([float(row["descriptor_build_cpu_us"]) for row in rows]),
            "descriptor_bytes": summarize([float(row["descriptor_bytes"]) for row in rows]),
            "triangles": summarize([float(row["triangles"]) for row in rows]),
            "v2_better_rate": sum(1 for row in rows if row["v2_better_than_v1"]) / float(len(rows) or 1),
        },
        "rows": rows,
        "claim_boundary": (
            "This benchmark uses synthetic metric masks generated from declared dimensions under a nadir camera model. "
            "It supports the SPPA contract claim that metric evidence can improve scale alignment over a semantic "
            "template prior. It does not prove real detector mask quality, real telemetry calibration, or visual SOTA."
        ),
    }
    write_csv(out_dir / "sppa_contract_rows.csv", rows)
    (out_dir / "sppa_contract_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(out_dir / "sppa_contract_summary.md", report)
    print(json.dumps({"out_dir": str(out_dir), "overall": report["overall"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
