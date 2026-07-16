from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = PACKAGE_ROOT.parents[1]


def _discover_repo_root() -> Path:
    # The paper path is intentionally a Windows junction whose resolved parent
    # is outside the checkout. Prefer the caller's checkout and only then walk
    # the resolved package parents.
    for start in (Path.cwd().resolve(), PACKAGE_ROOT):
        for candidate in (start, *start.parents):
            if (candidate / ".git").exists():
                return candidate
    raise RuntimeError("cannot locate repository root")


REPO_ROOT = _discover_repo_root()
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.metrics import evaluate_geometry  # noqa: E402
from method.sppa_mvfit import (  # noqa: E402
    GRAPHS,
    WORLD,
    baseline_occupancy,
    complexity_metadata,
    infer_method,
    voxelize_actor,
)
from source.source_generators import (  # noqa: E402
    FAMILIES,
    generate_source_actor,
    render_source_masks,
    validate_actor_inside_world,
    voxelize_source,
)

CONFIG = json.loads((PACKAGE_ROOT / "protocol_config.json").read_text(encoding="utf-8"))
CONDITIONS = tuple(CONFIG["conditions"])
METHODS = (
    "sppa_mvfit",
    "generic_mvfit",
    "sppa_text_only",
    "bbox",
    "ellipsoid",
    "capsule",
    "billboard",
    "nonsemantic_visual_hull",
)
METHOD_ACTOR = {"sppa_mvfit", "generic_mvfit", "sppa_text_only"}
DATA_DEV = PACKAGE_ROOT / "data" / "development"
RESULTS_DEV = PACKAGE_ROOT / "results" / "development"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def case_seed(base_seed: int, *labels: str) -> int:
    payload = f"{base_seed}|" + "|".join(labels)
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")


def _largest_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(np.argmax(sizes))


def _morph(mask: np.ndarray, seed: int, iterations: int) -> np.ndarray:
    if seed % 2:
        return ndimage.binary_dilation(mask, structure=np.ones((3, 3), dtype=bool), iterations=iterations)
    return ndimage.binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), iterations=iterations, border_value=0)


