from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_to_parts_to_proxy_v14.png"

COL = {
    "ink": "#202020",
    "muted": "#5a5a5a",
    "line": "#4a4a4a",
    "llm": "#fff1c2",
    "cache": "#eaf6ed",
    "runtime": "#eef2ff",
    "output": "#f5f5f5",
    "cargo": "#efc06b",
    "cab": "#8296f1",
    "chassis": "#9c9c9c",
    "wheel": "#202020",
    "window": "#8cd6dd",
    "warn": "#a46a00",
    "good": "#237a36",
}


def rounded(ax, x, y, w, h, face, *, edge=None, dashed=False, lw=0.9, radius=0.075):
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
            shrinkA=5,
            shrinkB=5,
        )
    )


def box3d(ax, x, y, w, h, color, *, depth=0.09, top=None, lw=0.55):
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=lw))
    ax.add_patch(
        Polygon(
            [(x, y + h), (x + depth, y + h + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=lw * 0.8,
        )
    )
    ax.add_patch(
        Polygon(
            [(x + w, y), (x + w + depth, y + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=lw * 0.8,
        )
    )


def wheel(ax, x, y, r):
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.45))
    ax.add_patch(Circle((x, y), r * 0.42, facecolor="white", edgecolor=COL["ink"], linewidth=0.28))


def part_chip(ax, x, y, label, color, rule):
    ax.add_patch(Rectangle((x, y), 0.17, 0.17, facecolor=color, edgecolor=COL["ink"], linewidth=0.35))
    ax.text(x + 0.24, y + 0.085, label, fontsize=5.5, fontweight="bold", va="center", ha="left")
    ax.text(x + 0.86, y + 0.085, rule, fontsize=4.8, color=COL["muted"], va="center", ha="left")


def side_truck(ax, x, y, cargo_len, *, scale=1.0, long=False, label=None):
    cab_w = 0.44 * scale
    cab_h = 0.48 * scale
    gap = 0.03 * scale
    wheel_r = 0.048 * scale
    chassis_y = y + 0.20 * scale
    box3d(ax, x, y + 0.34 * scale, cargo_len, 0.24 * scale, COL["cargo"], depth=0.065 * scale, top="#f5d18f")
    box3d(ax, x + cargo_len + gap, y + 0.29 * scale, cab_w, cab_h, COL["cab"], depth=0.055 * scale)
    ax.add_patch(
        Rectangle(
            (x + cargo_len + gap + 0.17 * scale, y + 0.48 * scale),
            0.09 * scale,
            0.08 * scale,
            facecolor=COL["window"],
            edgecolor=COL["ink"],
            linewidth=0.3,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + 0.02 * scale, chassis_y),
            cargo_len + cab_w + gap + 0.02 * scale,
            0.055 * scale,
            facecolor=COL["chassis"],
            edgecolor=COL["ink"],
            linewidth=0.38,
        )
    )
    wheel_xs = [x + 0.15 * scale, x + max(cargo_len - 0.14 * scale, 0.34 * scale), x + cargo_len + gap + 0.15 * scale, x + cargo_len + gap + 0.34 * scale]
    if long:
        wheel_xs.insert(1, x + cargo_len * 0.55)
    for wx in wheel_xs:
        wheel(ax, wx, y + 0.11 * scale, wheel_r)
    if label:
        ax.text(x, y + 0.93 * scale, label, fontsize=5.6, fontweight="bold", ha="left", va="center")


def exploded_parts(ax, x, y):
    ax.text(x, y + 0.78, "3D primitive parts", fontsize=5.7, fontweight="bold", ha="left")
    box3d(ax, x, y + 0.36, 0.66, 0.22, COL["cargo"], depth=0.06, top="#f5d18f")
    box3d(ax, x + 0.86, y + 0.29, 0.34, 0.45, COL["cab"], depth=0.05)
    ax.add_patch(Rectangle((x, y + 0.11), 1.28, 0.06, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.35))
    for wx in [x + 0.10, x + 0.42, x + 0.92, x + 1.12]:
        wheel(ax, wx, y - 0.04, 0.04)


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.25, 4.35), dpi=300)
    ax.set_xlim(0, 10.0)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    ax.text(0.16, 5.76, "Language-to-parts-to-proxy example", fontsize=8.8, fontweight="bold", ha="left", va="top")
    ax.text(
        0.16,
        5.49,
        "The language model is an offline recipe authoring aid. The runtime path uses only reviewed cached rules.",
        fontsize=5.45,
        color=COL["muted"],
        ha="left",
        va="top",
    )

    rounded(ax, 0.18, 3.05, 2.82, 2.12, COL["llm"], dashed=True)
    ax.text(0.36, 4.94, "offline language draft", fontsize=6.45, fontweight="bold", ha="left", va="top")
    rounded(ax, 0.40, 4.38, 2.34, 0.34, "white", lw=0.55, radius=0.045)
    ax.text(0.52, 4.55, 'YOLO tag / word: "truck"', fontsize=5.8, fontweight="bold", ha="left", va="center")
    ax.text(0.42, 4.13, "parts(truck) ->", fontsize=5.5, fontweight="bold", ha="left")
    part_chip(ax, 0.50, 3.78, "cargo", COL["cargo"], "variable span")
    part_chip(ax, 0.50, 3.48, "cab", COL["cab"], "bounded module")
    part_chip(ax, 0.50, 3.18, "wheels", COL["wheel"], "fixed radius")

    rounded(ax, 3.36, 3.05, 1.82, 2.12, COL["cache"])
    ax.text(3.56, 4.92, "review gate", fontsize=6.45, fontweight="bold", ha="left", va="top")
    ax.text(3.56, 4.55, "cache key: z_c", fontsize=5.35, fontweight="bold", ha="left")
    ax.text(3.56, 4.17, "[ok] allowed roles", fontsize=5.0, color=COL["good"], ha="left")
    ax.text(3.56, 3.88, "[ok] scale limits", fontsize=5.0, color=COL["good"], ha="left")
    ax.text(3.56, 3.59, "[ok] fallback rule", fontsize=5.0, color=COL["good"], ha="left")
    ax.text(3.56, 3.22, "runtime LLM: off", fontsize=5.1, color=COL["warn"], fontweight="bold", ha="left")

    rounded(ax, 5.56, 3.05, 2.08, 2.12, COL["runtime"])
    ax.text(5.75, 4.92, "runtime compiler", fontsize=6.45, fontweight="bold", ha="left", va="top")
    ax.text(5.75, 4.55, "inputs:", fontsize=5.25, fontweight="bold", ha="left")
    ax.text(5.75, 4.27, "label + bbox/mask + track", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(5.75, 3.87, "q_t:", fontsize=5.25, fontweight="bold", ha="left")
    ax.text(6.16, 3.87, "part dimensions", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(5.75, 3.57, "xi_t:", fontsize=5.25, fontweight="bold", ha="left")
    ax.text(6.16, 3.57, "actor pose", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(5.75, 3.23, "update: transform/parts only", fontsize=4.9, color=COL["muted"], ha="left")

    rounded(ax, 8.02, 3.05, 1.78, 2.12, COL["output"])
    exploded_parts(ax, 8.18, 3.28)

    arrow(ax, (3.00, 4.12), (3.36, 4.12), dashed=True)
    arrow(ax, (5.18, 4.12), (5.56, 4.12))
    arrow(ax, (7.64, 4.12), (8.02, 4.12))

    rounded(ax, 0.18, 0.34, 9.62, 2.30, "white")
    ax.text(0.42, 2.40, "Role-specific adaptation, not global object scaling", fontsize=6.5, fontweight="bold", ha="left", va="top")
    side_truck(ax, 0.50, 1.22, 0.62, scale=0.88, long=False, label="short evidence")
    side_truck(ax, 3.03, 1.22, 1.18, scale=0.88, long=True, label="long evidence")
    arrow(ax, (2.25, 1.78), (2.82, 1.78))
    ax.text(5.62, 2.01, "same cab size", fontsize=5.2, color=COL["cab"], fontweight="bold", ha="left")
    ax.text(5.62, 1.72, "same wheel radius", fontsize=5.2, color=COL["wheel"], fontweight="bold", ha="left")
    ax.text(5.62, 1.43, "cargo span absorbs length", fontsize=5.2, color=COL["warn"], fontweight="bold", ha="left")
    ax.text(5.62, 1.14, "extra axle allowed by rule", fontsize=5.2, color=COL["muted"], fontweight="bold", ha="left")
    ax.text(7.62, 1.83, "descriptor emits", fontsize=5.1, color=COL["muted"], ha="left")
    ax.text(7.62, 1.56, "parts[] + update policy", fontsize=5.1, fontweight="bold", ha="left")
    ax.text(7.62, 1.23, "not a regenerated mesh", fontsize=5.1, color=COL["muted"], ha="left")

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
