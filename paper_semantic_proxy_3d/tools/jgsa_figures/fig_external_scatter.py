"""fig_external_scatter.png — External mesh sanity check: per-case scatter of
SPPA-MVFit vs Generic-MVFit voxel IoU on the 52 real meshes (Objaverse LVIS +
ModelNet40), one point per case, colored by mapped family, y=x reference.

Data: benchmarks/external_mesh_sanity/results/results.jsonl (52 cases x 10
methods, clean condition). Matches the main-paper caption: "per-case
SPPA-MVFit versus Generic-MVFit voxel IoU ... colored by mapped family.
Points near the diagonal dominate; the paired difference (+0.043,
CI [-0.007, +0.094]) includes zero."
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
SRC = REPO / "benchmarks" / "external_mesh_sanity" / "results" / "results.jsonl"
OUT = REPO / "figures" / "fig_external_scatter.png"

FAMILY_COLORS = {
    "compact_vehicle": OI["blue"],
    "articulated_vehicle": OI["vermillion"],
    "quadruped": OI["bluish_green"],
    "branching_vertical": OI["orange"],
    "lattice_tower": OI["sky_blue"],
    "rider_cycle": OI["reddish_purple"],
}


def main() -> None:
    rows = [json.loads(l) for l in SRC.open("r", encoding="utf-8")]
    by_case: dict[str, dict[str, float]] = {}
    fam_of: dict[str, str] = {}
    for r in rows:
        if r.get("condition") != "clean":
            continue
        fam_of[r["case_id"]] = r["family"]
        by_case.setdefault(r["case_id"], {})[r["method"]] = r["voxel_iou"]

    cases = sorted(by_case)
    x = np.array([by_case[c]["generic_mvfit"] for c in cases])
    y = np.array([by_case[c]["sppa_mvfit"] for c in cases])
    fams = [fam_of[c] for c in cases]
    assert len(cases) == 52, f"expected 52 cases, got {len(cases)}"

    d = y - x
    print(f"n={len(cases)}  sppa mean={y.mean():.3f}  generic mean={x.mean():.3f}  "
          f"paired diff={d.mean():+.3f}  above diag={int((d > 0).sum())}/{len(cases)}")

    apply_style()
    fig, ax = plt.subplots(figsize=(3.7, 3.6))
    lim = (0.10, 0.90)
    ax.plot(lim, lim, color="#999999", linestyle="--", linewidth=1.0, zorder=2,
            label="y = x (no difference)")
    for f in FAMILIES:
        idx = [i for i, ff in enumerate(fams) if ff == f]
        if not idx:
            continue
        ax.scatter(x[idx], y[idx], s=26, color=FAMILY_COLORS[f], alpha=0.85,
                   edgecolor="white", linewidth=0.5, zorder=3,
                   label=FAMILY_LABELS[f])
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Generic-MVFit voxel IoU (64\u00b3)")
    ax.set_ylabel("SPPA-MVFit voxel IoU (64\u00b3)")
    ax.text(0.03, 0.97,
            "paired $\\Delta$ = +0.043, 95% CI [$-$0.007, +0.094]\n"
            "52 real meshes (Objaverse LVIS + ModelNet40)",
            transform=ax.transAxes, ha="left", va="top", fontsize=7.4,
            color="#1A1A1A")
    ax.legend(loc="lower right", fontsize=6.6, markerscale=0.9,
              handletextpad=0.15, borderpad=0.3, labelspacing=0.35)
    save(fig, str(OUT))
    plt.close(fig)


if __name__ == "__main__":
    main()
