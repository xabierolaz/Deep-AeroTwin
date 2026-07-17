"""Local SPPA benchmarks for the semantic proxy paper.

The benchmark is intentionally narrow. It measures the current procedural
prototype and a small footprint-fitting simulator; it does not claim end-to-end
UAV, Unreal, headset, or human-subject validity.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PAPER_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = PAPER_DIR / "benchmarks" / "results"
DEFAULT_REPO_ROOT = Path(os.environ.get("SPPA_REPO_ROOT", r"D:\Deep-AeroTwin-UE57-Test"))
DEFAULT_GENERATOR = DEFAULT_REPO_ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
CLASSES = ["biker", "bush", "car", "cow", "tractor", "tree", "truck"]


PART_GRAPHS = {
    "biker": ("cyclist", [("wheel", "torus", 2), ("frame", "cylinder", 4), ("torso", "ellipsoid", 1), ("head", "ellipsoid", 1), ("limb", "cylinder", 3)]),
    "bush": ("vegetation_blob", [("canopy", "ellipsoid", 4), ("stem", "cylinder", 1)]),
    "car": ("road_vehicle", [("body", "box", 1), ("cabin", "box", 1), ("window", "box", 2), ("wheel", "torus", 4), ("hub", "cylinder", 4)]),
    "cow": ("quadruped", [("body", "ellipsoid", 1), ("marking", "ellipsoid", 4), ("head", "ellipsoid", 2), ("horn", "cone", 2), ("leg", "cylinder", 4), ("tail", "cylinder", 1)]),
    "tractor": ("work_vehicle", [("body", "box", 3), ("cabin", "box", 1), ("window", "box", 2), ("wheel", "torus", 4), ("hub", "cylinder", 4), ("exhaust", "cylinder", 1)]),
    "tree": ("tree", [("trunk", "cylinder", 1), ("canopy", "ellipsoid", 4)]),
    "truck": ("long_vehicle", [("cargo", "box", 1), ("cab", "box", 1), ("window", "box", 1), ("wheel", "torus", 8), ("hub", "cylinder", 8)]),
}


SOTA_EXTERNAL = [
    {
        "method": "TripoSR",
        "input": "single image",
        "reported_latency_s": 0.5,
        "hardware_or_condition": "NVIDIA A100 GPU; paper/repository claim: under 0.5 s",
        "output": "textured mesh",
        "source": "Tochilkin et al. 2024 / official GitHub",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "SF3D / Stable Fast 3D",
        "input": "single image",
        "reported_latency_s": 0.5,
        "hardware_or_condition": "technical report/model card: about 0.5 s / under 1 s",
        "output": "UV-unwrapped textured mesh with materials",
        "source": "Boss et al. 2024 / Stability AI model card",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "LRM",
        "input": "single image",
        "reported_latency_s": 5.0,
        "hardware_or_condition": "paper abstract: within 5 s",
        "output": "NeRF/triplane 3D reconstruction",
        "source": "Hong et al. 2023",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "LGM",
        "input": "text or single image",
        "reported_latency_s": 5.0,
        "hardware_or_condition": "paper abstract: within 5 s",
        "output": "3D Gaussians / high-resolution 3D content",
        "source": "Tang et al. 2024",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "InstantMesh",
        "input": "single image",
        "reported_latency_s": 10.0,
        "hardware_or_condition": "paper abstract: within 10 s",
        "output": "mesh",
        "source": "Xu et al. 2024",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "Point-E",
        "input": "text prompt",
        "reported_latency_s": 60.0,
        "hardware_or_condition": "paper/OpenAI summary: 1-2 min on a single GPU",
        "output": "point cloud",
        "source": "Nichol et al. 2022",
        "comparison_status": "external reported value; not reproduced here",
    },
    {
        "method": "Magic3D",
        "input": "text prompt",
        "reported_latency_s": 2400.0,
        "hardware_or_condition": "paper/project page: about 40 min",
        "output": "textured mesh",
        "source": "Lin et al. 2023",
        "comparison_status": "external reported value; not reproduced here",
    },
]


def load_generator(path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LODMesh:
    """Mesh with the same API as the prototype, but clamped primitive tessellation."""

    LIMITS = {
        "ultralow": {"rings": 3, "segments": 6, "major_steps": 8, "minor_steps": 4},
        "low": {"rings": 4, "segments": 8, "major_steps": 10, "minor_steps": 4},
        "default": {"rings": 99, "segments": 99, "major_steps": 99, "minor_steps": 99},
    }

    def __init__(self, base_cls, profile: str):
        self._base = base_cls()
        self.profile = profile

    @property
    def vertices(self):
        return self._base.vertices

    @property
    def faces(self):
        return self._base.faces

    def add_vertex(self, *args):
        return self._base.add_vertex(*args)

    def add_face(self, *args):
        return self._base.add_face(*args)

    def box(self, *args, **kwargs):
        return self._base.box(*args, **kwargs)

    def _limit(self, key: str, value: int) -> int:
        return min(value, self.LIMITS[self.profile][key])

    def sphere(self, center, scale, material, rings=6, segments=10):
        return self._base.sphere(
            center,
            scale,
            material,
            rings=self._limit("rings", rings),
            segments=self._limit("segments", segments),
        )

    def cylinder(self, center, radius, depth, material, axis="z", segments=10):
        return self._base.cylinder(
            center,
            radius,
            depth,
            material,
            axis=axis,
            segments=self._limit("segments", segments),
        )

    def cone(self, center, radius, depth, material, axis="z", segments=10):
        return self._base.cone(
            center,
            radius,
            depth,
            material,
            axis=axis,
            segments=self._limit("segments", segments),
        )

    def torus(self, center, major, minor, material, axis="x", major_steps=14, minor_steps=6):
        return self._base.torus(
            center,
            major,
            minor,
            material,
            axis=axis,
            major_steps=self._limit("major_steps", major_steps),
            minor_steps=self._limit("minor_steps", minor_steps),
        )


def percentile(values, p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[int(idx)]
    return ordered[lo] * (hi - idx) + ordered[hi] * (idx - lo)


def summarize_ms(samples_ns):
    samples_ms = [x / 1_000_000 for x in samples_ns]
    return {
        "n": len(samples_ms),
        "mean_ms": statistics.fmean(samples_ms),
        "median_ms": statistics.median(samples_ms),
        "p95_ms": percentile(samples_ms, 0.95),
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
    }


def mesh_stats(mesh):
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    dims = {
        "length_x": max(xs) - min(xs),
        "width_y": max(ys) - min(ys),
        "height_z": max(zs) - min(zs),
    }
    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "triangles_equiv": sum(max(0, len(face[0]) - 2) for face in mesh.faces),
        "bbox_volume": dims["length_x"] * dims["width_y"] * dims["height_z"],
        **dims,
    }


def descriptor_for(label: str, stats: dict) -> bytes:
    archetype, parts = PART_GRAPHS[label]
    descriptor = {
        "label": label,
        "archetype": archetype,
        "bbox": [
            round(stats["length_x"], 3),
            round(stats["width_y"], 3),
            round(stats["height_z"], 3),
        ],
        "pose": {"x": 0, "y": 0, "z": 0, "yaw": 0, "yaw_ambiguous": True},
        "parts": [{"r": r, "g": g, "n": n} for r, g, n in parts],
        "unc": {"scale": 0.0, "semantic": 1.0},
    }
    return json.dumps(descriptor, separators=(",", ":"), sort_keys=True).encode("utf-8")


def make_mesh(gen, label: str, profile: str):
    mesh = LODMesh(gen.Mesh, profile)
    gen.BUILDERS[label](mesh)
    return mesh


def run_direct_build(gen, repeats: int, warmup: int):
    rows = []
    for profile in ["ultralow", "low", "default"]:
        for label in CLASSES:
            for _ in range(warmup):
                make_mesh(gen, label, profile)
            samples = []
            mesh = None
            for _ in range(repeats):
                start = time.perf_counter_ns()
                mesh = make_mesh(gen, label, profile)
                samples.append(time.perf_counter_ns() - start)
            assert mesh is not None
            stats = mesh_stats(mesh)
            descriptor = descriptor_for(label, stats)
            row = {
                "method": "sppa_direct_build",
                "label": label,
                "profile": profile,
                **summarize_ms(samples),
                **stats,
                "descriptor_bytes": len(descriptor),
            }
            rows.append(row)
    return rows


def run_export_build(gen, repeats: int, warmup: int):
    rows = []
    with tempfile.TemporaryDirectory(prefix="sppa_export_") as tmpdir:
        tmp = Path(tmpdir)
        for profile in ["ultralow", "low", "default"]:
            for label in CLASSES:
                for _ in range(warmup):
                    mesh = make_mesh(gen, label, profile)
                    gen.write_mtl(tmp / f"{label}_{profile}.mtl")
                    gen.write_obj(mesh, tmp / f"{label}_{profile}.obj", f"{label}_{profile}.mtl")
                samples = []
                mesh = None
                obj_path = tmp / f"{label}_{profile}.obj"
                mtl_path = tmp / f"{label}_{profile}.mtl"
                for _ in range(repeats):
                    start = time.perf_counter_ns()
                    mesh = make_mesh(gen, label, profile)
                    gen.write_mtl(mtl_path)
                    gen.write_obj(mesh, obj_path, mtl_path.name)
                    samples.append(time.perf_counter_ns() - start)
                assert mesh is not None
                stats = mesh_stats(mesh)
                row = {
                    "method": "sppa_build_plus_obj_export",
                    "label": label,
                    "profile": profile,
                    **summarize_ms(samples),
                    **stats,
                    "obj_bytes": obj_path.stat().st_size,
                    "mtl_bytes": mtl_path.stat().st_size,
                    "descriptor_bytes": len(descriptor_for(label, stats)),
                }
                rows.append(row)
    return rows


def run_subprocess(generator_path: Path, repeats: int):
    rows = []
    with tempfile.TemporaryDirectory(prefix="sppa_subprocess_") as tmpdir:
        tmp = Path(tmpdir)
        for label in CLASSES:
            samples = []
            for _ in range(repeats):
                start = time.perf_counter_ns()
                subprocess.run(
                    [sys.executable, str(generator_path), label, "--out-dir", str(tmp)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                samples.append(time.perf_counter_ns() - start)
            obj_path = tmp / f"{label}.obj"
            mtl_path = tmp / f"{label}.mtl"
            rows.append(
                {
                    "method": "sppa_subprocess_cli_plus_obj_export",
                    "label": label,
                    "profile": "default",
                    **summarize_ms(samples),
                    "obj_bytes": obj_path.stat().st_size if obj_path.exists() else 0,
                    "mtl_bytes": mtl_path.stat().st_size if mtl_path.exists() else 0,
                }
            )
    return rows


def rectangle_iou(pred_l, pred_w, target_l, target_w):
    inter = min(pred_l, target_l) * min(pred_w, target_w)
    union = pred_l * pred_w + target_l * target_w - inter
    return inter / union if union > 0 else 0.0


def volume_error(pred_l, pred_w, pred_h, target_l, target_w, target_h):
    target = target_l * target_w * target_h
    pred = pred_l * pred_w * pred_h
    return abs(pred - target) / target if target > 0 else math.nan


def run_adaptive_simulation(gen, repeats: int, noise_sigma: float):
    variants = [
        ("truck", "short_truck", 2.5, 1.05, 1.30),
        ("truck", "long_truck", 5.2, 1.15, 1.35),
        ("cow", "calf", 1.9, 0.75, 1.20),
        ("cow", "adult_cow", 3.4, 1.10, 1.70),
        ("bush", "wide_bush", 2.2, 1.7, 0.90),
        ("bush", "tall_bush", 1.1, 0.9, 1.75),
    ]
    rng = random.Random(42)
    rows = []
    for label, variant, target_l, target_w, target_h in variants:
        base = mesh_stats(make_mesh(gen, label, "default"))
        base_l, base_w, base_h = base["length_x"], base["width_y"], base["height_z"]
        samples = {"fixed_template": [], "uniform_area_scale": [], "footprint_adaptive": []}
        for _ in range(repeats):
            obs_l = max(0.05, target_l * (1.0 + rng.gauss(0.0, noise_sigma)))
            obs_w = max(0.05, target_w * (1.0 + rng.gauss(0.0, noise_sigma)))
            obs_h = max(0.05, target_h * (1.0 + rng.gauss(0.0, noise_sigma)))
            area_scale = math.sqrt((obs_l * obs_w) / (base_l * base_w))
            predictions = {
                "fixed_template": (base_l, base_w, base_h),
                "uniform_area_scale": (base_l * area_scale, base_w * area_scale, base_h * area_scale),
                "footprint_adaptive": (obs_l, obs_w, obs_h),
            }
            for method, dims in predictions.items():
                pred_l, pred_w, pred_h = dims
                samples[method].append(
                    (
                        rectangle_iou(pred_l, pred_w, target_l, target_w),
                        volume_error(pred_l, pred_w, pred_h, target_l, target_w, target_h),
                    )
                )
        for method, vals in samples.items():
            rows.append(
                {
                    "label": label,
                    "variant": variant,
                    "method": method,
                    "target_length": target_l,
                    "target_width": target_w,
                    "target_height": target_h,
                    "mean_bev_iou": statistics.fmean(v[0] for v in vals),
                    "p05_bev_iou": percentile([v[0] for v in vals], 0.05),
                    "mean_volume_error": statistics.fmean(v[1] for v in vals),
                    "p95_volume_error": percentile([v[1] for v in vals], 0.95),
                    "noise_sigma": noise_sigma,
                    "n": repeats,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    keys = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def build_latex_tables(timing_rows, adaptive_rows, path: Path):
    default_rows = [r for r in timing_rows if r["method"] == "sppa_build_plus_obj_export" and r["profile"] == "default"]
    low_rows = [r for r in timing_rows if r["method"] == "sppa_build_plus_obj_export" and r["profile"] == "ultralow"]
    by_label_low = {r["label"]: r for r in low_rows}
    lines = []
    lines.append("% Auto-generated by benchmarks/run_sppa_local_benchmarks.py")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\caption{Local SPPA prototype timing and geometry complexity. Values measure Python procedural mesh construction plus OBJ/MTL export on the benchmark machine; they are not Unreal runtime measurements.}")
    lines.append("\\label{tab:sppa-local-benchmark}")
    lines.append("\\begin{tabular}{@{}lrrrrrr@{}}")
    lines.append("\\toprule")
    lines.append("Class & Time ms & P95 ms & Vertices & Faces & Triangles & OBJ bytes \\\\")
    lines.append("\\midrule")
    for r in default_rows:
        lines.append(
            f"{r['label']} & {r['median_ms']:.3f} & {r['p95_ms']:.3f} & "
            f"{int(r['vertices'])} & {int(r['faces'])} & {int(r['triangles_equiv'])} & {int(r['obj_bytes'])} \\\\"
        )
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    lines.append("")
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\caption{Triangle budget effect of an ultra-low primitive tessellation profile. This is a local implementation path for dense-scene evaluation, not a visual-quality study.}")
    lines.append("\\label{tab:sppa-lod-benchmark}")
    lines.append("\\begin{tabular}{@{}lrrr@{}}")
    lines.append("\\toprule")
    lines.append("Class & Default triangles & Ultra-low triangles & Reduction \\\\")
    lines.append("\\midrule")
    for r in default_rows:
        low = by_label_low[r["label"]]
        reduction = 100.0 * (1.0 - low["triangles_equiv"] / r["triangles_equiv"])
        lines.append(f"{r['label']} & {int(r['triangles_equiv'])} & {int(low['triangles_equiv'])} & {reduction:.1f}\\% \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    lines.append("")
    grouped = {}
    for row in adaptive_rows:
        grouped.setdefault((row["label"], row["variant"]), {})[row["method"]] = row
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\caption{Synthetic footprint-adaptation simulation under 7\\% Gaussian measurement noise. The footprint-adaptive row uses measured dimensions and therefore tests the fitting contract, not detector accuracy.}")
    lines.append("\\label{tab:sppa-adaptive-fitting}")
    lines.append("\\begin{tabular}{@{}llrrrr@{}}")
    lines.append("\\toprule")
    lines.append("Class & Variant & Fixed IoU & Uniform IoU & Adaptive IoU & Adaptive volume err. \\\\")
    lines.append("\\midrule")
    for (label, variant), methods in grouped.items():
        fixed = methods["fixed_template"]
        uniform = methods["uniform_area_scale"]
        adaptive = methods["footprint_adaptive"]
        lines.append(
            f"{label} & {variant.replace('_', ' ')} & "
            f"{fixed['mean_bev_iou']:.3f} & {uniform['mean_bev_iou']:.3f} & "
            f"{adaptive['mean_bev_iou']:.3f} & {adaptive['mean_volume_error']:.3f} \\\\"
        )
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def system_info():
    info = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
    }
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        info["nvidia_smi"] = out
    except Exception as exc:
        info["nvidia_smi"] = f"unavailable: {exc}"
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--direct-repeats", type=int, default=300)
    parser.add_argument("--export-repeats", type=int, default=80)
    parser.add_argument("--subprocess-repeats", type=int, default=12)
    parser.add_argument("--adaptive-repeats", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--noise-sigma", type=float, default=0.07)
    args = parser.parse_args()

    if not args.generator.exists():
        raise SystemExit(f"Missing generator: {args.generator}")
    args.results_dir.mkdir(parents=True, exist_ok=True)

    gen = load_generator(args.generator)
    timing_rows = []
    timing_rows.extend(run_direct_build(gen, args.direct_repeats, args.warmup))
    timing_rows.extend(run_export_build(gen, args.export_repeats, args.warmup))
    timing_rows.extend(run_subprocess(args.generator, args.subprocess_repeats))
    adaptive_rows = run_adaptive_simulation(gen, args.adaptive_repeats, args.noise_sigma)

    write_csv(args.results_dir / "sppa_local_timing_geometry.csv", timing_rows)
    write_csv(args.results_dir / "sppa_adaptive_fitting.csv", adaptive_rows)
    write_csv(args.results_dir / "sota_external_reported_latency.csv", SOTA_EXTERNAL)
    build_latex_tables(timing_rows, adaptive_rows, args.results_dir / "sppa_benchmark_tables.tex")

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generator": str(args.generator),
        "scope": "local procedural SPPA prototype benchmark; external SOTA values are literature/model-card reported values only",
        "system": system_info(),
        "timing_rows": len(timing_rows),
        "adaptive_rows": len(adaptive_rows),
        "classes": CLASSES,
        "results": {
            "timing_geometry_csv": str(args.results_dir / "sppa_local_timing_geometry.csv"),
            "adaptive_fitting_csv": str(args.results_dir / "sppa_adaptive_fitting.csv"),
            "sota_external_csv": str(args.results_dir / "sota_external_reported_latency.csv"),
            "latex_tables": str(args.results_dir / "sppa_benchmark_tables.tex"),
        },
    }
    (args.results_dir / "sppa_benchmark_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
