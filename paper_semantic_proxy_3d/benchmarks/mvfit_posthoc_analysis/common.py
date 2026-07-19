"""Shared utilities for the SPPA-MVFit post-hoc re-analysis.

All analyses are exploratory post-hoc analyses (not confirmatory). They read
only the sealed artifacts and never write inside ``reproducibility/sppa_mvfit``.

The stratified paired bootstrap replicates ``benchmark/analyze_test.py`` from
the sealed package: per-actor paired differences are grouped into
(family, stratum) cells, the point estimate is the equal-weight mean of cell
means, and each bootstrap draw resamples actors within each cell with
replacement. Sealed seed: 77157 (protocol_config.json ``bootstrap_seed``).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SEAL_ROOT = REPO_ROOT / "reproducibility" / "sppa_mvfit"
RESULTS_TEST = SEAL_ROOT / "results" / "test"
DATA_TEST = SEAL_ROOT / "data" / "test"
OUT_ROOT = REPO_ROOT / "benchmarks" / "mvfit_posthoc_analysis"

# Import the sealed modules read-only (importing is safe: no writes).
if str(SEAL_ROOT) not in sys.path:
    sys.path.insert(0, str(SEAL_ROOT))

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
CONDITIONS = ("clean", "mild_morphology", "moderate_morphology", "partial_occlusion", "mask_corruption")
FAMILIES = ("compact_vehicle", "articulated_vehicle", "quadruped", "branching_vertical", "lattice_tower", "rider_cycle")
STRATA = ("csg_id", "implicit_ood")

BOOTSTRAP_SEED = 77157  # protocol_config.json bootstrap_seed (documented, fixed)
BOOTSTRAP_RESAMPLES = 10000  # protocol_config.json bootstrap_resamples

METHOD_LABELS = {
    "sppa_mvfit": "SPPA-MVFit",
    "generic_mvfit": "Generic-MVFit",
    "sppa_text_only": "SPPA text-only",
    "bbox": "Axis-aligned box",
    "ellipsoid": "Ellipsoid",
    "capsule": "Capsule",
    "billboard": "Billboard",
    "nonsemantic_visual_hull": "Visual hull",
}
CONDITION_LABELS = {
    "clean": "Clean",
    "mild_morphology": "Mild morph.",
    "moderate_morphology": "Moderate morph.",
    "partial_occlusion": "Partial occl.",
    "mask_corruption": "Mask corrupt.",
}

# Voxel cell sizes of the 64^3 evaluation grid (protocol world extents).
VOXEL_SIZE = {"x": 9.6 / 64.0, "y": 6.4 / 64.0, "z": 6.4 / 64.0}  # 0.15, 0.10, 0.10


def load_raw_rows() -> list[dict]:
    """Load the sealed raw_metrics.csv (9600 rows) with typed numerics."""
    with (RESULTS_TEST / "raw_metrics.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    numeric = (
        "inference_ms", "voxel_iou", "bev_iou", "volume_error",
        "gt_outside_prediction", "prediction_outside_gt",
        "normalized_symmetric_chamfer", "heldout_silhouette_iou", "objective",
    )
    for row in rows:
        for key in numeric:
            row[key] = float(row[key]) if row[key] not in ("", None) else float("nan")
        for key in ("evaluations", "primitive_count", "triangle_equiv", "descriptor_bytes"):
            row[key] = int(row[key]) if row[key] not in ("", None) else -1
    return rows


def stratified_paired_bootstrap(
    pairs: list[tuple[str, str, float, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
    exclude_families: tuple[str, ...] = (),
) -> dict:
    """Stratified paired bootstrap on (family, stratum, value_a, value_b) tuples.

    Point estimate: equal-weight mean over (family, stratum) cells of the
    within-cell mean paired difference a - b, exactly as the sealed analysis.
    """
    cells: dict[tuple[str, str], list[float]] = {}
    for family, stratum, a, b in pairs:
        if family in exclude_families:
            continue
        cells.setdefault((family, stratum), []).append(a - b)
    if not cells:
        raise ValueError("no cells left after filtering")
    cell_diffs = {key: np.asarray(values, dtype=np.float64) for key, values in sorted(cells.items())}
    observed = float(np.mean([values.mean() for values in cell_diffs.values()]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    arrays = list(cell_diffs.values())
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(cell, size=len(cell), replace=True).mean() for cell in arrays]))
    return {
        "mean_difference": observed,
        "ci95_low_percentile": float(np.quantile(draws, 0.025)),
        "ci95_high_percentile": float(np.quantile(draws, 0.975)),
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
        "actor_count": int(sum(len(values) for values in cell_diffs.values())),
        "cell_counts": {"|".join(key): len(values) for key, values in cell_diffs.items()},
        "cell_point_estimates": {"|".join(key): float(values.mean()) for key, values in cell_diffs.items()},
    }


def stratified_mean_bootstrap(
    values: list[tuple[str, str, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict:
    """Stratified bootstrap CI for a single mean (equal weight per cell).

    Cells are balanced (20 actors each), so the equal-cell mean equals the
    plain actor-level mean.
    """
    cells: dict[tuple[str, str], list[float]] = {}
    for family, stratum, value in values:
        cells.setdefault((family, stratum), []).append(value)
    cell_arrays = {key: np.asarray(v, dtype=np.float64) for key, v in sorted(cells.items())}
    observed = float(np.mean([arr.mean() for arr in cell_arrays.values()]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    arrays = list(cell_arrays.values())
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(cell, size=len(cell), replace=True).mean() for cell in arrays]))
    return {
        "mean": observed,
        "ci95_low_percentile": float(np.quantile(draws, 0.025)),
        "ci95_high_percentile": float(np.quantile(draws, 0.975)),
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
        "actor_count": int(sum(len(v) for v in cell_arrays.values())),
    }


def fmt(value: float, digits: int = 3) -> str:
    """Fixed 3-decimal formatting for LaTeX tables ($-$ for negatives)."""
    if value < 0:
        return f"$-${abs(value):.{digits}f}"
    return f"{value:.{digits}f}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_tex(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_private_actors() -> dict:
    """Load the released post-seal private GT source actors (read-only)."""
    actors: dict[str, dict] = {}
    with (DATA_TEST / "private_source_actors.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    return actors


def load_sealed_records():
    """Iterate sealed_method_outputs.jsonl lazily (read-only)."""
    with (RESULTS_TEST / "sealed_method_outputs.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def read_sealed_prediction(record: dict) -> np.ndarray:
    """Read one 64^3 packed prediction grid from sealed_predictions.bin."""
    with (RESULTS_TEST / "sealed_predictions.bin").open("rb") as binary:
        binary.seek(int(record["offset"]))
        packed = binary.read(int(record["length"]))
    return np.unpackbits(np.frombuffer(packed, dtype=np.uint8), bitorder="little")[: 64 ** 3].reshape((64, 64, 64)).astype(bool)
