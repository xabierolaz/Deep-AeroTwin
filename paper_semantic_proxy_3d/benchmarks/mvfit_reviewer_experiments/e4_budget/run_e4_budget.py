"""E4 - Optimizer budget sweep (exploratory post-hoc, not confirmatory).

The sealed fit evaluates 1 + 2*5*len(STEP_FRACTIONS) = 31 candidates with
STEP_FRACTIONS = (0.2, 0.1, 0.05). We sweep the evaluation budget by patching
the module-level STEP_FRACTIONS IN MEMORY (no sealed file is touched):

  budget 11 -> (0.2,)
  budget 21 -> (0.2, 0.1)
  budget 31 -> (0.2, 0.1, 0.05)                      [sealed configuration]
  budget 61 -> (0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625)  [same scheme, finer
               geometric tail: keep halving the step fraction]

fit_graph reads STEP_FRACTIONS and PROTOCOL["fit_candidate_budget"] at call
time, so setting both (and restoring them afterwards in a finally block) is
the complete, documented monkeypatch. The budget-31 arm is validated
bit-exactly against results/test/raw_metrics.csv before any sweep number is
trusted.

n = 240 actors, clean condition, sppa_mvfit with the correct family token,
voxel IoU at 64^3. Wall-clock ms per fit via time.perf_counter.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, GtCache, bootstrap_paired, clean_view_masks, f3, load_masks,
    load_public_cases, load_sealed_clean_ious, mv, pooled_mean, voxel_iou,
    write_json, write_text, EXPLORATORY_LABEL,
)

OUT = EXPERIMENTS_ROOT / "e4_budget"

BUDGETS: dict[int, tuple[float, ...]] = {
    11: (0.2,),
    21: (0.2, 0.1),
    31: (0.2, 0.1, 0.05),
    61: (0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625),
}


def run_budget(cases, masks, gt, fractions: tuple[float, ...]) -> tuple[dict[str, float], list[float]]:
    original_fractions = mv.STEP_FRACTIONS
    original_budget = mv.PROTOCOL["fit_candidate_budget"]
    mv.STEP_FRACTIONS = tuple(float(v) for v in fractions)
    mv.PROTOCOL["fit_candidate_budget"] = 1 + 2 * len(mv.PARAMETER_NAMES) * len(mv.STEP_FRACTIONS)
    try:
        ious: dict[str, float] = {}
        ms: list[float] = []
        for case_index, case in enumerate(cases):
            top, side = clean_view_masks(masks, case_index)
            start = time.perf_counter()
            result = mv.infer_method("sppa_mvfit", case["family"], top, side)
            elapsed = (time.perf_counter() - start) * 1000.0
            if result["evaluations"] != mv.PROTOCOL["fit_candidate_budget"]:
                raise AssertionError("budget drift")
            ms.append(elapsed)
            ious[case["case_id"]] = voxel_iou(gt.voxels(case["case_id"]), mv.voxelize_actor(result["actor"], 64))
        return ious, ms
    finally:
        mv.STEP_FRACTIONS = original_fractions
        mv.PROTOCOL["fit_candidate_budget"] = original_budget


def main() -> int:
    cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()

    per_budget_iou: dict[int, dict[str, float]] = {}
    per_budget_ms: dict[int, list[float]] = {}
    for budget, fractions in BUDGETS.items():
        ious, ms = run_budget(cases, masks, gt, fractions)
        per_budget_iou[budget] = ious
        per_budget_ms[budget] = ms

    # sealed configuration must reproduce the sealed numbers exactly
    max_err = max(abs(per_budget_iou[31][c["case_id"]] - sealed[(c["case_id"], "sppa_mvfit")]) for c in cases)
    if max_err > 1e-12:
        raise RuntimeError(f"budget-31 arm drifts from seal: {max_err}")

    summary: dict[int, dict] = {}
    for budget in BUDGETS:
        values = list(per_budget_iou[budget].values())
        times = np.asarray(per_budget_ms[budget])
        summary[budget] = {
            "mean_iou": pooled_mean(values),
            "mean_ms": float(times.mean()),
            "median_ms": float(np.median(times)),
            "p95_ms": float(np.quantile(times, 0.95)),
        }
    paired_vs_31 = {
        f"{b}_minus_31": bootstrap_paired(
            cases, {c["case_id"]: per_budget_iou[b][c["case_id"]] - per_budget_iou[31][c["case_id"]] for c in cases})
        for b in BUDGETS if b != 31
    }
    per_stratum: dict[str, dict] = {}
    for stratum in ("csg_id", "implicit_ood"):
        ids = [c["case_id"] for c in cases if c["stratum"] == stratum]
        per_stratum[stratum] = {str(b): pooled_mean([per_budget_iou[b][i] for i in ids]) for b in BUDGETS}

    lines = [
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "Candidate budget & Mean IoU & Mean ms & Median ms & p95 ms \\\\",
        "\\midrule",
    ]
    for budget in BUDGETS:
        s = summary[budget]
        tag = " (sealed)" if budget == 31 else ""
        lines.append(f"{budget}{tag} & {f3(s['mean_iou'])} & {f3(s['mean_ms'])} & {f3(s['median_ms'])} & {f3(s['p95_ms'])} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    write_text(OUT / "budget_sweep_table.tex", "\n".join(lines))

    payload = {
        "experiment": "E4 optimizer budget sweep",
        "label": EXPLORATORY_LABEL,
        "n_actors": len(cases),
        "condition": "clean",
        "metric": "voxel_iou_64cubed",
        "seal_validation": {"budget31_max_abs_err": max_err},
        "monkeypatch": {
            "what": "method.sppa_mvfit.STEP_FRACTIONS and PROTOCOL['fit_candidate_budget'] set in memory, restored in finally",
            "budgets_to_step_fractions": {str(b): list(f) for b, f in BUDGETS.items()},
        },
        "summary_per_budget": {str(b): summary[b] for b in BUDGETS},
        "paired_bootstrap_vs_31": paired_vs_31,
        "per_stratum_mean_iou": per_stratum,
        "protocol": {"bootstrap_resamples": 10000, "bootstrap_seed": 77157},
    }
    write_json(OUT / "budget_sweep.json", payload)

    for budget in BUDGETS:
        s = summary[budget]
        print(f"budget {budget:3d}: IoU {s['mean_iou']:.4f}  mean {s['mean_ms']:.2f} ms  p95 {s['p95_ms']:.2f} ms")
    for name, diff in paired_vs_31.items():
        print(f"{name}: {diff['mean_difference']:.4f} [{diff['ci95_low']:.4f}, {diff['ci95_high']:.4f}] p={diff['null_centered_two_sided_p']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
