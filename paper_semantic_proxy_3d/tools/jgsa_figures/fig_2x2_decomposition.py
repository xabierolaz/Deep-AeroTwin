"""fig_2x2_decomposition.png — 2x2 decomposition of graph family (SPPA vs
Generic) x fitting (text-only vs mask-fitted): four mean voxel-IoU cells with
annotated graph and fitting effects (95% CI).

Data: benchmarks/mvfit_posthoc_analysis/t2_graph_x_fitting/graph_x_fitting_2x2.json
(post-hoc; generic_nofit computed from the sealed method module + released GT,
other cells from sealed raw_metrics.csv clean rows).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "benchmarks" / "mvfit_posthoc_analysis" / "t2_graph_x_fitting" / "graph_x_fitting_2x2.json"
OUT = REPO / "figures" / "fig_2x2_decomposition.png"


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    cells = data["cell_mean_voxel_iou"]["overall"]
    eff = data["effects"]["overall"]

    g_nofit = eff["graph_effect_nofit"]          # SPPA-nofit - Generic-nofit  (+0.248)
    g_fit = eff["graph_effect_fit"]              # SPPA-fit - Generic-fit    (+0.190, headline)
    f_gen = eff["fitting_effect_generic"]        # Generic-fit - Generic-nofit (+0.187)
    f_sppa = eff["fitting_effect_sppa"]          # SPPA-fit - SPPA-nofit     (+0.130)

    apply_style()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    groups = ["No fitting\n(text-only)", "Mask-fitted"]
    xs = [0.0, 1.0]
    w = 0.32
    gen_vals = [cells["generic_nofit"], cells["generic_fit"]]
    sppa_vals = [cells["sppa_nofit"], cells["sppa_fit"]]

    b1 = ax.bar([x - w / 2 for x in xs], gen_vals, w, color=OI["vermillion"],
                edgecolor="white", linewidth=0.6, label="Generic graph", zorder=3)
    b2 = ax.bar([x + w / 2 for x in xs], sppa_vals, w, color=OI["blue"],
                edgecolor="white", linewidth=0.6, label="SPPA family graph", zorder=3)
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.008,
                    f"{r.get_height():.3f}", ha="center", va="bottom", fontsize=8.2)

    def arrow(x0, x1, y, text, color):
        ax.annotate("", xy=(x1, y), xytext=(x0, y),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=1.4,
                                    shrinkA=2, shrinkB=2))
        ax.text((x0 + x1) / 2, y + 0.006, text, ha="center", va="bottom",
                fontsize=7.8, color=color)

    # graph effect arrows (horizontal, above each group pair)
    arrow(xs[0] - w / 2, xs[0] + w / 2, 0.50,
          f"graph +{g_nofit['mean_difference']:.3f}\n[{g_nofit['ci95_low_percentile']:.3f}, {g_nofit['ci95_high_percentile']:.3f}]",
          OI["bluish_green"])
    arrow(xs[1] - w / 2, xs[1] + w / 2, 0.635,
          f"graph +{g_fit['mean_difference']:.3f} (headline Δ)\n[{g_fit['ci95_low_percentile']:.3f}, {g_fit['ci95_high_percentile']:.3f}]",
          OI["bluish_green"])

    # fitting effect arrows (vertical, inside/right of bars)
    ax.annotate("", xy=(xs[1] - w / 2 - 0.055, cells["generic_fit"]),
                xytext=(xs[1] - w / 2 - 0.055, cells["generic_nofit"]),
                arrowprops=dict(arrowstyle="->", color=OI["reddish_purple"], lw=1.4))
    ax.text(xs[1] - w / 2 - 0.075, 0.27,
            f"fitting +{f_gen['mean_difference']:.3f}\n[{f_gen['ci95_low_percentile']:.3f}, {f_gen['ci95_high_percentile']:.3f}]",
            ha="right", va="center", fontsize=7.8, color=OI["reddish_purple"])
    ax.annotate("", xy=(xs[1] + w / 2 + 0.055, cells["sppa_fit"]),
                xytext=(xs[1] + w / 2 + 0.055, cells["sppa_nofit"]),
                arrowprops=dict(arrowstyle="->", color=OI["reddish_purple"], lw=1.4))
    ax.text(xs[1] + w / 2 + 0.075, 0.49,
            f"fitting +{f_sppa['mean_difference']:.3f}\n[{f_sppa['ci95_low_percentile']:.3f}, {f_sppa['ci95_high_percentile']:.3f}]",
            ha="left", va="center", fontsize=7.8, color=OI["reddish_purple"])

    ax.set_xticks(xs)
    ax.set_xticklabels(groups)
    ax.set_ylabel("Mean voxel IoU (64³, clean)")
    ax.set_ylim(0, 0.72)
    ax.set_xlim(-0.55, 1.75)
    ax.legend(loc="upper left")
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
