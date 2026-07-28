from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench_common import ROOT, write_csv

PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from sppa_observation import build_sppa_observation_contract, descriptor_kwargs_from_observation  # noqa: E402
from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402


OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_contract" / "20260704_silhouette_projection_vs_bbox"
CAMERA = {
    "drone_yaw_deg": 0.0,
    "drone_pitch_deg": 0.0,
    "drone_roll_deg": 0.0,
    "camera_vfov_deg": 70.0,
    "mount_roll_deg": 0.0,
    "mount_pitch_deg": -90.0,
    "mount_yaw_deg": 0.0,
    "max_range_m": 250.0,
    "alt_agl_m": 30.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def axial_angle_error_deg(a: float, b: float) -> float:
    diff = abs((a - b) % 180.0)
    return min(diff, 180.0 - diff)


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


def bbox_from_points(points: list[list[float]]) -> dict[str, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}


def metric_dim_error(candidate: dict[str, Any], reference: dict[str, Any]) -> float:
    return abs(float(candidate["length_m"]) - float(reference["length_m"])) + abs(
        float(candidate["width_m"]) - float(reference["width_m"])
    )


def run_case(label: str, length_px: float, aspect_ratio: float, angle_deg: float) -> dict[str, Any]:
    width_px = length_px / aspect_ratio
    polygon = rotated_rectangle(640.0, 360.0, length_px, width_px, angle_deg)
    bbox = bbox_from_points(polygon)
    common = {
        "label": label,
        "confidence": 0.91,
        "bbox": bbox,
        "image_width": 1280,
        "image_height": 720,
        "flight": CAMERA,
        "height_prior_m": 2.7,
        "height_source": "declared_test_height_prior",
        "timestamp": "2026-07-04T00:00:00Z",
        "telemetry_measured": True,
        "metric_ground_truth": True,
    }
    bbox_obs = build_sppa_observation_contract(
        **common,
        track_id=f"{label}:bbox",
        source="synthetic_bbox_projection_ground_truth_camera",
    )
    mask_obs = build_sppa_observation_contract(
        **common,
        mask={
            "source": "synthetic_real_mask_polygon",
            "method": "rotated_rectangle_ground_truth",
            "quality_score": 1.0,
            "polygon": polygon,
        },
        track_id=f"{label}:mask",
        source="synthetic_mask_projection_ground_truth_camera",
    )
    bbox_fp = (bbox_obs.get("metric") or {}).get("footprint_m") or {}
    mask_fp = (mask_obs.get("metric") or {}).get("footprint_m") or {}
    descriptor_payload = build_sppa_descriptor_payload(
        label=label,
        confidence=0.91,
        max_descriptor_bytes=30000,
        **descriptor_kwargs_from_observation(mask_obs),
    )
    bbox_error = metric_dim_error(bbox_fp, mask_fp)
    mask_error = metric_dim_error(mask_fp, mask_fp)
    bbox_yaw = float(bbox_fp.get("orientation_deg_axial") or 0.0)
    mask_yaw = float(mask_fp.get("orientation_deg_axial") or 0.0)
    return {
        "label": label,
        "length_px": length_px,
        "width_px": width_px,
        "aspect_ratio": aspect_ratio,
        "angle_deg_axial": angle_deg,
        "bbox_length_m": bbox_fp.get("length_m"),
        "bbox_width_m": bbox_fp.get("width_m"),
        "mask_length_m": mask_fp.get("length_m"),
        "mask_width_m": mask_fp.get("width_m"),
        "bbox_dim_error_m": bbox_error,
        "mask_dim_error_m": mask_error,
        "improvement_m": bbox_error - mask_error,
        "bbox_yaw_error_deg": axial_angle_error_deg(bbox_yaw, mask_yaw),
        "mask_yaw_error_deg": axial_angle_error_deg(mask_yaw, mask_yaw),
        "bbox_metric_source": (bbox_obs.get("metric") or {}).get("metric_evidence_source"),
        "mask_metric_source": (mask_obs.get("metric") or {}).get("metric_evidence_source"),
        "descriptor_scale_source": descriptor_payload.get("sppa_scale_source"),
        "descriptor_has_mask_polygon": bool(
            json.loads(descriptor_payload.get("sppa_descriptor_json", "{}"))
            .get("evidence", {})
            .get("mask_ref_or_polygon")
        )
        if descriptor_payload.get("sppa_descriptor_json")
        else False,
        "position_sigma_bbox_m": (bbox_obs.get("uncertainty") or {}).get("position_sigma_m"),
        "position_sigma_mask_m": (mask_obs.get("uncertainty") or {}).get("position_sigma_m"),
        "yaw_sigma_bbox_deg": (bbox_obs.get("uncertainty") or {}).get("yaw_sigma_deg"),
        "yaw_sigma_mask_deg": (mask_obs.get("uncertainty") or {}).get("yaw_sigma_deg"),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    non_axis = [row for row in rows if axial_angle_error_deg(float(row["angle_deg_axial"]), 0.0) > 1e-6]
    return {
        "cases": len(rows),
        "non_axis_cases": len(non_axis),
        "bbox_dim_error_m": summarize([float(row["bbox_dim_error_m"]) for row in rows]),
        "mask_dim_error_m": summarize([float(row["mask_dim_error_m"]) for row in rows]),
        "bbox_yaw_error_deg": summarize([float(row["bbox_yaw_error_deg"]) for row in rows]),
        "mask_yaw_error_deg": summarize([float(row["mask_yaw_error_deg"]) for row in rows]),
        "improvement_m": summarize([float(row["improvement_m"]) for row in rows]),
        "non_axis_bbox_dim_error_m": summarize([float(row["bbox_dim_error_m"]) for row in non_axis]),
        "non_axis_improvement_m": summarize([float(row["improvement_m"]) for row in non_axis]),
        "mask_descriptor_preserved_rate": (
            sum(1 for row in rows if row["descriptor_has_mask_polygon"]) / float(len(rows)) if rows else 0.0
        ),
        "mask_better_rate": (
            sum(1 for row in rows if float(row["improvement_m"]) > 1e-9) / float(len(rows)) if rows else 0.0
        ),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    s = report["summary"]
    lines = [
        "# SPPA Silhouette Projection Benchmark",
        "",
        "This benchmark uses synthetic rotated mask polygons under a known nadir camera. It measures SPPA-OBS projection plumbing, not real detector-mask quality.",
        "",
        "## Summary",
        "",
        f"- Cases: {s['cases']}",
        f"- Non-axis cases: {s['non_axis_cases']}",
        f"- Bbox dim error P50/P95 m: {s['bbox_dim_error_m']['p50']:.4f}/{s['bbox_dim_error_m']['p95']:.4f}",
        f"- Mask dim error P50/P95 m: {s['mask_dim_error_m']['p50']:.4f}/{s['mask_dim_error_m']['p95']:.4f}",
        f"- Non-axis improvement P50/P95 m: {s['non_axis_improvement_m']['p50']:.4f}/{s['non_axis_improvement_m']['p95']:.4f}",
        f"- Mask descriptor preserved rate: {100.0 * s['mask_descriptor_preserved_rate']:.1f}%",
        "",
        "## Interpretation Boundary",
        "",
        "The result supports the claim that SPPA can consume silhouette evidence and avoid axis-aligned bbox inflation when such evidence exists. It does not claim that YOLOE currently provides perfect masks on the real UAV images.",
        "",
        f"Status: `{report['status']}`",
    ]
    if report["failures"]:
        lines += ["", "## Failures", ""]
        lines += [f"- {failure}" for failure in report["failures"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare SPPA-OBS bbox projection against silhouette polygon projection.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in out_dir.iterdir() if path.name != ".gitkeep"]
    if existing and not args.allow_existing:
        raise SystemExit(f"Output directory is not empty: {out_dir}. Use --allow-existing or choose a new output directory.")

    rows: list[dict[str, Any]] = []
    for label in ["truck", "cow", "biker"]:
        for length_px in [60.0, 120.0, 180.0]:
            for aspect_ratio in [1.5, 2.5, 4.0]:
                for angle_deg in [0.0, 15.0, 30.0, 45.0, 60.0, 75.0]:
                    rows.append(run_case(label, length_px, aspect_ratio, angle_deg))

    summary = summarize_rows(rows)
    failures: list[str] = []
    if summary["mask_descriptor_preserved_rate"] < 1.0:
        failures.append("mask_polygon_not_preserved_in_descriptor")
    if summary["non_axis_improvement_m"]["p50"] <= 0.0:
        failures.append("non_axis_mask_projection_did_not_improve_median")
    if summary["mask_dim_error_m"]["p95"] > 1e-9:
        failures.append("mask_projection_error_nonzero_against_own_reference")

    report = {
        "schema": "SPPA-SILHOUETTE-PROJECTION-BENCHMARK-0.1",
        "created_utc": utc_now(),
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "camera": CAMERA,
        "summary": summary,
        "claim_boundary": (
            "Synthetic mask polygons and known camera geometry are used. The benchmark validates SPPA-OBS "
            "silhouette projection and descriptor propagation, not real detector segmentation quality."
        ),
        "rows": rows,
    }
    write_csv(out_dir / "sppa_silhouette_projection_rows.csv", rows)
    (out_dir / "sppa_silhouette_projection_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(out_dir / "sppa_silhouette_projection_summary.md", report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "failures": failures,
                "out_dir": str(out_dir),
                "cases": summary["cases"],
                "non_axis_improvement_p50_m": summary["non_axis_improvement_m"]["p50"],
            },
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
