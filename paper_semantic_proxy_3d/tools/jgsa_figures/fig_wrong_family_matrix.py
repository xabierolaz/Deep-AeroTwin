"""fig_wrong_family_matrix.png — 6x6 heatmap of mean voxel IoU when the fitter
receives the correct vs a wrong family token (rows: true family, columns:
given token). Diagonal = correct token (pooled 0.557); off-diagonal collapse
shows the token carries usable geometric information.

Data: benchmarks/mvfit_reviewer_experiments/e1_wrong_family/wrong_family_matrix.json
(matrix_true_by_token; exploratory post-hoc label preserved).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import FAMILIES, FAMILY_LABELS, OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "benchmarks" / "mvfit_reviewer_experiments" / "e1_wrong_family" / "wrong_family_matrix.json"
OUT = REPO / "figures" / "fig_wrong_family_matrix.png"


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    M = np.array([[data["matrix_true_by_token"][t][g] for g in FAMILIES] for t in FAMILIES])
    pooled = data["pooled_means"]

    apply_style()
    fig, ax = plt.subplots(figsize=(5.9, 4.6))
    im = ax.imshow(M, cmap="Blues", vmin=0.0, vmax=0.75, aspect="equal")
    ax.set_xticks(range(6))
    ax.set_yticks(range(6))
    short = {f: FAMILY_LABELS[f].replace(" vehicle", "").replace(" vertical", "") for f in FAMILIES}
    ax.set_xticklabels([short[f] for f in FAMILIES], rotation=32, ha="right")
    ax.set_yticklabels([short[f] for f in FAMILIES])
    ax.set_xlabel("Family token given to the fitter")
    ax.set_ylabel("True family")

    for i in range(6):
        for j in range(6):
            v = M[i, j]
            color = "white" if v > 0.42 else "#222222"
            weight = "bold" if i == j else "normal"
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7.6,
                    color=color, fontweight=weight)
        # diagonal outline
        ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False,
                                   edgecolor=OI["vermillion"], linewidth=1.6, zorder=5))

    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cb.set_label("Mean voxel IoU (64³, clean)", fontsize=8)
    cb.ax.tick_params(labelsize=7.5)
    cb.outline.set_visible(False)

    ax.set_title(
        f"Correct-token mean {pooled['correct_token']:.3f} vs wrong-token mean {pooled['wrong_token_mean_over_5']:.3f}\n"
        f"(best-of-5 wrong tokens {pooled['wrong_token_best_of_5']:.3f} ≤ generic {pooled['generic']:.3f})",
        fontsize=8.6, pad=8)
    ax.grid(False)
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
