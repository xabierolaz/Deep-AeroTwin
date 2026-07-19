"""T5 - Drop-one-family robustness of the headline delta.

Exploratory post-hoc analysis (not confirmatory).

Recomputes the headline paired delta (SPPA-MVFit - Generic-MVFit, clean voxel
IoU) excluding each of the 6 families in turn. As in the sealed protocol, the
estimate is the equal-weight mean over the remaining family x stratum cells
(10 cells after dropping one family), with a stratified bootstrap 95% CI
(10 000 resamples within cells, seed 77157). A pre-verified expectation:
excluding rider_cycle gives ~0.152.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    FAMILIES,
    fmt,
    load_raw_rows,
    stratified_paired_bootstrap,
    write_json,
    write_tex,
)

OUT_DIR = Path(__file__).resolve().parent


def main() -> int:
    rows = load_raw_rows()
    by_case: dict[str, dict[str, dict]] = {}
    for row in rows:
        if row["condition"] == "clean":
            by_case.setdefault(row["case_id"], {})[row["method"]] = row
    pairs_all = [
        (
            pair["sppa_mvfit"]["family"],
            pair["sppa_mvfit"]["stratum"],
            pair["sppa_mvfit"]["voxel_iou"],
            pair["generic_mvfit"]["voxel_iou"],
        )
        for pair in by_case.values()
        if "sppa_mvfit" in pair and "generic_mvfit" in pair
    ]
    assert len(pairs_all) == 240

    results: dict[str, dict] = {}
    results["all_families"] = stratified_paired_bootstrap(pairs_all, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES)
    for family in FAMILIES:
        results[f"drop_{family}"] = stratified_paired_bootstrap(
            pairs_all, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES, exclude_families=(family,)
        )

    # sanity: protocol aggregate must reproduce the sealed headline
    assert abs(results["all_families"]["mean_difference"] - 0.190) < 0.005
    assert abs(results["drop_rider_cycle"]["mean_difference"] - 0.152) < 0.01, results["drop_rider_cycle"]["mean_difference"]

    payload = {
        "schema": "sppa-mvfit-posthoc-drop-one-family-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "endpoint": "clean voxel IoU paired delta SPPA-MVFit - Generic-MVFit",
        "aggregation": "equal-weight mean over family x stratum cells (10 cells after each drop; 12 for all)",
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "results": results,
        "sanity": {
            "all_families_expected": 0.190,
            "drop_rider_cycle_expected": 0.152,
            "pass": bool(abs(results["drop_rider_cycle"]["mean_difference"] - 0.152) < 0.01),
        },
    }
    write_json(OUT_DIR / "drop_one_family.json", payload)

    lines = [
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"Excluded family & $\Delta$ IoU & 95\% CI & $n$ \\",
        r"\midrule",
    ]
    lines.append(
        f"None (all families) & {fmt(results['all_families']['mean_difference'])} & "
        f"[{fmt(results['all_families']['ci95_low_percentile'])}, {fmt(results['all_families']['ci95_high_percentile'])}] & 240 \\\\"
    )
    lines.append(r"\midrule")
    for family in FAMILIES:
        r = results[f"drop_{family}"]
        lines.append(
            f"{family.replace('_', r'\_')} & {fmt(r['mean_difference'])} & "
            f"[{fmt(r['ci95_low_percentile'])}, {fmt(r['ci95_high_percentile'])}] & {r['actor_count']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "drop_one_family_table.tex", "\n".join(lines))

    for key, r in results.items():
        print(f"{key:26s} {r['mean_difference']:.4f} [{r['ci95_low_percentile']:.4f}, {r['ci95_high_percentile']:.4f}] n={r['actor_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
