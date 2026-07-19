"""fig_view_ablation.png — View ablation for SPPA-MVFit: dual-view vs top-only
vs side-only mean voxel IoU, with paired-bootstrap deltas (95% CI) against the
dual view. Right panel: the observed top and side masks of one sealed test
case (the two views the fitter consumes).

Data: benchmarks/mvfit_reviewer_experiments/e2_top_only/top_only_ablation.json
(pooled_means, paired_bootstrap). Masks:
reproducibility/sppa_mvfit/data/test/observation_masks.npy (case
test-csg_id-articulated_vehicle-013, clean; index 0 = top, 1 = side).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "benchmarks" / "mvfit_reviewer_experiments" / "e2_top_only" / "top_only_ablation.json"
MASKS = REPO / "reproducibility" / "sppa_mvfit" / "data" / "test" / "observation_masks.npy"
CASES = REPO / "reproducibility" / "sppa_mvfit" / "data" / "test" / "public_cases.json"
OUT = REPO / "figures" / "fig_view_ablation.png"

CASE_ID = "test-csg_id-articulated_vehicle-013"


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    pm = data["pooled_means"]
    pb = data["paired_bootstrap"]

    apply_style()
    fig = plt.figure(figsize=(7.0, 3.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.5, 1.0], wspace=0.18)
    ax = fig.add_subplot(gs[0, 0])

    labels = ["Dual view\n(top + side)", "Top-only", "Side-only"]
    vals = [pm["dual_view"], pm["top_only"], pm["side_only"]]
    deltas = [None, pb["top_only_minus_dual"], pb["side_only_minus_dual"]]
    colors = [OI["blue"], OI["orange"], OI["sky_blue"]]
    bars = ax.bar(range(3), vals, 0.55, color=colors, edgecolor="white", linewidth=0.6, zorder=3)
    for i, (r, v) in enumerate(zip(bars, vals)):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.008, f"{v:.3f}", ha="center",
                va="bottom", fontsize=8.6)
        if deltas[i] is not None:
            d = deltas[i]
            ax.text(r.get_x() + r.get_width() / 2, v / 2,
                    f"Δ = {d['mean_difference']:.3f}\n[{d['ci95_low']:.3f},\n{d['ci95_high']:.3f}]",
                    ha="center", va="center", fontsize=7.2, color="white", linespacing=1.35)

    ax.set_xticks(range(3))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Mean voxel IoU (64³, clean)")
    ax.set_ylim(0, 0.64)
    ax.set_title("Observation-view ablation (SPPA-MVFit, n = 240; Δ vs dual view)", pad=6)

    # right panel: the two observed views of a sealed test case
    cases = json.load(CASES.open("r", encoding="utf-8"))
    idx = next(c["index"] for c in cases if c["case_id"] == CASE_ID)
    masks = np.load(MASKS)
    top, side = masks[idx, 0, 0], masks[idx, 0, 1]
    sub = gs[0, 1].subgridspec(2, 1, hspace=0.45)
    for k, (mask, name) in enumerate(((top, "top view"), (side, "side view"))):
        axm = fig.add_subplot(sub[k, 0])
        axm.imshow(mask.T, cmap="gray_r", interpolation="nearest", origin="lower")
        axm.set_title(f"observed {name}", fontsize=7.4, pad=2)
        axm.set_xticks([]); axm.set_yticks([])
        for s in axm.spines.values():
            s.set_edgecolor("#999999"); s.set_linewidth(0.6)
    fig.text(0.995, 0.02, f"masks: {CASE_ID} (clean)", fontsize=6.4, color="#666666",
             ha="right", va="bottom")

    save(fig, str(OUT))


if __name__ == "__main__":
    main()