def _partial_occlusion(mask: np.ndarray, seed: int) -> np.ndarray:
    result = mask.copy()
    points = np.argwhere(mask)
    if not len(points):
        return result
    rng = np.random.default_rng(seed)
    lo = points.min(axis=0)
    hi = points.max(axis=0) + 1
    bbox_h, bbox_w = max(1, int(hi[0] - lo[0])), max(1, int(hi[1] - lo[1]))
    target_area = max(1, int(round(0.12 * bbox_h * bbox_w)))
    rect_h = max(1, min(bbox_h, int(round(math.sqrt(target_area * bbox_h / max(bbox_w, 1))))))
    rect_w = max(1, min(bbox_w, int(math.ceil(target_area / rect_h))))
    occupied_point = points[int(rng.integers(0, len(points)))]
    x0 = int(np.clip(occupied_point[0] - rect_h // 2, lo[0], max(lo[0], hi[0] - rect_h)))
    y0 = int(np.clip(occupied_point[1] - rect_w // 2, lo[1], max(lo[1], hi[1] - rect_w)))
    result[x0 : x0 + rect_h, y0 : y0 + rect_w] = False
    return result


def _mask_corruption(mask: np.ndarray, seed: int) -> np.ndarray:
    result = mask.copy()
    rng = np.random.default_rng(seed)
    component = _largest_component(mask)
    points = np.argwhere(component)
    if not len(points):
        return result
    lo, hi = points.min(axis=0), points.max(axis=0) + 1
    candidates = np.array([(i, j) for i in range(int(lo[0]), int(hi[0])) for j in range(int(lo[1]), int(hi[1]))], dtype=int)
    flip_count = max(1, int(round(0.005 * len(candidates))))
    selected = candidates[rng.choice(len(candidates), size=min(flip_count, len(candidates)), replace=False)]
    result[selected[:, 0], selected[:, 1]] = ~result[selected[:, 0], selected[:, 1]]
    outside = np.argwhere(~ndimage.binary_dilation(component, iterations=4))
    if len(outside):
        center = outside[int(rng.integers(0, len(outside)))]
        xx, yy = np.ogrid[: mask.shape[0], : mask.shape[1]]
        result |= (xx - int(center[0])) ** 2 + (yy - int(center[1])) ** 2 <= 4
    return result


def make_conditions(clean_top: np.ndarray, clean_side: np.ndarray, seed: int) -> np.ndarray:
    masks = np.zeros((len(CONDITIONS), 2, clean_top.shape[0], clean_top.shape[1]), dtype=bool)
    masks[0, 0], masks[0, 1] = clean_top, clean_side
    for view_index, clean in enumerate((clean_top, clean_side)):
        masks[1, view_index] = _morph(clean, case_seed(seed, "mild", str(view_index)), 1)
        masks[2, view_index] = _morph(clean, case_seed(seed, "moderate", str(view_index)), 2)
        masks[3, view_index] = _partial_occlusion(clean, case_seed(seed, "occlusion", str(view_index)))
        masks[4, view_index] = _mask_corruption(clean, case_seed(seed, "corruption", str(view_index)))
    return masks


def development_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seed = int(CONFIG["development"]["seed_start"])
    count_per_family = int(CONFIG["development"]["actors_per_family_per_stratum"])
    for family in FAMILIES:
        for family_index in range(count_per_family):
            case_id = f"dev-csg_id-{family}-{family_index:03d}"
            cases.append({"case_id": case_id, "family": family, "stratum": "csg_id", "seed": seed})
            seed += 1
    if len(cases) != int(CONFIG["development"]["actor_count"]):
        raise AssertionError("development count drift")
    return cases


def generate_development() -> None:
    DATA_DEV.mkdir(parents=True, exist_ok=True)
    cases = development_cases()
    masks = np.zeros((len(cases), len(CONDITIONS), 2, int(CONFIG["observation_resolution"]), int(CONFIG["observation_resolution"])), dtype=bool)
    manifest_path = DATA_DEV / "source_actors.jsonl"
    manifest_rows: list[dict[str, Any]] = []
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        for case_index, case in enumerate(cases):
            actor = generate_source_actor(case["family"], case["stratum"], case["seed"])
            if not validate_actor_inside_world(actor):
                raise RuntimeError(f"source touches evaluation boundary: {case['case_id']}")
            top, side = render_source_masks(actor, int(CONFIG["source_projection_resolution"]), int(CONFIG["observation_resolution"]))
            masks[case_index] = make_conditions(top, side, int(case["seed"]))
            gt = voxelize_source(actor, int(CONFIG["evaluation_resolution"]))
            actor_hash = sha256_bytes(canonical_json(actor).encode("utf-8"))
            gt_hash = sha256_bytes(np.packbits(gt, bitorder="little").tobytes())
            mask_hashes = {
                condition: sha256_bytes(np.packbits(masks[case_index, condition_index], bitorder="little").tobytes())
                for condition_index, condition in enumerate(CONDITIONS)
            }
            row = {
                **case,
                "schema_version": "SPPA-MVFIT-DATASET-ROW-1.0",
                "provenance": "synthetic_geometry",
                "actor": actor,
                "actor_sha256": actor_hash,
                "gt_64_packbits_sha256": gt_hash,
                "mask_sha256": mask_hashes,
            }
            handle.write(canonical_json(row) + "\n")
            manifest_rows.append(row)
    np.save(DATA_DEV / "observation_masks.npy", masks, allow_pickle=False)
    case_ids = [row["case_id"] for row in manifest_rows]
    (DATA_DEV / "case_ids.json").write_text(json.dumps(case_ids, indent=2) + "\n", encoding="utf-8")
    dataset_manifest = {
        "schema_version": "SPPA-MVFIT-DATASET-MANIFEST-1.0",
        "provenance": "synthetic_geometry",
        "split": "development",
        "case_count": len(cases),
        "conditions": list(CONDITIONS),
        "files": {
            "source_actors.jsonl": sha256_file(manifest_path),
            "observation_masks.npy": sha256_file(DATA_DEV / "observation_masks.npy"),
            "case_ids.json": sha256_file(DATA_DEV / "case_ids.json"),
        },
        "array_content_sha256": sha256_bytes(np.packbits(masks, bitorder="little").tobytes()),
    }
    (DATA_DEV / "dataset_manifest.json").write_text(json.dumps(dataset_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(dataset_manifest, indent=2))


def load_development() -> tuple[list[dict[str, Any]], np.ndarray]:
    manifest_path = DATA_DEV / "source_actors.jsonl"
    masks_path = DATA_DEV / "observation_masks.npy"
    if not manifest_path.exists() or not masks_path.exists():
        raise FileNotFoundError("development data missing; run generate-development")
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    masks = np.load(masks_path, allow_pickle=False)
    if masks.shape[0] != len(rows):
        raise ValueError("manifest/mask count mismatch")
    return rows, masks


def _method_prediction(method: str, family: str, top: np.ndarray, side: np.ndarray, resolution: int) -> tuple[np.ndarray, dict[str, Any]]:
    if method in METHOD_ACTOR:
        result = infer_method(method, family, top, side)
        occupancy = voxelize_actor(result["actor"], resolution)
        metadata = {key: value for key, value in result.items() if key not in {"trace", "actor"}}
        metadata.update(complexity_metadata(method, actor=result["actor"]))
        return occupancy, metadata
    occupancy, result = baseline_occupancy(method, top, side, resolution)
    actor = result.get("actor")
    result.update(complexity_metadata(method, actor=actor, occupancy=None if actor is not None else occupancy))
    return occupancy, result


def environment_snapshot() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for name in ("numpy", "scipy", "cv2", "PIL", "matplotlib"):
        try:
            module = __import__(name)
            packages[name] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:
            packages[name] = f"unavailable:{type(exc).__name__}"
    snapshot = {
        "python": sys.version,
        "executable_name": Path(sys.executable).name,
        "executable_sha256": sha256_file(Path(sys.executable)),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "packages": packages,
    }
    try:
        snapshot["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception as exc:
        snapshot["git_head"] = f"unavailable:{type(exc).__name__}"
    return snapshot


def run_development() -> None:
    rows, masks = load_development()
    RESULTS_DEV.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DEV / "raw_metrics.csv"
    fieldnames = [
        "case_id", "family", "stratum", "seed", "condition", "method", "status", "exception",
        "voxel_iou", "bev_iou", "normalized_symmetric_chamfer", "heldout_silhouette_iou",
        "volume_error", "gt_outside_prediction", "prediction_outside_gt", "inference_ms",
        "primitive_count", "triangle_equiv", "descriptor_bytes", "evaluations", "objective",
        "top_fit_iou", "side_fit_iou", "theta_json",
    ]
    world_diagonal = math.sqrt(sum((WORLD[axis][1] - WORLD[axis][0]) ** 2 for axis in ("x", "y", "z")))
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        total = len(rows) * len(CONDITIONS) * len(METHODS)
        completed = 0
        for case_index, source_row in enumerate(rows):
            actor = source_row["actor"]
            gt = voxelize_source(actor, int(CONFIG["evaluation_resolution"]))
            current_gt_hash = sha256_bytes(np.packbits(gt, bitorder="little").tobytes())
            if current_gt_hash != source_row["gt_64_packbits_sha256"]:
                raise RuntimeError(f"GT hash drift: {source_row['case_id']}")
            for condition_index, condition in enumerate(CONDITIONS):
                top, side = masks[case_index, condition_index, 0], masks[case_index, condition_index, 1]
                for method in METHODS:
                    row = {
                        "case_id": source_row["case_id"],
                        "family": source_row["family"],
                        "stratum": source_row["stratum"],
                        "seed": source_row["seed"],
                        "condition": condition,
                        "method": method,
                        "status": "pass",
                        "exception": "",
                    }
                    start = time.perf_counter_ns()
                    try:
                        pred, metadata = _method_prediction(method, source_row["family"], top, side, int(CONFIG["evaluation_resolution"]))
                        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
                        metrics = evaluate_geometry(gt, pred, condition == "clean", world_diagonal)
                        row.update(metrics)
                        row.update(
                            {
                                "inference_ms": elapsed_ms,
                                "primitive_count": metadata.get("primitive_count", ""),
                                "triangle_equiv": metadata.get("triangle_equiv", ""),
                                "descriptor_bytes": metadata.get("descriptor_bytes", ""),
                                "evaluations": metadata.get("evaluations", 0),
                                "objective": metadata.get("objective", ""),
                                "top_fit_iou": metadata.get("top_iou", ""),
                                "side_fit_iou": metadata.get("side_iou", ""),
                                "theta_json": canonical_json(metadata.get("theta")) if metadata.get("theta") is not None else "",
                            }
                        )
                    except Exception as exc:
                        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
                        row.update(
                            {
                                "status": "exception",
                                "exception": f"{type(exc).__name__}:{exc}",
                                "voxel_iou": 0.0,
                                "bev_iou": 0.0,
                                "normalized_symmetric_chamfer": 1.0 if condition == "clean" else math.nan,
                                "heldout_silhouette_iou": 0.0 if condition == "clean" else math.nan,
                                "volume_error": 1.0,
                                "gt_outside_prediction": 1.0,
                                "prediction_outside_gt": 1.0,
                                "inference_ms": elapsed_ms,
                                "primitive_count": "",
                                "triangle_equiv": "",
                                "descriptor_bytes": "",
                                "evaluations": 0,
                                "objective": "",
                                "top_fit_iou": "",
                                "side_fit_iou": "",
                                "theta_json": "",
                            }
                        )
                    writer.writerow(row)
                    completed += 1
            if (case_index + 1) % 6 == 0:
                print(f"development progress {case_index + 1}/{len(rows)} actors; {completed}/{total} rows", flush=True)
    run_manifest = {
        "schema_version": "SPPA-MVFIT-RUN-MANIFEST-1.0",
        "split": "development",
        "provenance": "synthetic_geometry",
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": environment_snapshot(),
        "input_manifest_sha256": sha256_file(DATA_DEV / "dataset_manifest.json"),
        "raw_metrics_sha256": sha256_file(output_path),
        "methods": list(METHODS),
        "conditions": list(CONDITIONS),
        "row_count": len(rows) * len(CONDITIONS) * len(METHODS),
    }
    (RESULTS_DEV / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(run_manifest, indent=2))


def _read_raw_metrics() -> list[dict[str, Any]]:
    path = RESULTS_DEV / "raw_metrics.csv"
    if not path.exists():
        raise FileNotFoundError("raw metrics missing; run run-development")
    rows: list[dict[str, Any]] = []
    numeric = {
        "seed", "voxel_iou", "bev_iou", "normalized_symmetric_chamfer", "heldout_silhouette_iou",
        "volume_error", "gt_outside_prediction", "prediction_outside_gt", "inference_ms",
        "primitive_count", "triangle_equiv", "descriptor_bytes", "evaluations", "objective", "top_fit_iou", "side_fit_iou",
    }
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, Any] = dict(raw)
            for key in numeric:
                value = raw.get(key, "")
                row[key] = float(value) if value not in {"", "nan", "NaN"} else math.nan
            rows.append(row)
    return rows


def _stratified_bootstrap_difference(case_rows: list[dict[str, Any]], method_a: str, method_b: str, resamples: int, seed: int) -> dict[str, float]:
    by_case: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in case_rows:
        by_case[row["case_id"]][row["method"]] = row
    strata: dict[tuple[str, str], list[float]] = defaultdict(list)
    for methods in by_case.values():
        if method_a not in methods or method_b not in methods:
            continue
        a, b = methods[method_a], methods[method_b]
        strata[(a["family"], a["stratum"])].append(float(a["voxel_iou"]) - float(b["voxel_iou"]))
    observed = float(np.mean([np.mean(values) for values in strata.values()]))
    rng = np.random.default_rng(seed)
    bootstrap = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        stratum_means = []
        for values in strata.values():
            array = np.asarray(values, dtype=np.float64)
            sample = rng.choice(array, size=len(array), replace=True)
            stratum_means.append(float(sample.mean()))
        bootstrap[index] = float(np.mean(stratum_means))
    return {
        "mean_difference": observed,
        "ci95_low_percentile": float(np.quantile(bootstrap, 0.025)),
        "ci95_high_percentile": float(np.quantile(bootstrap, 0.975)),
        "resamples": int(resamples),
        "seed": int(seed),
        "case_count": int(sum(len(values) for values in strata.values())),
    }


def analyze_development() -> None:
    rows = _read_raw_metrics()
    clean = [row for row in rows if row["condition"] == "clean"]
    method_summary: dict[str, dict[str, Any]] = {}
    for method in METHODS:
        selected = [row for row in clean if row["method"] == method]
        method_summary[method] = {
            "n": len(selected),
            "exceptions": sum(row["status"] != "pass" for row in selected),
            "mean_voxel_iou": float(np.mean([row["voxel_iou"] for row in selected])),
            "median_voxel_iou": float(np.median([row["voxel_iou"] for row in selected])),
            "mean_bev_iou": float(np.mean([row["bev_iou"] for row in selected])),
            "mean_chamfer": float(np.mean([row["normalized_symmetric_chamfer"] for row in selected])),
            "mean_heldout_silhouette_iou": float(np.mean([row["heldout_silhouette_iou"] for row in selected])),
            "median_single_call_ms": float(np.median([row["inference_ms"] for row in selected])),
        }
    paired = _stratified_bootstrap_difference(
        clean,
        "sppa_mvfit",
        "generic_mvfit",
        int(CONFIG["bootstrap_resamples"]),
        int(CONFIG["bootstrap_seed"]),
    )
    robustness: dict[str, dict[str, float]] = {}
    for method in METHODS:
        by_condition: dict[str, float] = {}
        for condition in CONDITIONS:
            selected = [row["voxel_iou"] for row in rows if row["method"] == method and row["condition"] == condition]
            by_condition[condition] = float(np.mean(selected))
        robustness[method] = by_condition
    summary = {
        "schema_version": "SPPA-MVFIT-DEVELOPMENT-SUMMARY-1.0",
        "provenance": "synthetic_geometry",
        "split": "development_only_not_confirmatory",
        "method_summary_clean": method_summary,
        "paired_sppa_minus_generic_clean": paired,
        "robustness_mean_voxel_iou": robustness,
        "primary_test_executed": False,
        "interpretation_boundary": "Development results may debug fixed implementation only. They do not pass or fail the held-out H1 gate.",
    }
    RESULTS_DEV.mkdir(parents=True, exist_ok=True)
    (RESULTS_DEV / "development_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SPPA-MVFit development summary",
        "",
        "Synthetic development split only. This is not the held-out confirmatory result.",
        "",
        "| Method | n | Mean voxel IoU | Median voxel IoU | Mean BEV IoU | Median single call ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        item = method_summary[method]
        lines.append(f"| {method} | {item['n']} | {item['mean_voxel_iou']:.4f} | {item['median_voxel_iou']:.4f} | {item['mean_bev_iou']:.4f} | {item['median_single_call_ms']:.3f} |")
    lines.extend(
        [
            "",
            "Development paired SPPA-MVFit minus generic-MVFit clean voxel IoU:",
            f"mean {paired['mean_difference']:.4f}, percentile 95% CI [{paired['ci95_low_percentile']:.4f}, {paired['ci95_high_percentile']:.4f}], n={paired['case_count']}.",
            "",
            "This interval must not be reported as H1 evidence. No test seed, test GT, or test result exists in this package snapshot.",
        ]
    )
    (RESULTS_DEV / "development_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="SPPA-MVFit synthetic benchmark")
    parser.add_argument("command", choices=("generate-development", "run-development", "analyze-development"))
    args = parser.parse_args()
    if args.command == "generate-development":
        generate_development()
    elif args.command == "run-development":
        run_development()
    else:
        analyze_development()


if __name__ == "__main__":
    main()
