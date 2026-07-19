"""Shared helpers for the mvfit reviewer experiments.

Exploratory post-hoc analyses (not confirmatory). Read-only access to the
sealed package under ``reproducibility/sppa_mvfit``; no sealed file is ever
written or modified. All configuration changes are in-memory monkeypatches.

Sealed protocol constants reused here (mirrors benchmark/analyze_test.py):
  - bootstrap resamples: 10000, seed: 77157
  - stratified cells: (family, stratum); aggregate = mean of cell means
  - evaluation: voxel IoU at 64^3 against voxelize_source GT
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
PACKAGE_ROOT = REPO_ROOT / "reproducibility" / "sppa_mvfit"
EXPERIMENTS_ROOT = REPO_ROOT / "benchmarks" / "mvfit_reviewer_experiments"
DATA_ROOT = PACKAGE_ROOT / "data" / "test"
SEALED_RESULTS = PACKAGE_ROOT / "results" / "test"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from method import sppa_mvfit as mv  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402

FAMILIES = tuple(json.loads((PACKAGE_ROOT / "protocol_config.json").read_text(encoding="utf-8"))["families"])
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 77157
CONDITIONS = ("clean", "mild_morphology", "moderate_morphology", "partial_occlusion", "mask_corruption")
CLEAN_INDEX = CONDITIONS.index("clean")

EXPLORATORY_LABEL = "exploratory post-hoc analysis (not confirmatory)"


def load_public_cases() -> list[dict]:
    return json.loads((DATA_ROOT / "public_cases.json").read_text(encoding="utf-8"))


def load_masks() -> np.ndarray:
    """Returns array of shape (240, 5, 2, 96, 96); [case, condition, view]."""
    return np.load(DATA_ROOT / "observation_masks.npy", allow_pickle=False)


def clean_view_masks(masks: np.ndarray, case_index: int) -> tuple[np.ndarray, np.ndarray]:
    return masks[case_index, CLEAN_INDEX, 0].astype(bool), masks[case_index, CLEAN_INDEX, 1].astype(bool)


def load_gt_actors() -> dict[str, dict]:
    actors: dict[str, dict] = {}
    with (DATA_ROOT / "private_source_actors.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    return actors


class GtCache:
    """Voxelized GT cache at 64^3, keyed by case_id."""

    def __init__(self) -> None:
        self._actors = load_gt_actors()
        self._voxels: dict[str, np.ndarray] = {}

    def voxels(self, case_id: str) -> np.ndarray:
        if case_id not in self._voxels:
            self._voxels[case_id] = voxelize_source(self._actors[case_id], 64)
        return self._voxels[case_id]

    def actor(self, case_id: str) -> dict:
        return self._actors[case_id]


def voxel_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 1.0
    return float(np.count_nonzero(a & b) / union)


def load_sealed_clean_ious() -> dict[tuple[str, str], float]:
    """(case_id, method) -> sealed voxel_iou for the clean condition."""
    out: dict[tuple[str, str], float] = {}
    with (SEALED_RESULTS / "raw_metrics.csv").open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["condition"] == "clean":
                out[(row["case_id"], row["method"])] = float(row["voxel_iou"])
    return out


def cell_key(case: dict) -> tuple[str, str]:
    return (case["family"], case["stratum"])


def stratified_cells(cases: list[dict], value_by_case: dict[str, float]) -> dict[tuple[str, str], list[float]]:
    cells: dict[tuple[str, str], list[float]] = {}
    for case in cases:
        cells.setdefault(cell_key(case), []).append(value_by_case[case["case_id"]])
    return cells


def bootstrap_mean(cells: dict[tuple[str, str], list[float]], seed: int = BOOTSTRAP_SEED,
                   resamples: int = BOOTSTRAP_RESAMPLES) -> dict:
    """Stratified bootstrap of the mean-of-cell-means, mirroring analyze_test.py."""
    observed = float(np.mean([np.mean(values) for values in cells.values()]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    cell_lists = list(cells.values())
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(values, size=len(values), replace=True).mean() for values in cell_lists]))
    return {
        "mean": observed,
        "ci95_low": float(np.quantile(draws, 0.025)),
        "ci95_high": float(np.quantile(draws, 0.975)),
        "resamples": resamples,
        "seed": seed,
    }


def bootstrap_paired(cases: list[dict], diff_by_case: dict[str, float], seed: int = BOOTSTRAP_SEED,
                     resamples: int = BOOTSTRAP_RESAMPLES) -> dict:
    """Stratified paired bootstrap on per-case differences (seal protocol)."""
    cells = stratified_cells(cases, diff_by_case)
    observed = float(np.mean([np.mean(values) for values in cells.values()]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    cell_lists = list(cells.values())
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(values, size=len(values), replace=True).mean() for values in cell_lists]))
    null = np.empty(resamples, dtype=np.float64)
    cell_arrays = [np.asarray(values, dtype=np.float64) for _, values in sorted(cells.items())]
    for index in range(resamples):
        null[index] = float(np.mean([rng.choice(cell - cell.mean(), size=len(cell), replace=True).mean() for cell in cell_arrays]))
    return {
        "mean_difference": observed,
        "ci95_low": float(np.quantile(draws, 0.025)),
        "ci95_high": float(np.quantile(draws, 0.975)),
        "null_centered_two_sided_p": float(np.mean(np.abs(null) >= abs(observed))),
        "resamples": resamples,
        "seed": seed,
        "actor_count": sum(len(values) for values in cell_lists),
    }


def pooled_mean(values: list[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def f3(value: float) -> str:
    return f"{value:.3f}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def tex_table(path: Path, header: str, rows: list[str]) -> None:
    body = "\n".join([header, "\\toprule", *rows[:1], "\\midrule", *rows[1:], "\\bottomrule", "\\end{tabular}", ""])
    write_text(path, body)
