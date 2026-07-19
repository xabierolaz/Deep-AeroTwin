"""fig_h1_by_family.png — Delta SPPA-MVFit minus Generic-MVFit voxel IoU for the
12 family x stratum cells with 95% bootstrap CI, against the preregistered
+0.030 superiority margin.

Data: reproducibility/sppa_mvfit/results/test/raw_metrics.csv (sealed, clean
condition). Point estimates cross-checked against
reproducibility/sppa_mvfit/results/test/confirmatory_summary.json
(primary.stratum_point_estimates). Per-cell CIs are derived from the sealed
raw_metrics.csv with a within-cell percentile bootstrap (20 actors resampled
with replacement, 10000 draws, seed 77157 as in the sealed analysis).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import (FAMILIES, FAMILY_LABELS, MARGIN_IOT, OI, STRATA,
                        STRATUM_LABELS, apply_style, save)

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
RAW = REPO / "reproducibility" / "sppa_mvfit" / "results" / "test" / "raw_metrics.csv"
SUMMARY = REPO / "reproducibility" / "sppa_mvfit" / "results" / "test" / "confirmatory_summary.json"
OUT = REPO / "figures" / "fig_h1_by_family.png"

SEED = 77157
DRAWS = 10000


def main() -> None:
    rows = list(csv.DictReader(RAW.open("r", encoding="utf-8")))
    # paired per-actor differences, clean condition
    sppa = {r["case_id"]: float(r["voxel_iou"]) for r in rows
            if r["method"] == "sppa_mvfit" and r["condition"] == "clean"}
    gen = {r["case_id"]: float(r["voxel_iou"]) for r in rows
           if r["method"] == "generic_mvfit" and r["condition"] == "clean"}
    meta = {r["case_id"]: (r["family"], r["stratum"]) for r in rows
            if r["method"] == "sppa_mvfit" and r["condition"] == "clean"}
    assert len(sppa) == len(gen) == 240

    cells: dict[tuple[str, str], list[float]] = {}
    for cid, (fam, stratum) in meta.items():
        cells.setdefault((fam, stratum), []).append(sppa[cid] - gen[cid])

    # cross-check point estimates vs sealed confirmatory summary
    sealed = json.load(SUMMARY.open("r", encoding="utf-8"))["primary"]["stratum_point_estimates"]
    for (fam, stratum), diffs in sorted(cells.items()):
        est = float(np.mean(diffs))
        key = f"{fam}|{stratum}"
        assert abs(est - sealed[key]) < 1e-9, (key, est, sealed[key])

    # per-cell percentile bootstrap CI (within-cell resampling)
    rng = np.random.default_rng(SEED)
    stats = {}
    for (fam, stratum) in sorted(cells):
        arr = np.asarray(cells[(fam, stratum)], dtype=np.float64)
        boot = rng.random((DRAWS, len(arr)))
        idx = (boot * len(arr)).astype(int)
        draws = arr[idx].mean(axis=1)
        stats[(fam, stratum)] = (float(arr.mean()),
                                 float(np.quantile(draws, 0.025)),
                                 float(np.quantile(draws, 0.975)))

    apply_style()
    fig, ax = plt.subplots(figsize=(7.1, 3.4))
    x = np.arange(len(FAMILIES))
    width = 0.36
    colors = {"csg_id": OI["blue"], "implicit_ood": OI["orange"]}
    for k, stratum in enumerate(STRATA):
        vals, lo, hi = [], [], []
        for fam in FAMILIES:
            m, l, h = stats[(fam, stratum)]
            vals.append(m); lo.append(m - l); hi.append(h - m)
        pos = x + (k - 0.5) * width
        ax.bar(pos, vals, width, color=colors[stratum], label=STRATUM_LABELS[stratum],
               edgecolor="white", linewidth=0.5, zorder=3)
        ax.errorbar(pos, vals, yerr=[lo, hi], fmt="none", ecolor="#333333",
                    elinewidth=1.0, zorder=4)
        for xi, v in zip(pos, vals):
            ax.text(xi, v + 0.012, f"{v:.3f}", ha="center", va="bottom", fontsize=6.6,
                    color="#333333")

    overall = json.load(SUMMARY.open("r", encoding="utf-8"))["primary"]
    ax.axhline(MARGIN_IOT, color=OI["vermillion"], linestyle="--", linewidth=1.2, zorder=2)
    ax.text(len(FAMILIES) - 0.45, MARGIN_IOT + 0.006, f"H1 margin +{MARGIN_IOT:.3f}",
            color=OI["vermillion"], fontsize=7.5, ha="right", va="bottom")
    ax.axhline(overall["mean_difference"], color=OI["bluish_green"], linestyle=":",
               linewidth=1.2, zorder=2)
    ax.text(-0.45, overall["mean_difference"] - 0.007,
            f"overall $\\Delta$ = {overall['mean_difference']:.3f} "
            f"[{overall['ci95_low_percentile']:.3f}, {overall['ci95_high_percentile']:.3f}]",
            color=OI["bluish_green"], fontsize=7.5, ha="left", va="top")

    ax.set_xticks(x)
    ax.set_xticklabels([FAMILY_LABELS[f].replace(" ", "\n") for f in FAMILIES])
    ax.set_ylabel("Δ voxel IoU (SPPA − Generic)")
    ax.set_ylim(0, 0.52)
    ax.set_xlim(-0.6, len(FAMILIES) - 0.4)
    ax.legend(loc="upper left", ncols=2, title="Stratum", title_fontsize=8)
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
