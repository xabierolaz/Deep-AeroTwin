from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_to_parts_to_proxy_v13.png"

COL = {
    "ink": "#202020",
    "muted": "#585858",
    "line": "#404040",
    "blue": "#7f93ef",
    "blue_light": "#eef3ff",
    "orange": "#edbd68",
    "orange_light": "#fff3cd",
    "green_light": "#edf7ef",
    "gray_light": "#f4f4f4",
    "gray": "#8d8d8d",
    "wheel": "#1d1d1d",
    "window": "#86d2d8",
    "reject": "#9a6a00",
}


def rounded(ax, x, y, w, h, face, *, edge=None, dashed=False, lw=0.9, radius=0.07):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0.035,rounding_size={radius}",
            linewidth=lw,
            edgecolor=edge or COL["ink"],
            facecolor=face,
            linestyle=(0, (4, 3)) if dashed else "solid",
        )
    )


def arrow(ax, start, end, *, dashed=False, color=None, lw=1.0):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=lw,
            color=color or COL["line"],
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=4,
            shrinkB=4,
        )
    )


def box3d(ax, x, y, w, h, color, *, depth=0.10, top=None, lw=0.55):
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=lw))
    ax.add_patch(
        Polygon(
            [(x, y + h), (x + depth, y + h + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=lw * 0.75,
        )
    )
    ax.add_patch(
        Polygon(
            [(x + w, y), (x + w + depth, y + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=lw * 0.75,
        )
    )


def wheel(ax, x, y, r):
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.45))
    ax.add_patch(Circle((x, y), r * 0.42, facecolor="white", edgecolor=COL["ink"], linewidth=0.28))


def assembled_truck(ax, x, y, cargo_len, *, long=False, scale=1.0):
    cab_w = 0.42 * scale
    cab_h = 0.48 * scale
    gap = 0.035 * scale
    chassis_h = 0.06 * scale
    wheel_r = 0.045 * scale
    box3d(ax, x, y + 0.34 * scale, cargo_len, 0.23 * scale, COL["orange"], depth=0.07 * scale, top="#f6d396")
    box3d(ax, x + cargo_len + gap, y + 0.29 * scale, cab_w, cab_h, COL["blue"], depth=0.06 * scale)
    ax.add_patch(
        Rectangle(
            (x + cargo_len + gap + 0.17 * scale, y + 0.48 * scale),
            0.09 * scale,
            0.08 * scale,
            facecolor=COL["window"],
            edgecolor=COL["ink"],
            linewidth=0.32,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + 0.03 * scale, y + 0.22 * scale),
            cargo_len + cab_w + gap,
            chassis_h,
            facecolor=COL["gray"],
            edgecolor=COL["ink"],
            linewidth=0.42,
        )
    )
    wheel_xs = [x + 0.16 * scale, x + max(cargo_len - 0.15 * scale, 0.38 * scale), x + cargo_len + gap + 0.16 * scale, x + cargo_len + gap + 0.34 * scale]
    if long:
        wheel_xs.insert(1, x + cargo_len * 0.55)
    for wx in wheel_xs:
        wheel(ax, wx, y + 0.13 * scale, wheel_r)


def role_row(ax, y, role, rule, color):
    ax.add_patch(Rectangle((0.50, y - 0.11), 0.16, 0.16, facecolor=color, edgecolor=COL["ink"], linewidth=0.35))
    ax.text(0.72, y, role, fontsize=6.2, fontweight="bold", ha="left", va="center")
    ax.text(1.58, y, rule, fontsize=5.25, color=COL["muted"], ha="left", va="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.25, 4.55), dpi=300)
    ax.set_xlim(0, 10.0)
    ax.set_ylim(0, 6.15)
    ax.axis("off")

    ax.text(0.12, 5.86, "From a semantic word to an updateable 3D proxy", fontsize=9.0, fontweight="bold", ha="left", va="top")
    ax.text(
        0.12,
        5.58,
        "Offline language/ontology can propose the part recipe; runtime only compiles a reviewed cache entry.",
        fontsize=5.9,
        color=COL["muted"],
        ha="left",
        va="top",
    )

    # Left panel: offline language/ontology decomposition.
    rounded(ax, 0.18, 0.70, 3.28, 4.50, COL["orange_light"], dashed=True)
    ax.text(0.38, 4.96, "offline decomposition draft", fontsize=7.1, fontweight="bold", ha="left", va="top")
    ax.text(0.38, 4.66, "LLM / ontology / human author", fontsize=5.75, color=COL["muted"], ha="left")
    rounded(ax, 0.42, 4.10, 2.72, 0.36, "white", lw=0.55, radius=0.04)
    ax.text(0.52, 4.28, 'input word: "truck"', fontsize=6.2, fontweight="bold", ha="left", va="center")
    ax.text(0.42, 3.78, "candidate semantic recipe", fontsize=6.0, fontweight="bold", ha="left")
    role_row(ax, 3.42, "cargo", "prism; variable length", COL["orange"])
    role_row(ax, 3.02, "cab", "bounded cabin module", COL["blue"])
    role_row(ax, 2.62, "chassis", "thin support prism", COL["gray"])
    role_row(ax, 2.22, "wheels", "fixed r; count by length", COL["wheel"])
    role_row(ax, 1.82, "windows", "semantic material cue", COL["window"])
    rounded(ax, 0.42, 1.08, 2.72, 0.44, "white", lw=0.55, radius=0.04)
    ax.text(0.55, 1.31, "not accepted until reviewed", fontsize=5.9, color=COL["reject"], fontweight="bold", ha="left", va="center")

    # Middle review/cache gate.
    rounded(ax, 3.78, 1.05, 1.70, 3.64, COL["green_light"])
    ax.text(3.96, 4.40, "reviewed cache", fontsize=7.0, fontweight="bold", ha="left", va="top")
    ax.text(3.96, 4.08, "z_c: vehicle.truck", fontsize=5.9, fontweight="bold", ha="left")
    ax.text(3.96, 3.66, "[ok] roles allowed", fontsize=5.45, color="#2d7d3f", ha="left")
    ax.text(3.96, 3.38, "[ok] primitives allowed", fontsize=5.45, color="#2d7d3f", ha="left")
    ax.text(3.96, 3.10, "[ok] part-scale rules", fontsize=5.45, color="#2d7d3f", ha="left")
    ax.text(3.96, 2.82, "[ok] fallback defined", fontsize=5.45, color="#2d7d3f", ha="left")
    ax.text(3.96, 2.26, "runtime receives only", fontsize=5.45, color=COL["muted"], ha="left")
    ax.text(3.96, 2.03, "cached rules +", fontsize=5.45, color=COL["muted"], ha="left")
    ax.text(3.96, 1.80, "telemetry evidence", fontsize=5.45, color=COL["muted"], ha="left")
    arrow(ax, (3.46, 3.95), (3.78, 3.95), dashed=True)

    # Right panel: actual geometric mapping and runtime variants.
    rounded(ax, 5.80, 0.70, 3.98, 4.50, COL["gray_light"])
    ax.text(6.00, 4.96, "deterministic primitive assembly", fontsize=7.1, fontweight="bold", ha="left", va="top")
    ax.text(6.00, 4.66, "update pose/parts; no per-frame mesh generation", fontsize=5.55, color=COL["muted"], ha="left")

    ax.text(6.00, 4.22, "recipe roles become 3D parts", fontsize=5.95, fontweight="bold", ha="left")
    box3d(ax, 6.00, 3.60, 0.80, 0.24, COL["orange"], depth=0.08, top="#f6d396")
    box3d(ax, 7.05, 3.48, 0.38, 0.48, COL["blue"], depth=0.06)
    ax.add_patch(Rectangle((5.98, 3.19), 1.58, 0.07, facecolor=COL["gray"], edgecolor=COL["ink"], linewidth=0.42))
    ax.add_patch(Rectangle((7.20, 3.67), 0.10, 0.09, facecolor=COL["window"], edgecolor=COL["ink"], linewidth=0.30))
    for wx in [6.12, 6.52, 7.12, 7.34]:
        wheel(ax, wx, 2.96, 0.045)

    ax.text(8.02, 3.86, "part graph, not", fontsize=5.55, color=COL["muted"], ha="left")
    ax.text(8.02, 3.62, "a single scaled box", fontsize=5.55, color=COL["muted"], ha="left")
    ax.text(8.02, 3.20, "root scale stays 1", fontsize=5.55, color=COL["muted"], ha="left")

    ax.text(6.00, 2.62, "short evidence", fontsize=5.65, fontweight="bold", ha="left")
    assembled_truck(ax, 6.02, 1.78, 0.58, long=False, scale=0.93)
    ax.text(6.00, 1.35, "long evidence", fontsize=5.65, fontweight="bold", ha="left")
    assembled_truck(ax, 6.02, 0.66, 1.10, long=True, scale=0.93)
    ax.text(8.12, 2.13, "cargo length changes", fontsize=5.25, color="#9a6500", ha="left")
    ax.text(8.12, 1.82, "cab module fixed", fontsize=5.25, color=COL["blue"], ha="left")
    ax.text(8.12, 1.51, "tire radius fixed", fontsize=5.25, color=COL["line"], ha="left")
    ax.text(8.12, 1.20, "extra axle allowed", fontsize=5.25, color=COL["muted"], ha="left")

    arrow(ax, (5.48, 2.88), (5.80, 2.88))

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
