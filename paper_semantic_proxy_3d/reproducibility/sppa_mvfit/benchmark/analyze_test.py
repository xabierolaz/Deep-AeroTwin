"""Prespecified actor-level confirmatory analysis for the held-out split."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.test_authorization import require_test_authorization  # noqa: E402

RESULTS_ROOT = PACKAGE_ROOT / "results" / "test"
METHODS = ("sppa_mvfit", "generic_mvfit", "sppa_text_only", "bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull")


def read_rows() -> list[dict]:
    with (RESULTS_ROOT / "raw_metrics.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("voxel_iou", "bev_iou", "normalized_symmetric_chamfer", "inference_ms"):
            row[key] = float(row[key])
    return rows


def bootstrap(rows: list[dict], method_a: str, method_b: str, seed: int, resamples: int = 10000) -> dict:
    by_case: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row["condition"] == "clean":
            by_case[row["case_id"]][row["method"]] = row
    strata: dict[tuple[str, str], list[float]] = defaultdict(list)
    for pair in by_case.values():
        if method_a in pair and method_b in pair:
            a, b = pair[method_a], pair[method_b]
            strata[(a["family"], a["stratum"])].append(a["voxel_iou"] - b["voxel_iou"])
    observed = float(np.mean([np.mean(values) for values in strata.values()]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(values, size=len(values), replace=True).mean() for values in strata.values()]))
    # Null-centered two-sided p: resample within-cell centered differences.
    null = np.empty(resamples, dtype=np.float64)
    cell_arrays = [np.asarray(values, dtype=np.float64) for _, values in sorted(strata.items())]
    for index in range(resamples):
        null[index] = float(
            np.mean([rng.choice(cell - cell.mean(), size=len(cell), replace=True).mean() for cell in cell_arrays])
        )
    return {
        "mean_difference": observed,
        "ci95_low_percentile": float(np.quantile(draws, 0.025)),
        "ci95_high_percentile": float(np.quantile(draws, 0.975)),
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
        "actor_count": sum(len(values) for values in strata.values()),
        "stratum_counts": {"|".join(key): len(values) for key, values in sorted(strata.items())},
        "stratum_point_estimates": {"|".join(key): float(np.mean(values)) for key, values in sorted(strata.items())},
        "null_centered_two_sided_p": float(np.mean(np.abs(null) >= abs(observed))),
    }


def main() -> int:
    require_test_authorization()
    rows = read_rows()
    primary = bootstrap(rows, "sppa_mvfit", "generic_mvfit", 77157)
    secondaries = {}
    for method in ("sppa_text_only", "bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull"):
        secondaries[method] = bootstrap(rows, "sppa_mvfit", method, 77157)
    ordered = sorted(secondaries.items(), key=lambda item: item[1]["null_centered_two_sided_p"])
    holm = {}
    m = len(ordered)
    running = 0.0
    for rank, (method, result) in enumerate(ordered):
        adjusted = min(1.0, (m - rank) * result["null_centered_two_sided_p"])
        running = max(running, adjusted)
        holm[method] = running
    h1_pass = primary["ci95_low_percentile"] > 0.030
    # Aggregate equal-stratum estimates; this does not silently discard a
    # negative OOD stratum even when the aggregate passes.
    by_stratum: dict[str, list[float]] = defaultdict(list)
    for key, value in primary["stratum_point_estimates"].items():
        _, stratum = key.split("|", 1)
        by_stratum[stratum].append(value)
    ood = {key: float(np.mean(values)) for key, values in by_stratum.items()}
    sensitivity_path = RESULTS_ROOT / "resolution_sensitivity.json"
    sensitivity = json.loads(sensitivity_path.read_text(encoding="utf-8")) if sensitivity_path.exists() else {"status": "missing_required_artifact"}
    report = {
        "schema": "sppa-mvfit-confirmatory-analysis-v1",
        "provenance": "synthetic_geometry",
        "primary_endpoint": "clean_64cubed_voxel_iou_sppa_mvfit_minus_generic_mvfit",
        "primary": primary,
        "h1_superiority_margin": 0.030,
        "h1_pass": h1_pass,
        "ood_stratum_point_estimates": ood,
        "ood_nonpositive_warning": ood.get("implicit_ood", 0.0) <= 0.0,
        "secondary_bootstrap": secondaries,
        "holm_adjusted_two_sided_p": holm,
        "resolution_sensitivity": sensitivity,
        "interpretation": "A passing H1 interval is still synthetic internal evidence and does not establish real-world, geospatial, flight, or universal reconstruction validity.",
    }
    (RESULTS_ROOT / "confirmatory_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"h1_pass": h1_pass, "mean_difference": primary["mean_difference"], "ci95": [primary["ci95_low_percentile"], primary["ci95_high_percentile"]], "ood": ood}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
