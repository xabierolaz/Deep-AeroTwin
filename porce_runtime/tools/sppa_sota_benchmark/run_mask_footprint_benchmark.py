from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench_common import ROOT, gpu_snapshot, write_csv


GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def load_generator(generator_path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {generator_path}")
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


def axial_angle_error_deg(a: float, b: float) -> float:
    diff = abs((a - b) % 180.0)
    return min(diff, 180.0 - diff)


def rotated_corners(cx: float, cy: float, length: float, width: float, angle_deg: float) -> list[tuple[float, float]]:
    theta = math.radians(angle_deg)
    ux = (math.cos(theta), math.sin(theta))
    uy = (-math.sin(theta), math.cos(theta))
    return [
        (
            cx + sx * length * 0.5 * ux[0] + sy * width * 0.5 * uy[0],
            cy + sx * length * 0.5 * ux[1] + sy * width * 0.5 * uy[1],
        )
        for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    ]


def sample_rotated_rectangle(
    cx: float,
    cy: float,
    length: float,
    width: float,
    angle_deg: float,
    samples_per_edge: int,
    jitter_px: float,
    rng: random.Random,
) -> list[list[float]]:
    corners = rotated_corners(cx, cy, length, width, angle_deg)
    points: list[list[float]] = []
    for edge_index, start in enumerate(corners):
        end = corners[(edge_index + 1) % len(corners)]
        for sample_index in range(samples_per_edge):
            t = sample_index / float(samples_per_edge)
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            if jitter_px > 0.0:
                x += rng.gauss(0.0, jitter_px)
                y += rng.gauss(0.0, jitter_px)
            points.append([x, y])
    return points


def build_descriptor(module, label: str, mask: list[list[float]], case_id: str) -> dict[str, Any]:
    mesh = module.Mesh()
    if hasattr(module, "build_label_parametric"):
        meta = module.build_label_parametric(mesh, label)
    else:
        meta = module.build_label(mesh, label)
    return module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=0.86,
        mask=mask,
        image_width=640,
        image_height=480,
        track_id=f"mask-footprint-{case_id}",
        frame_id=case_id,
        timestamp="2026-07-02T00:00:00Z",
    )


