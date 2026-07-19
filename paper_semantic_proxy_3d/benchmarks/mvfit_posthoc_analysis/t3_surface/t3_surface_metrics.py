"""T3 - Surface metrics: normalized symmetric Chamfer and F-score@tau.

Exploratory post-hoc analysis (not confirmatory).

(a) normalized_symmetric_chamfer aggregated from the sealed raw_metrics.csv:
    mean per method x condition (n = 240), plus clean paired delta
    method - SPPA-MVFit with stratified bootstrap CI (positive = SPPA has the
    lower/better Chamfer). Chamfer is normalized by the world diagonal, so
    values are unit-free fractions of the world extent.

(b) Voxel-surface F-score @ tau = 1.5 voxels (grid-index units), computed from
    the sealed 64^3 prediction grids (sealed_predictions.bin) against the
    released private GT re-voxelized with the sealed voxelizer. Surface masks
    and EDT reuse the sealed benchmark.metrics implementation.
    Methods: sppa_mvfit, generic_mvfit, nonsemantic_visual_hull,
    sppa_text_only; condition clean; n = 240 per method.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from scipy import ndimage  # noqa: E402

import common  # noqa: E402,F401  (sets sys.path for the sealed package)
from benchmark.metrics import surface_mask  # noqa: E402
from common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CONDITION_LABELS,
    CONDITIONS,
    METHOD_LABELS,
    METHODS,
    fmt,
    load_private_actors,
    load_raw_rows,
    load_sealed_records,
    read_sealed_prediction,
    stratified_paired_bootstrap,
    write_json,
    write_tex,
)
from source.source_generators import voxelize_source  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
TAU_VOXELS = 1.5
FSCORE_METHODS = ("sppa_mvfit", "generic_mvfit", "nonsemantic_visual_hull", "sppa_text_only")


def fscore_surface(gt: np.ndarray, pred: np.ndarray, tau: float) -> float:
    gt_surface = surface_mask(gt)
    pred_surface = surface_mask(pred)
    if not np.any(gt_surface) and not np.any(pred_surface):
        return 1.0
    if not np.any(gt_surface) or not np.any(pred_surface):
        return 0.0
    distance_to_gt = ndimage.distance_transform_edt(~gt_surface)
    distance_to_pred = ndimage.distance_transform_edt(~pred_surface)
    precision = float(np.mean(distance_to_gt[pred_surface] <= tau))
    recall = float(np.mean(distance_to_pred[gt_surface] <= tau))
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def main() -> int:
    rows = load_raw_rows()

    # ---------------- (a) Chamfer from sealed CSV --------------------------
    chamfer_means: dict[str, dict[str, float]] = {method: {} for method in METHODS}
    for condition in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        for method in METHODS:
            values = [row["normalized_symmetric_chamfer"] for row in subset if row["method"] == method]
            chamfer_means[method][condition] = float(np.mean(values))

    chamfer_delta: dict[str, dict] = {}
    by_case: dict[str, dict[str, dict]] = {}
    for row in rows:
        if row["condition"] == "clean":
            by_case.setdefault(row["case_id"], {})[row["method"]] = row
    for method in METHODS:
        if method == "sppa_mvfit":
            continue
        pairs = [
            (
                pair[method]["family"],
                pair[method]["stratum"],
                pair[method]["normalized_symmetric_chamfer"],
                pair["sppa_mvfit"]["normalized_symmetric_chamfer"],
            )
            for pair in by_case.values()
            if method in pair and "sppa_mvfit" in pair
        ]
        chamfer_delta[method] = stratified_paired_bootstrap(pairs, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES)

    # ---------------- (b) F-score from sealed grids ------------------------
    actors = load_private_actors()
    gt_cache: dict[str, np.ndarray] = {}
    fscore_values: dict[str, dict[str, float]] = {method: {} for method in FSCORE_METHODS}
    case_meta: dict[str, dict] = {}
    for record in load_sealed_records():
        if record["condition"] != "clean" or record["method"] not in FSCORE_METHODS:
            continue
        case_id = record["case_id"]
        if case_id not in gt_cache:
            gt_cache[case_id] = voxelize_source(actors[case_id], 64)
            case_meta[case_id] = {"family": record["family"], "stratum": record["stratum"]}
        pred = read_sealed_prediction(record)
        fscore_values[record["method"]][case_id] = fscore_surface(gt_cache[case_id], pred, TAU_VOXELS)
    assert all(len(values) == 240 for values in fscore_values.values())

    fscore_means = {method: float(np.mean(list(values.values()))) for method, values in fscore_values.items()}
    fscore_delta: dict[str, dict] = {}
    for method in FSCORE_METHODS:
        if method == "sppa_mvfit":
            continue
        pairs = [
            (
                case_meta[case_id]["family"],
                case_meta[case_id]["stratum"],
                fscore_values[method][case_id],
                fscore_values["sppa_mvfit"][case_id],
            )
            for case_id in fscore_values[method]
        ]
        fscore_delta[method] = stratified_paired_bootstrap(pairs, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES)

    payload = {
        "schema": "sppa-mvfit-posthoc-surface-metrics-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "chamfer": {
            "source": "sealed raw_metrics.csv",
            "normalization": "fraction of world diagonal (sealed benchmark/metrics.py)",
            "mean_by_method_condition": chamfer_means,
            "clean_paired_delta_method_minus_sppa": chamfer_delta,
            "delta_sign": "positive = SPPA-MVFit has lower (better) Chamfer",
        },
        "fscore": {
            "tau_voxels": TAU_VOXELS,
            "tau_note": "voxel grid-index units; 64^3 world cells are 0.15 x 0.10 x 0.10 world units",
            "source": "sealed_predictions.bin + released private GT re-voxelized (sealed code)",
            "condition": "clean",
            "actors_per_method": 240,
            "mean_by_method": fscore_means,
            "clean_paired_delta_method_minus_sppa": fscore_delta,
            "delta_sign": "negative = method below SPPA-MVFit (SPPA better)",
        },
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "stratification": "family x stratum cells"},
    }
    write_json(OUT_DIR / "surface_metrics.json", payload)

    # ---------------- LaTeX: chamfer table ---------------------------------
    lines = [
        r"\begin{tabular}{@{}lrrrrrrr@{}}",
        r"\toprule",
        "Method & " + " & ".join(CONDITION_LABELS[c] for c in CONDITIONS) + r" & $\Delta$ vs SPPA & 95\% CI \\",
        r"\midrule",
    ]
    for method in METHODS:
        row = f"{METHOD_LABELS[method]} & " + " & ".join(fmt(chamfer_means[method][c]) for c in CONDITIONS)
        if method == "sppa_mvfit":
            row += r" & --- & --- \\"
        else:
            d = chamfer_delta[method]
            row += f" & {fmt(d['mean_difference'])} & [{fmt(d['ci95_low_percentile'])}, {fmt(d['ci95_high_percentile'])}] \\\\"
        lines.append(row)
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "chamfer_conditions_table.tex", "\n".join(lines))

    # ---------------- LaTeX: F-score table ---------------------------------
    lines = [
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Method & F-score$@1.5$ vox & $\Delta$ vs SPPA & 95\% CI \\",
        r"\midrule",
    ]
    for method in FSCORE_METHODS:
        if method == "sppa_mvfit":
            lines.append(f"{METHOD_LABELS[method]} & {fmt(fscore_means[method])} & --- & --- \\\\")
        else:
            d = fscore_delta[method]
            lines.append(
                f"{METHOD_LABELS[method]} & {fmt(fscore_means[method])} & {fmt(d['mean_difference'])} & "
                f"[{fmt(d['ci95_low_percentile'])}, {fmt(d['ci95_high_percentile'])}] \\\\"
            )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "surface_metrics_table.tex", "\n".join(lines))

    print("Chamfer clean means:", {m: round(chamfer_means[m]['clean'], 5) for m in METHODS})
    print("Chamfer clean delta vs SPPA:")
    for method, d in chamfer_delta.items():
        print(f"  {method:24s} {d['mean_difference']:.5f} [{d['ci95_low_percentile']:.5f}, {d['ci95_high_percentile']:.5f}]")
    print("F-score@1.5 means:", {m: round(v, 4) for m, v in fscore_means.items()})
    for method, d in fscore_delta.items():
        print(f"  {method:24s} {d['mean_difference']:.5f} [{d['ci95_low_percentile']:.5f}, {d['ci95_high_percentile']:.5f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
