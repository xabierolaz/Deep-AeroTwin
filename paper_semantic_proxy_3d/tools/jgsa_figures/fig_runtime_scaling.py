"""fig_runtime_scaling.png — Packaged Unreal 5.7 HISM backend dense scaling:
frame P95 of the pose-update and shape-update streams at 100/250/500 synthetic
objects (3 repetitions, 120 measured frames per phase), against 60 FPS and
30 FPS frame budgets.

Data: experiments/sppa_packaged_render/20260703T033655Z_packaged_render/
packaged_render_summary.json (frame_summary, backend semantic_proxy_instanced).
Documented in docs/sppa_hism_dense_scaling_benchmark_20260703.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = (REPO / "experiments" / "sppa_packaged_render" / "20260703T033655Z_packaged_render"
       / "packaged_render_summary.json")
OUT = REPO / "figures" / "fig_runtime_scaling.png"

COUNTS = (100, 250, 500)


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    fs = data["frame_summary"]
    series = {"pose_stream": [], "shape_stream": [], "create_steady": []}
    for c in COUNTS:
        for phase in series:
            row = next(r for r in fs if r["count"] == c and r["phase"] == phase)
            series[phase].append(float(row["frame_ms"]["p95"]))

    apply_style()
    fig, ax = plt.subplots(figsize=(5.8, 3.5))
    ax.axhline(16.6, color=OI["vermillion"], linestyle="--", linewidth=1.2, zorder=2)
    ax.text(500, 16.6 * 1.08, "60 FPS budget (16.6 ms)", color=OI["vermillion"],
            fontsize=7.6, ha="right")
    ax.axhline(33.3, color=OI["orange"], linestyle="--", linewidth=1.2, zorder=2)
    ax.text(500, 33.3 * 1.08, "30 FPS budget (33.3 ms)", color=OI["orange"],
            fontsize=7.6, ha="right")

    style = {
        "create_steady": (OI["bluish_green"], "o", "Create (steady)"),
        "pose_stream": (OI["blue"], "s", "Pose-update stream"),
        "shape_stream": (OI["vermillion"], "^", "Shape-update stream"),
    }
    for phase, (color, marker, label) in style.items():
        vals = series[phase]
        ax.plot(COUNTS, vals, marker=marker, color=color, linewidth=1.6,
                markersize=5.5, label=label, zorder=4)
        for c, v in zip(COUNTS, vals):
            off = (0, 8) if phase != "create_steady" else (0, -13)
            ax.annotate(f"{v:.1f}", (c, v), textcoords="offset points", xytext=off,
                        ha="center", fontsize=7.4, color=color)

    ax.set_yscale("log")
    ax.set_yticks([4, 8, 16, 32, 64, 128, 256])
    ax.set_yticklabels(["4", "8", "16", "32", "64", "128", "256"])
    ax.set_xticks(COUNTS)
    ax.set_xticklabels([str(c) for c in COUNTS])
    ax.set_xlabel("Synthetic objects in packaged scene")
    ax.set_ylabel("Frame P95 (ms, log scale)")
    ax.set_ylim(3.5, 300)
    ax.legend(loc="upper left", fontsize=7.8)
    ax.set_title("Packaged Unreal dense-update scaling (HISM backend, 11 draw groups)",
                 fontsize=8.6, pad=6)
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
