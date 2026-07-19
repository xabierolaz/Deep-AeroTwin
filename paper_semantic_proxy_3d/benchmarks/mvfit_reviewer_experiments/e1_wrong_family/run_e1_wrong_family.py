"""E1 - Wrong-family token experiment (exploratory post-hoc, not confirmatory).

For every held-out test actor (n=240, clean condition) we run the frozen
SPPA-MVFit coordinate-descent fit with each of the six family tokens,
including the true one (240 x 6 = 1440 fits, deterministic, no RNG in the
fitting path). The off-diagonal cells answer the reviewer question: does a
WRONG family token hurt more than the generic graph?

Validation: the recomputed diagonal (correct token) and generic fits must
match the sealed results/test/raw_metrics.csv voxel IoU per case exactly;
the script aborts otherwise, proving protocol equivalence with the seal.

Protocol mirrored from the sealed pipeline:
  - masks: data/test/observation_masks.npy, condition index 0 = clean
  - evaluation: voxel IoU at 64^3 vs voxelize_source(private GT)
  - bootstrap: stratified by (family, stratum), mean of cell means,
    10000 resamples, seed 77157, plus null-centered two-sided p
    (same scheme as benchmark/analyze_test.py)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, FAMILIES, GtCache, bootstrap_paired, cell_key, clean_view_masks,
    f3, load_masks, load_public_cases, load_sealed_clean_ious, mv, pooled_mean,
    stratified_cells, voxel_iou, write_json, write_text, EXPLORATORY_LABEL,
)

OUT = EXPERIMENTS_ROOT / "e1_wrong_family"


def main() -> int:
    cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()
    assert len(cases) == 240 and len(sealed) == 240 * 8

    # iou_by_token[case_id][token] = voxel IoU of sppa_mvfit fit with that token
    iou_by_token: dict[str, dict[str, float]] = {}
    generic_iou: dict[str, float] = {}
    t0 = time.perf_counter()
    for case_index, case in enumerate(cases):
        top, side = clean_view_masks(masks, case_index)
        per_token: dict[str, float] = {}
        for token in FAMILIES:
            result = mv.infer_method("sppa_mvfit", token, top, side)
            occupancy = mv.voxelize_actor(result["actor"], 64)
            per_token[token] = voxel_iou(gt.voxels(case["case_id"]), occupancy)
        generic = mv.infer_method("generic_mvfit", case["family"], top, side)
        generic_iou[case["case_id"]] = voxel_iou(gt.voxels(case["case_id"]), mv.voxelize_actor(generic["actor"], 64))
        iou_by_token[case["case_id"]] = per_token
    fit_seconds = time.perf_counter() - t0

    # --- validation against the seal -------------------------------------------------
    max_diag_err = 0.0
    max_generic_err = 0.0
    for case in cases:
        cid, family = case["case_id"], case["family"]
        max_diag_err = max(max_diag_err, abs(iou_by_token[cid][family] - sealed[(cid, "sppa_mvfit")]))
        max_generic_err = max(max_generic_err, abs(generic_iou[cid] - sealed[(cid, "generic_mvfit")]))
    if max_diag_err > 1e-12 or max_generic_err > 1e-12:
        raise RuntimeError(f"seal reproduction failed: diag_err={max_diag_err} generic_err={max_generic_err}")

    # --- 6x6 matrix (rows true family, cols given token), mean over 40 cases ---------
    matrix: dict[str, dict[str, float]] = {}
    for true_family in FAMILIES:
        row: dict[str, float] = {}
        family_cases = [c for c in cases if c["family"] == true_family]
        for token in FAMILIES:
            row[token] = pooled_mean([iou_by_token[c["case_id"]][token] for c in family_cases])
        matrix[true_family] = row

    # --- per-case aggregates ----------------------------------------------------------
    correct_iou = {c["case_id"]: iou_by_token[c["case_id"]][c["family"]] for c in cases}
    wrong_mean = {
        c["case_id"]: pooled_mean([iou_by_token[c["case_id"]][t] for t in FAMILIES if t != c["family"]])
        for c in cases
    }
    wrong_best = {
        c["case_id"]: max(iou_by_token[c["case_id"]][t] for t in FAMILIES if t != c["family"])
        for c in cases
    }

    pooled = {
        "correct_token": pooled_mean(list(correct_iou.values())),
        "wrong_token_mean_over_5": pooled_mean(list(wrong_mean.values())),
        "wrong_token_best_of_5": pooled_mean(list(wrong_best.values())),
        "generic": pooled_mean(list(generic_iou.values())),
        "all_wrong_fits": pooled_mean(
            [iou_by_token[c["case_id"]][t] for c in cases for t in FAMILIES if t != c["family"]]
        ),
    }

    # paired differences per case (wrong - comparator), seal bootstrap protocol
    diff_vs_correct = bootstrap_paired(cases, {cid: wrong_mean[cid] - correct_iou[cid] for cid in correct_iou})
    diff_vs_generic = bootstrap_paired(cases, {cid: wrong_mean[cid] - generic_iou[cid] for cid in generic_iou})
    diff_correct_vs_generic = bootstrap_paired(cases, {cid: correct_iou[cid] - generic_iou[cid] for cid in generic_iou})

    # per true family: correct vs wrong-mean vs generic, with per-family paired CI
    per_family: dict[str, dict] = {}
    for family in FAMILIES:
        fcs = [c for c in cases if c["family"] == family]
        ids = [c["case_id"] for c in fcs]
        per_family[family] = {
            "n": len(ids),
            "correct": pooled_mean([correct_iou[i] for i in ids]),
            "wrong_mean": pooled_mean([wrong_mean[i] for i in ids]),
            "generic": pooled_mean([generic_iou[i] for i in ids]),
            "wrong_minus_generic": bootstrap_paired(fcs, {i: wrong_mean[i] - generic_iou[i] for i in ids}),
            "wrong_minus_correct": bootstrap_paired(fcs, {i: wrong_mean[i] - correct_iou[i] for i in ids}),
        }

    # per stratum pooled means
    per_stratum: dict[str, dict] = {}
    for stratum in ("csg_id", "implicit_ood"):
        scs = [c for c in cases if c["stratum"] == stratum]
        ids = [c["case_id"] for c in scs]
        per_stratum[stratum] = {
            "n": len(ids),
            "correct": pooled_mean([correct_iou[i] for i in ids]),
            "wrong_mean": pooled_mean([wrong_mean[i] for i in ids]),
            "generic": pooled_mean([generic_iou[i] for i in ids]),
            "wrong_minus_generic": bootstrap_paired(scs, {i: wrong_mean[i] - generic_iou[i] for i in ids}),
        }

    # cells for a stratified CI on the wrong-token global mean itself
    wrong_cells = stratified_cells(cases, wrong_mean)
    from _common import bootstrap_mean
    wrong_global = bootstrap_mean(wrong_cells)

    share_wrong_below_generic = pooled_mean(
        [1.0 if wrong_mean[c["case_id"]] < generic_iou[c["case_id"]] else 0.0 for c in cases]
    )

    # --- LaTeX: 6x6 matrix ------------------------------------------------------------
    short = {f: f.replace("_", "\\_") for f in FAMILIES}
    lines = [
        "\\begin{tabular}{@{}lrrrrrr@{}}",
        "\\toprule",
        "True family $\\downarrow$ / token $\\rightarrow$ & " + " & ".join(short[f] for f in FAMILIES) + " \\\\",
        "\\midrule",
    ]
    for true_family in FAMILIES:
        cells = []
        for token in FAMILIES:
            value = f3(matrix[true_family][token])
            cells.append(f"\\textbf{{{value}}}" if token == true_family else value)
        lines.append(f"{short[true_family]} & " + " & ".join(cells) + " \\\\")
    lines += [
        "\\midrule",
        "Wrong-token row mean & " + " & ".join(
            f3(pooled_mean([matrix[tf][t] for t in FAMILIES if t != tf])) for tf in FAMILIES
        ) + " \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "wrong_family_matrix.tex", "\n".join(lines))

    comp_lines = [
        "\\begin{tabular}{@{}lrrr@{}}",
        "\\toprule",
        "Comparison & Mean diff & CI95 low & CI95 high \\\\",
        "\\midrule",
        f"Wrong-token mean $-$ correct token & {f3(diff_vs_correct['mean_difference'])} & {f3(diff_vs_correct['ci95_low'])} & {f3(diff_vs_correct['ci95_high'])} \\\\",
        f"Wrong-token mean $-$ Generic-MVFit & {f3(diff_vs_generic['mean_difference'])} & {f3(diff_vs_generic['ci95_low'])} & {f3(diff_vs_generic['ci95_high'])} \\\\",
        f"Correct token $-$ Generic-MVFit & {f3(diff_correct_vs_generic['mean_difference'])} & {f3(diff_correct_vs_generic['ci95_low'])} & {f3(diff_correct_vs_generic['ci95_high'])} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "wrong_family_comparisons.tex", "\n".join(comp_lines))

    payload = {
        "experiment": "E1 wrong-family token",
        "label": EXPLORATORY_LABEL,
        "n_actors": len(cases),
        "fits_total": len(cases) * len(FAMILIES),
        "wrong_fits": len(cases) * (len(FAMILIES) - 1),
        "condition": "clean",
        "metric": "voxel_iou_64cubed",
        "fit_seconds_wallclock": fit_seconds,
        "seal_validation": {"max_diag_abs_err": max_diag_err, "max_generic_abs_err": max_generic_err},
        "anchors": {"sppa_mvfit_clean": 0.557, "generic_mvfit_clean": 0.367},
        "pooled_means": pooled,
        "wrong_token_stratified": wrong_global,
        "share_of_actors_wrong_below_generic": share_wrong_below_generic,
        "paired_bootstrap": {
            "wrong_minus_correct": diff_vs_correct,
            "wrong_minus_generic": diff_vs_generic,
            "correct_minus_generic": diff_correct_vs_generic,
        },
        "matrix_true_by_token": matrix,
        "per_family": per_family,
        "per_stratum": per_stratum,
        "protocol": {
            "bootstrap_resamples": 10000,
            "bootstrap_seed": 77157,
            "cells": "family x stratum, mean of cell means",
            "fits": "frozen coordinate descent via method.sppa_mvfit.infer_method, deterministic",
        },
    }
    write_json(OUT / "wrong_family_matrix.json", payload)

    print(f"fits: {len(cases) * len(FAMILIES)} in {fit_seconds:.1f}s; seal validation OK")
    print(f"pooled correct={pooled['correct_token']:.4f} wrong={pooled['wrong_token_mean_over_5']:.4f} "
          f"generic={pooled['generic']:.4f} all_wrong={pooled['all_wrong_fits']:.4f}")
    print(f"wrong-generic: {diff_vs_generic['mean_difference']:.4f} "
          f"[{diff_vs_generic['ci95_low']:.4f}, {diff_vs_generic['ci95_high']:.4f}] p={diff_vs_generic['null_centered_two_sided_p']:.4f}")
    print(f"share wrong<generic: {share_wrong_below_generic:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
