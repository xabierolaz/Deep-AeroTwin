"""E7 figure split for the 2026-07-20 mission reframe.

The original 2x2 fig_real_stream.png is split per the reframe plan:
  - MAIN keeps the degraded-signal panels: (a) real frame with detector
    bboxes + GT anchors, (b) 2D reprojection IoU by detector class
    (original panels a and c).
  - SUPPLEMENT keeps the localization panels: (a) plan view of a GT-matched
    tower case, (b) observation-error identity scatter (original panels b
    and d).

Reuses the panel renderers of make_fig_e7.py; only the panel letters in the
titles are re-lettered. Original figure and script are left untouched.

Run:  python make_fig_e7_split.py
Outputs (paper_semantic_proxy_3d/figures/):
  fig_real_stream_main.png, fig_real_stream_localization.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

E7_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(E7_ROOT))

import make_fig_e7 as e7  # noqa: E402

FIGURES_DIR = E7_ROOT.parents[1] / "figures"


def main() -> int:
    analysis = e7.json.loads((E7_ROOT / "e7_analysis.json").read_text(encoding="utf-8"))

    # --- main-text figure: degraded-signal panels (frame + reprojection) ---
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9))
    e7.panel_frame(axes[0])
    axes[0].set_title("(a) Real frame f478: detector bboxes (red) vs exact GT anchors (green/blue)",
                      fontsize=8)
    e7.panel_bars(axes[1], analysis)
    axes[1].set_title("(b) Fit to the real image evidence, by detector class", fontsize=8)
    fig.tight_layout()
    out_main = FIGURES_DIR / "fig_real_stream_main.png"
    fig.savefig(out_main, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("saved", out_main)

    # --- supplement figure: localization panels (plan view + identity) ---
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1))
    e7.panel_plan(axes[0])
    axes[0].set_title("(a) Plan view, tower case (loc. err. = observation-bound)", fontsize=8)
    axes[0].legend(fontsize=5.5, loc="best", framealpha=0.9)
    e7.panel_scatter(axes[1])
    axes[1].set_title("(b) Localization is observation-bound", fontsize=8)
    fig.tight_layout()
    out_supp = FIGURES_DIR / "fig_real_stream_localization.png"
    fig.savefig(out_supp, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("saved", out_supp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
