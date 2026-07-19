"""fig_robustness_conditions.png — Paired Delta SPPA-MVFit minus Generic-MVFit
voxel IoU across the five observation conditions with 95% CI; all deltas lie
above the +0.030 preregistered margin.

Data: benchmarks/mvfit_posthoc_analysis/t1_robustness/robustness_conditions_table.json
(sealed raw_metrics.csv re-analysis; post-hoc/exploratory label preserved).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import MARGIN_IOT, OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "benchmarks" / "mvfit_posthoc_analysis" / "t1_robustness" / "robustness_conditions_table.json"
OUT = REPO / "figures" / "fig_robustness_conditions.png"

CONDITIONS = ("clean", "mild_morphology", "moderate_morphology", "partial_occlusion", "mask_corruption")
LABELS = {
    "clean": "Clean",
    "mild_morphology": "Mild\nmorphology",
    "moderate_morphology": "Moderate\nmorphology",
    "partial_occlusion": "Partial\nocclusion",
    "mask_corruption": "Mask\ncorruption",
}


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    deltas = data["paired_delta_sppa_minus_generic_by_condition"]
    means = data["mean_voxel_iou_by_method_condition"]

    apply_style()
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    xs = range(len(CONDITIONS))
    vals = [deltas[c]["mean_difference"] for c in CONDITIONS]
    lo = [deltas[c]["mean_difference"] - deltas[c]["ci95_low_percentile"] for c in CONDITIONS]
    hi = [deltas[c]["ci95_high_percentile"] - deltas[c]["mean_difference"] for c in CONDITIONS]

    bars = ax.bar(xs, vals, 0.58, color=OI["blue"], edgecolor="white", linewidth=0.6, zorder=3)
    ax.errorbar(xs, vals, yerr=[lo, hi], fmt="none", ecolor="#333333", elinewidth=1.1, zorder=4)
    for x, v, c in zip(xs, vals, CONDITIONS):
        ax.text(x, v + 0.008, f"{v:.3f}", ha="center", va="bottom", fontsize=7.6, color="#333333")
        # absolute means under each bar (S = SPPA, G = Generic)
        ax.text(x, 0.006, f"S {means['sppa_mvfit'][c]:.3f}\nG {means['generic_mvfit'][c]:.3f}",
                ha="center", va="bottom", fontsize=6.6, color="white", zorder=5,
                linespacing=1.3)

    ax.axhline(MARGIN_IOT, color=OI["vermillion"], linestyle="--", linewidth=1.2, zorder=2)
    ax.text(4.35, MARGIN_IOT + 0.004, f"H1 margin +{MARGIN_IOT:.3f}", color=OI["vermillion"],
            fontsize=7.5, ha="right", va="bottom")

    ax.set_xticks(list(xs))
    ax.set_xticklabels([LABELS[c] for c in CONDITIONS])
    ax.set_ylabel("Δ voxel IoU (SPPA − Generic)")
    ax.set_ylim(0, 0.25)
    worst = min(CONDITIONS, key=lambda c: deltas[c]["mean_difference"])
    ax.set_title("Paired Δ SPPA−Generic by observation condition (n = 240 per condition)",
                 pad=6, fontsize=8.6)
    ax.annotate(f"all Δ > +0.030 margin (min {deltas[worst]['mean_difference']:.3f}, "
                f"{LABELS[worst].replace(chr(10), ' ')})\nS/G inside bars = SPPA / Generic mean IoU",
                xy=(0.015, 0.975), xycoords="axes fraction", fontsize=7.4, va="top",
                color=OI["bluish_green"], linespacing=1.4)
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
