"""Compose figures/fig_role_colored_blender.png.

(a) Blender render of the fitted quadruped (test-csg_id-quadruped-018) with
    slot-role colors and the GT mesh as a semi-transparent ghost
    (assets/render_role_overlay.png, from blender/render_role_overlay.py).
(b) E6 role-aware IoU bar chart, read from
    benchmarks/mvfit_reviewer_experiments/e6_role_aware/role_aware_iou.json
    (descriptive post-hoc, mapping frozen before computation; csg_id stratum,
    120 actors; theta from sealed outputs, no refitting).

Run: python compose_role_colored.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

import jgsa_style as JS

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
ASSETS = REPO / "tools" / "jgsa_figures" / "assets"
E6 = REPO / "benchmarks" / "mvfit_reviewer_experiments" / "e6_role_aware" / "role_aware_iou.json"
OUT = REPO / "figures" / "fig_role_colored_blender.png"


def main() -> None:
    JS.apply_style()
    e6 = json.loads(E6.read_text(encoding="utf-8"))
    ov = e6["overall"]
    delta = e6["true_minus_shuffle_random_actor_iou"]

    names = ["true role mapping", "shuffle (random)", "shuffle (cyclic)"]
    vals = [ov["role_iou"], ov["shuffle_random_role_iou"], ov["shuffle_cyclic_role_iou"]]
    colors = [JS.OI["blue"], JS.OI["gray"], JS.OI["light_gray"]]

    fig = plt.figure(figsize=(10.6, 4.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1.0], wspace=0.06)

    ax_img = fig.add_subplot(gs[0, 0])
    ax_img.imshow(mpimg.imread(ASSETS / "render_role_overlay.png"))
    ax_img.set_axis_off()
    ax_img.set_title("(a) fitted quadruped: slot roles + GT ghost", pad=6)

    ax = fig.add_subplot(gs[0, 1])
    bars = ax.bar(names, vals, color=colors, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.008, f"{v:.3f}",
                ha="center", va="bottom", fontsize=8.5)
    ax.set_ylim(0, 0.40)
    ax.set_ylabel("role-aware voxel IoU (64\u00b3)")
    ax.set_title("(b) Role-aware IoU vs shuffle controls", pad=6)
    ax.tick_params(axis="x", labelrotation=12)
    ax.text(0.03, 0.97,
            (f"\u0394 = {delta['mean_difference']:.3f}, 95% CI "
             f"[{delta['ci95_low']:.3f}, {delta['ci95_high']:.3f}]\n"
             f"csg_id stratum, n = {e6['n_actors']} actors"),
            transform=ax.transAxes, ha="left", va="top", fontsize=8,
            color="#1A1A1A")

    JS.save(fig, str(OUT))
    plt.close(fig)


if __name__ == "__main__":
    main()
