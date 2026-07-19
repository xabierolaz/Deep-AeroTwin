"""fig_pareto_neural.png — Payload vs voxel IoU scatter for descriptor-based
methods (SPPA-MVFit, Generic-MVFit, visual hull) and image-to-3D neural models
(TripoSR, Hunyuan3D-2mini-turbo, oblique/mask input conditions) on the 60-case
external neural wave. Log payload axis. The point is the modality mismatch
(compact semantic descriptor vs full mesh), not a leaderboard.

Data: benchmarks/results/sppa_neural_external_wave.json
(sppa_reference_rows_clean: voxel_iou/descriptor_bytes means;
aggregates: voxel_iou/mesh_bytes means per method x condition).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jgsa_style import OI, apply_style, save

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "benchmarks" / "results" / "sppa_neural_external_wave.json"
OUT = REPO / "figures" / "fig_pareto_neural.png"


def fmt_bytes(b: float) -> str:
    if b < 1e3:
        return f"{b:.0f} B"
    if b < 1e6:
        return f"{b / 1e3:.1f} kB"
    return f"{b / 1e6:.1f} MB"


def main() -> None:
    data = json.load(SRC.open("r", encoding="utf-8"))
    ref = data["sppa_reference_rows_clean"]
    agg = data["aggregates"]

    # (legend label, bytes, iou, color, marker, label dx, label dy, ha)
    points = [
        ("SPPA-MVFit (descriptor)", ref["sppa_mvfit"]["descriptor_bytes"]["mean"],
         ref["sppa_mvfit"]["voxel_iou"]["mean"], OI["blue"], "o", 12, -3, "left"),
        ("Generic-MVFit (descriptor)", ref["generic_mvfit"]["descriptor_bytes"]["mean"],
         ref["generic_mvfit"]["voxel_iou"]["mean"], OI["vermillion"], "o", 12, -3, "left"),
        ("Visual hull (descriptor)", ref["nonsemantic_visual_hull"]["descriptor_bytes"]["mean"],
         ref["nonsemantic_visual_hull"]["voxel_iou"]["mean"], OI["bluish_green"], "o", 12, -3, "left"),
        ("TripoSR (mask input)", agg["triposr/mask"]["mesh_bytes"]["mean"],
         agg["triposr/mask"]["voxel_iou"]["mean"], OI["orange"], "s", 0, 12, "center"),
        ("TripoSR (oblique input)", agg["triposr/oblique"]["mesh_bytes"]["mean"],
         agg["triposr/oblique"]["voxel_iou"]["mean"], OI["orange"], "D", -12, -16, "right"),
        ("Hunyuan3D-2mini (mask input)", agg["hunyuan3d_2mini_turbo/mask"]["mesh_bytes"]["mean"],
         agg["hunyuan3d_2mini_turbo/mask"]["voxel_iou"]["mean"], OI["reddish_purple"], "s", 0, 12, "center"),
        ("Hunyuan3D-2mini (oblique input)", agg["hunyuan3d_2mini_turbo/oblique"]["mesh_bytes"]["mean"],
         agg["hunyuan3d_2mini_turbo/oblique"]["voxel_iou"]["mean"], OI["reddish_purple"], "D", 0, -18, "center"),
    ]

    apply_style()
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    for label, b, iou, color, marker, dx, dy, ha in points:
        ax.scatter(b, iou, s=64, color=color, marker=marker, edgecolor="white",
                   linewidth=0.7, zorder=5, label=label)
        ax.annotate(f"{fmt_bytes(b)} / IoU {iou:.3f}", (b, iou),
                    textcoords="offset points", xytext=(dx, dy), fontsize=7.2,
                    color="#444444", ha=ha,
                    va="bottom" if dy > 0 else "top")

    ax.axvspan(7e2, 1e5, color=OI["blue"], alpha=0.05, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(7e2, 3e8)
    ax.set_ylim(0.05, 0.66)
    ax.set_xlabel("Payload per object (bytes, log scale)")
    ax.set_ylabel("Voxel IoU (64³)")
    ax.set_title("Representation cost vs fidelity, 60-case external wave — modality mismatch, not a leaderboard",
                 fontsize=8.4, pad=6)
    ax.legend(loc="upper right", fontsize=7.2, ncols=1, framealpha=0.95)
    # zone captions along the bottom edge (kept clear of points and legend)
    ax.text(1.05e3, 0.056, "descriptor payloads (≤ 33 kB)", fontsize=7.8,
            color=OI["blue"], va="bottom", ha="left")
    ax.text(2.7e8, 0.056, "neural mesh payloads (1.5–46.5 MB)", fontsize=7.8,
            color=OI["reddish_purple"], va="bottom", ha="right")
    save(fig, str(OUT))


if __name__ == "__main__":
    main()