def run_case(
    module,
    case_id: str,
    length: float,
    aspect_ratio: float,
    angle_deg: float,
    jitter_px: float,
    samples_per_edge: int,
    rng: random.Random,
) -> dict[str, Any]:
    width = length / aspect_ratio
    mask = sample_rotated_rectangle(
        cx=320.0,
        cy=240.0,
        length=length,
        width=width,
        angle_deg=angle_deg,
        samples_per_edge=samples_per_edge,
        jitter_px=jitter_px,
        rng=rng,
    )
    descriptor = build_descriptor(module, "truck", mask, case_id)
    mask_meta = descriptor["evidence"]["mask_ref_or_polygon"]
    bbox = mask_meta["bbox_px"]
    oriented = mask_meta["oriented_footprint_px"]
    scale_footprint = descriptor["scale"]["footprint_px"]
    yaw = descriptor["pose"]

    aabb_major = max(float(bbox["w"]), float(bbox["h"]))
    aabb_minor = min(float(bbox["w"]), float(bbox["h"]))
    oriented_length = float(oriented["length"])
    oriented_width = float(oriented["width"])
    yaw_deg = float(oriented["orientation_deg_axial"])

    aabb_dim_error_px = abs(aabb_major - length) + abs(aabb_minor - width)
    oriented_dim_error_px = abs(oriented_length - length) + abs(oriented_width - width)
    aabb_rel_error = aabb_dim_error_px / (length + width)
    oriented_rel_error = oriented_dim_error_px / (length + width)
    yaw_error = axial_angle_error_deg(yaw_deg, angle_deg)
    true_area = length * width
    aabb_area_ratio = (float(bbox["w"]) * float(bbox["h"])) / true_area if true_area > 0 else 0.0
    oriented_area_ratio = (oriented_length * oriented_width) / true_area if true_area > 0 else 0.0
    non_axis_aligned = axial_angle_error_deg(angle_deg, 0.0) > 1e-6

    return {
        "case_id": case_id,
        "label": "truck",
        "length_px_true": length,
        "width_px_true": width,
        "aspect_ratio": aspect_ratio,
        "angle_deg_axial_true": angle_deg,
        "jitter_px": jitter_px,
        "samples_per_edge": samples_per_edge,
        "point_count": len(mask),
        "non_axis_aligned": non_axis_aligned,
        "bbox_w_px": bbox["w"],
        "bbox_h_px": bbox["h"],
        "aabb_major_px": aabb_major,
        "aabb_minor_px": aabb_minor,
        "aabb_area_ratio": aabb_area_ratio,
        "aabb_dim_error_px": aabb_dim_error_px,
        "aabb_rel_dim_error": aabb_rel_error,
        "oriented_length_px": oriented_length,
        "oriented_width_px": oriented_width,
        "oriented_area_ratio": oriented_area_ratio,
        "oriented_dim_error_px": oriented_dim_error_px,
        "oriented_rel_dim_error": oriented_rel_error,
        "oriented_yaw_deg_axial": yaw_deg,
        "oriented_yaw_error_deg": yaw_error,
        "oriented_fill_ratio": oriented.get("fill_ratio"),
        "oriented_source": oriented.get("source"),
        "descriptor_scale_source": descriptor["scale"]["scale_source"],
        "descriptor_footprint_source": scale_footprint.get("source"),
        "pose_yaw_source": yaw.get("yaw_source"),
        "pose_yaw_ambiguous": yaw.get("yaw_ambiguous"),
        "descriptor_bytes": descriptor["cost"]["descriptor_bytes"],
        "descriptor_build_cpu_us": descriptor["cost"]["descriptor_build_cpu_us"],
        "oriented_beats_aabb": oriented_dim_error_px < aabb_dim_error_px - 1e-9,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "aabb_dim_error_px": summarize([float(row["aabb_dim_error_px"]) for row in rows]),
        "oriented_dim_error_px": summarize([float(row["oriented_dim_error_px"]) for row in rows]),
        "aabb_rel_dim_error": summarize([float(row["aabb_rel_dim_error"]) for row in rows]),
        "oriented_rel_dim_error": summarize([float(row["oriented_rel_dim_error"]) for row in rows]),
        "oriented_yaw_error_deg": summarize([float(row["oriented_yaw_error_deg"]) for row in rows]),
        "aabb_area_ratio": summarize([float(row["aabb_area_ratio"]) for row in rows]),
        "oriented_area_ratio": summarize([float(row["oriented_area_ratio"]) for row in rows]),
        "oriented_fill_ratio": summarize([float(row["oriented_fill_ratio"] or 0.0) for row in rows]),
        "descriptor_build_cpu_us": summarize([float(row["descriptor_build_cpu_us"]) for row in rows]),
        "oriented_beats_aabb_rate": (
            sum(1 for row in rows if row["oriented_beats_aabb"]) / len(rows) if rows else 0.0
        ),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Mask/PCA Oriented Footprint Benchmark",
        "",
        "This benchmark evaluates descriptor-level image-space geometry only. It uses synthetic rotated rectangles, not real UAV masks, BEV ground truth, or Unreal runtime rendering.",
        "",
        "## Setup",
        "",
        f"- Cases: {report['overall']['cases']}",
        f"- Lengths px: {report['lengths_px']}",
        f"- Aspect ratios: {report['aspect_ratios']}",
        f"- Angles deg: {report['angles_deg']}",
        f"- Jitter levels px: {report['jitter_px']}",
        f"- Samples per edge: {report['samples_per_edge']}",
        f"- GPU snapshot: `{json.dumps(report['gpu_snapshot'], sort_keys=True)}`",
        "",
        "## Main Results",
        "",
        "| Subset | n | AABB dim err P50/P95 px | Oriented dim err P50/P95 px | Yaw err P50/P95 deg | Oriented beats AABB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label in ["overall", "clean", "jittered", "clean_non_axis", "jittered_non_axis"]:
        stats = report[label]
        lines.append(
            f"| {label} | {stats['cases']} | "
            f"{stats['aabb_dim_error_px']['p50']:.3f}/{stats['aabb_dim_error_px']['p95']:.3f} | "
            f"{stats['oriented_dim_error_px']['p50']:.3f}/{stats['oriented_dim_error_px']['p95']:.3f} | "
            f"{stats['oriented_yaw_error_deg']['p50']:.3f}/{stats['oriented_yaw_error_deg']['p95']:.3f} | "
            f"{100.0 * stats['oriented_beats_aabb_rate']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundaries",
            "",
            "- AABB is expected to tie on axis-aligned rectangles; non-axis-aligned rows are the relevant diagnostic.",
            "- The result supports only oriented footprint extraction from a supplied polygon/mask.",
            "- It does not prove real-image segmentation quality, metric scale recovery, or morphology fitting.",
            "- Yaw is axial modulo pi and remains ambiguous unless velocity, heading, or explicit yaw evidence is available.",
            "",
            f"Status: `{report['status']}`",
        ]
    )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    started_utc = utc_now()
    parser = argparse.ArgumentParser(description="Benchmark SPPA image-space oriented footprint extraction on synthetic masks.")
    parser.add_argument("--generator", default=str(GENERATOR))
    parser.add_argument("--out-dir", default=str(ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_mask_footprint" / "20260702_synthetic_pca"))
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument("--samples-per-edge", type=int, default=12)
    parser.add_argument("--lengths-px", nargs="+", type=float, default=[60.0, 120.0, 180.0])
    parser.add_argument("--aspect-ratios", nargs="+", type=float, default=[1.5, 2.5, 4.0])
    parser.add_argument("--angles-deg", nargs="+", type=float, default=[0.0, 15.0, 30.0, 45.0, 60.0, 75.0])
    parser.add_argument("--jitter-px", nargs="+", type=float, default=[0.0, 0.75, 1.5])
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in out_dir.iterdir() if path.name != ".gitkeep"]
    if existing and not args.allow_existing:
        raise SystemExit(f"Output directory is not empty: {out_dir}. Use --allow-existing or choose a new output directory.")

    module = load_generator(Path(args.generator))
    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []
    case_index = 0
    for length in args.lengths_px:
        for aspect_ratio in args.aspect_ratios:
            for angle_deg in args.angles_deg:
                for jitter_px in args.jitter_px:
                    case_id = f"c{case_index:04d}_l{length:g}_ar{aspect_ratio:g}_a{angle_deg:g}_j{jitter_px:g}"
                    rows.append(
                        run_case(
                            module=module,
                            case_id=case_id,
                            length=length,
                            aspect_ratio=aspect_ratio,
                            angle_deg=angle_deg,
                            jitter_px=jitter_px,
                            samples_per_edge=args.samples_per_edge,
                            rng=rng,
                        )
                    )
                    case_index += 1

    clean = [row for row in rows if float(row["jitter_px"]) == 0.0]
    jittered = [row for row in rows if float(row["jitter_px"]) > 0.0]
    clean_non_axis = [row for row in clean if row["non_axis_aligned"]]
    jittered_non_axis = [row for row in jittered if row["non_axis_aligned"]]

    report: dict[str, Any] = {
        "status": "ok",
        "failures": [],
        "started_utc": started_utc,
        "ended_utc": utc_now(),
        "generator": str(Path(args.generator)),
        "generator_version": getattr(module, "GENERATOR_VERSION", None),
        "descriptor_schema": getattr(module, "SPPA_DESCRIPTOR_VERSION", None),
        "git_head": git_head(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "gpu_snapshot": gpu_snapshot(),
        "seed": args.seed,
        "samples_per_edge": args.samples_per_edge,
        "lengths_px": args.lengths_px,
        "aspect_ratios": args.aspect_ratios,
        "angles_deg": args.angles_deg,
        "jitter_px": args.jitter_px,
        "overall": summarize_rows(rows),
        "clean": summarize_rows(clean),
        "jittered": summarize_rows(jittered),
        "clean_non_axis": summarize_rows(clean_non_axis),
        "jittered_non_axis": summarize_rows(jittered_non_axis),
        "by_jitter": {
            str(jitter): summarize_rows([row for row in rows if float(row["jitter_px"]) == float(jitter)])
            for jitter in args.jitter_px
        },
    }

    if report["clean"]["oriented_dim_error_px"]["p95"] > 0.05:
        report["failures"].append("clean_oriented_dim_error_p95_gt_0.05px")
    if report["clean"]["oriented_yaw_error_deg"]["p95"] > 0.05:
        report["failures"].append("clean_oriented_yaw_error_p95_gt_0.05deg")
    if report["clean_non_axis"]["oriented_beats_aabb_rate"] < 0.95:
        report["failures"].append("clean_non_axis_oriented_beats_aabb_rate_lt_0.95")
    if any(row["descriptor_footprint_source"] != "mask_oriented_pca" for row in rows):
        report["failures"].append("descriptor_not_using_mask_oriented_pca")
    if any(row["pose_yaw_source"] != "mask_pca_axial" or not row["pose_yaw_ambiguous"] for row in rows):
        report["failures"].append("descriptor_yaw_not_mask_pca_axial_ambiguous")
    if report["failures"]:
        report["status"] = "failed"

    write_csv(out_dir / "mask_footprint_rows.csv", rows)
    (out_dir / "mask_footprint_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(out_dir / "mask_footprint_summary.md", report)
    (out_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "started_utc": started_utc,
                "ended_utc": utc_now(),
                "command": " ".join(sys.argv),
                "cwd": str(Path.cwd()),
                "output_dir": str(out_dir),
                "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "failures": report["failures"], "out_dir": str(out_dir)}, indent=2))
    if report["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
