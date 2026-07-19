"""T1 - Robustness table: voxel IoU by method x observation condition.

Exploratory post-hoc analysis (not confirmatory).

Reads the sealed raw_metrics.csv (240 actors x 5 conditions x 8 methods) and
produces:
  * mean voxel IoU per method x condition (plain actor-level mean, n=240);
  * paired delta SPPA-MVFit - Generic-MVFit per condition with a 95%
    stratified bootstrap CI (family x stratum cells, 10000 resamples, seed
    77157), replicating the sealed analysis approach per condition.

Sanity check: clean delta must match the sealed confirmatory value ~0.190.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CONDITION_LABELS,
    CONDITIONS,
    METHOD_LABELS,
    METHODS,
    fmt,
    load_raw_rows,
    stratified_paired_bootstrap,
    write_json,
    write_tex,
)

OUT_DIR = Path(__file__).resolve().parent


def main() -> int:
    rows = load_raw_rows()
    assert len(rows) == 9600, f"expected 9600 sealed rows, got {len(rows)}"

    # --- means per method x condition -------------------------------------
    means: dict[str, dict[str, float]] = {method: {} for method in METHODS}
    ns: dict[str, int] = {}
    for condition in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        ns[condition] = len({row["case_id"] for row in subset})
        for method in METHODS:
            values = [row["voxel_iou"] for row in subset if row["method"] == method]
            means[method][condition] = float(np.mean(values))

    # --- paired delta per condition (stratified bootstrap) -----------------
    deltas: dict[str, dict] = {}
    for condition in CONDITIONS:
        by_case: dict[str, dict[str, dict]] = {}
        for row in rows:
            if row["condition"] == condition:
                by_case.setdefault(row["case_id"], {})[row["method"]] = row
        pairs = [
            (
                pair["sppa_mvfit"]["family"],
                pair["sppa_mvfit"]["stratum"],
                pair["sppa_mvfit"]["voxel_iou"],
                pair["generic_mvfit"]["voxel_iou"],
            )
            for pair in by_case.values()
            if "sppa_mvfit" in pair and "generic_mvfit" in pair
        ]
        deltas[condition] = stratified_paired_bootstrap(pairs, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES)

    # --- sanity check against the sealed confirmatory headline -------------
    clean_delta = deltas["clean"]["mean_difference"]
    assert abs(clean_delta - 0.190) < 0.005, f"clean delta {clean_delta} != ~0.190"
    assert abs(means["sppa_mvfit"]["clean"] - 0.5574) < 0.001, means["sppa_mvfit"]["clean"]
    assert abs(means["generic_mvfit"]["clean"] - 0.3674) < 0.001, means["generic_mvfit"]["clean"]

    # --- JSON ---------------------------------------------------------------
    payload = {
        "schema": "sppa-mvfit-posthoc-robustness-conditions-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "source": "reproducibility/sppa_mvfit/results/test/raw_metrics.csv (sealed)",
        "actors_per_condition": ns,
        "bootstrap": {
            "approach": "stratified paired bootstrap replicating benchmark/analyze_test.py",
            "stratification": "family x stratum (12 cells, equal weight per cell)",
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
        "mean_voxel_iou_by_method_condition": means,
        "paired_delta_sppa_minus_generic_by_condition": deltas,
        "sanity_check": {
            "clean_delta_expected": 0.190,
            "clean_delta_observed": clean_delta,
            "pass": bool(abs(clean_delta - 0.190) < 0.005),
        },
    }
    write_json(OUT_DIR / "robustness_conditions_table.json", payload)

    # --- main LaTeX table: focus SPPA vs Generic + paired delta -------------
    lines = [
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Condition & SPPA-MVFit & Generic-MVFit & $\Delta$ paired & 95\% CI \\",
        r"\midrule",
    ]
    for condition in CONDITIONS:
        d = deltas[condition]
        ci = f"[{fmt(d['ci95_low_percentile'])}, {fmt(d['ci95_high_percentile'])}]"
        lines.append(
            f"{CONDITION_LABELS[condition]} & {fmt(means['sppa_mvfit'][condition])} & "
            f"{fmt(means['generic_mvfit'][condition])} & {fmt(d['mean_difference'])} & {ci} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "robustness_conditions_table.tex", "\n".join(lines))

    # --- extended table: all 8 methods x 5 conditions (means only) ----------
    lines = [
        r"\begin{tabular}{@{}lrrrrr@{}}",
        r"\toprule",
        "Method & " + " & ".join(CONDITION_LABELS[c] for c in CONDITIONS) + r" \\",
        r"\midrule",
    ]
    for method in METHODS:
        lines.append(
            f"{METHOD_LABELS[method]} & " + " & ".join(fmt(means[method][c]) for c in CONDITIONS) + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "robustness_conditions_all_methods_table.tex", "\n".join(lines))

    print("clean delta:", round(clean_delta, 6), "(expected ~0.190)")
    for condition in CONDITIONS:
        d = deltas[condition]
        print(
            f"{condition:20s} SPPA {means['sppa_mvfit'][condition]:.4f}  GEN {means['generic_mvfit'][condition]:.4f}  "
            f"delta {d['mean_difference']:.4f} [{d['ci95_low_percentile']:.4f}, {d['ci95_high_percentile']:.4f}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
