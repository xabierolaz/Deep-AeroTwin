from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench_common import ROOT, gpu_snapshot, write_csv


GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_generator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def cargo_length(parts: list[dict[str, Any]]) -> float:
    cargos = [
        part
        for part in parts
        if part.get("primitive") == "box" and part.get("material") == "vehicle_neutral_body_prior"
    ]
    return float(cargos[0]["scale"][0]) if len(cargos) == 1 else 0.0


def tire_count(parts: list[dict[str, Any]]) -> int:
    return sum(1 for part in parts if part.get("role") == "vehicle_tire")


def run_case(module: Any, length_px: float, width_px: float, angle_deg: float, meters_per_pixel: float, reps: int) -> dict[str, Any]:
    mask = rotated_rectangle(320.0, 240.0, length_px, width_px, angle_deg)
    metric_scale = {
        "meters_per_pixel": meters_per_pixel,
        "source": "synthetic_ground_sample_distance",
        "confidence": 1.0,
    }
    true_dims = {
        "length": length_px * meters_per_pixel,
        "width": width_px * meters_per_pixel,
        "height": 2.7,
    }
    build_times_us: list[float] = []
    mesh = None
    meta = None
    descriptor = None
    for _ in range(reps):
        mesh = module.Mesh()
        start = time.perf_counter_ns()
        meta = module.build_label_observed(
            mesh,
            "truck",
            mask=mask,
            metric_scale=metric_scale,
            height_m=true_dims["height"],
        )
        build_times_us.append((time.perf_counter_ns() - start) / 1000.0)
    assert mesh is not None and meta is not None
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.91,
        mask=mask,
        dims_m=meta.get("effective_dims_m"),
        image_width=640,
        image_height=480,
        track_id=f"mask-shape-{int(length_px)}-{int(width_px)}-{int(angle_deg)}",
        frame_id=f"{int(angle_deg)}",
        timestamp="2026-07-03T00:00:00Z",
    )

    no_calib_mesh = module.Mesh()
    no_calib_meta = module.build_label_observed(no_calib_mesh, "truck", mask=mask, height_m=true_dims["height"])
    dims = meta.get("effective_dims_m") or {}
    length_error_m = abs(float(dims.get("length", 0.0)) - true_dims["length"])
    width_error_m = abs(float(dims.get("width", 0.0)) - true_dims["width"])
    return {
        "label": "truck",
        "length_px": length_px,
        "width_px": width_px,
        "angle_deg_axial": angle_deg,
        "meters_per_pixel": meters_per_pixel,
        "target_length_m": true_dims["length"],
        "target_width_m": true_dims["width"],
        "effective_length_m": float(dims.get("length", 0.0)),
        "effective_width_m": float(dims.get("width", 0.0)),
        "length_error_m": length_error_m,
        "width_error_m": width_error_m,
        "sum_dim_error_m": length_error_m + width_error_m,
        "shape_policy": meta.get("shape_policy"),
        "metric_dims_source": meta.get("metric_dims_source"),
        "descriptor_scale_source": descriptor.get("scale", {}).get("scale_source"),
        "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
        "descriptor_build_cpu_us": descriptor.get("cost", {}).get("descriptor_build_cpu_us"),
        "build_cpu_us_p50": pct(build_times_us, 50),
        "build_cpu_us_p95": pct(build_times_us, 95),
        "triangles": descriptor.get("mesh", {}).get("triangles"),
        "cargo_length_m": cargo_length(mesh.parts),
        "tire_count": tire_count(mesh.parts),
        "no_calibration_shape_policy": no_calib_meta.get("shape_policy"),
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    overall = report["overall"]
    lines = [
        "# Calibrated Mask-To-Shape Benchmark",
        "",
        "Synthetic calibrated-mask benchmark. This verifies only the deterministic SPPA contract path from image-space footprint plus supplied ground scale to parametric geometry. It is not real UAV-mask validation.",
        "",
        "## Setup",
        "",
        f"- Cases: {overall['cases']}",
        f"- Lengths px: {report['lengths_px']}",
        f"- Widths px: {report['widths_px']}",
        f"- Angles deg: {report['angles_deg']}",
        f"- Meters per pixel: {report['meters_per_pixel']}",
        f"- Repetitions per case: {report['reps']}",
        f"- GPU snapshot: `{json.dumps(report['gpu_snapshot'], sort_keys=True)}`",
        "",
        "## Results",
        "",
        "| Metric | P50 | P95 | Max |",
        "|---|---:|---:|---:|",
        f"| Sum length/width error (m) | {overall['sum_dim_error_m']['p50']:.6f} | {overall['sum_dim_error_m']['p95']:.6f} | {overall['sum_dim_error_m']['max']:.6f} |",
        f"| Build CPU (us) | {overall['build_cpu_us_p50']['p50']:.3f} | {overall['build_cpu_us_p95']['p95']:.3f} | {overall['build_cpu_us_p95']['max']:.3f} |",
        f"| Descriptor bytes | {overall['descriptor_bytes']['p50']:.0f} | {overall['descriptor_bytes']['p95']:.0f} | {overall['descriptor_bytes']['max']:.0f} |",
        "",
        "## Boundary",
        "",
        "- The control path without metric image scale remains `template_prior`; mask polygons alone are not treated as metric shape evidence.",
        "- Height is supplied explicitly in this benchmark; if absent, SPPA records that height came from an archetype prior.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark calibrated mask footprint to parametric SPPA geometry.")
    parser.add_argument("--out-dir", default="experiments/sppa_calibrated_mask_shape/20260703_synthetic")
    parser.add_argument("--reps", type=int, default=50)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()

    out_dir = ROOT / args.out_dir if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.allow_existing:
        raise SystemExit(f"Output directory is not empty: {out_dir}; pass --allow-existing to append/overwrite")
    out_dir.mkdir(parents=True, exist_ok=True)
    module = load_generator(GENERATOR)

    lengths_px = [100.0, 140.0, 180.0, 220.0]
    widths_px = [36.0, 48.0]
    angles_deg = [0.0, 17.5, 35.0, 62.5]
    meters_per_pixel_values = [0.04, 0.06]

    rows: list[dict[str, Any]] = []
    for length_px in lengths_px:
        for width_px in widths_px:
            for angle_deg in angles_deg:
                for meters_per_pixel in meters_per_pixel_values:
                    rows.append(run_case(module, length_px, width_px, angle_deg, meters_per_pixel, args.reps))

    report = {
        "created_utc": utc_now(),
        "generator": str(GENERATOR),
        "lengths_px": lengths_px,
        "widths_px": widths_px,
        "angles_deg": angles_deg,
        "meters_per_pixel": meters_per_pixel_values,
        "reps": args.reps,
        "gpu_snapshot": gpu_snapshot(),
        "overall": {
            "cases": len(rows),
            "sum_dim_error_m": summarize([float(row["sum_dim_error_m"]) for row in rows]),
            "build_cpu_us_p50": summarize([float(row["build_cpu_us_p50"]) for row in rows]),
            "build_cpu_us_p95": summarize([float(row["build_cpu_us_p95"]) for row in rows]),
            "descriptor_bytes": summarize([float(row["descriptor_bytes"]) for row in rows]),
            "descriptor_build_cpu_us": summarize([float(row["descriptor_build_cpu_us"]) for row in rows]),
        },
        "all_calibrated_sources": sorted({str(row["descriptor_scale_source"]) for row in rows}),
        "no_calibration_policies": sorted({str(row["no_calibration_shape_policy"]) for row in rows}),
    }
    write_csv(out_dir / "calibrated_mask_shape_rows.csv", rows)
    (out_dir / "calibrated_mask_shape_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary(out_dir / "calibrated_mask_shape_summary.md", report)
    (out_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "created_utc": report["created_utc"],
                "command": "tools/sppa_sota_benchmark/run_calibrated_mask_shape_benchmark.py",
                "outputs": [
                    "calibrated_mask_shape_rows.csv",
                    "calibrated_mask_shape_summary.json",
                    "calibrated_mask_shape_summary.md",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(out_dir)


if __name__ == "__main__":
    main()
