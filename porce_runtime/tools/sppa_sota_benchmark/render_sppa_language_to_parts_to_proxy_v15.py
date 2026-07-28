from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_to_parts_to_proxy_v15.png"

COL = {
    "ink": "#202020",
    "muted": "#595959",
    "line": "#444444",
    "draft": "#fff1c2",
    "cache": "#e6f3ea",
    "runtime": "#eef2ff",
    "cargo": "#efc06b",
    "cab": "#8296f1",
    "chassis": "#9c9c9c",
    "wheel": "#202020",
    "window": "#8bd2d8",
    "warn": "#a46a00",
}


def rounded(ax, x, y, w, h, face, *, edge=None, dashed=False, lw=0.9, radius=0.06):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0.03,rounding_size={radius}",
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


def box3d(ax, x, y, w, h, color, *, depth=0.08, top=None, lw=0.55):
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


def side_truck(ax, x, y, cargo_len, *, scale=1.0, long=False, label=None, annotate=False):
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
        ax.text(x, y + 0.92 * scale, label, fontsize=5.4, fontweight="bold", ha="left", va="center")
    if annotate:
        ax.text(x + cargo_len * 0.34, y + 0.70 * scale, "cargo grows", fontsize=4.6, color=COL["warn"], ha="center")
        ax.text(x + cargo_len + cab_w * 0.55, y + 0.86 * scale, "cab bounded", fontsize=4.6, color=COL["cab"], ha="center")
        ax.text(x + cargo_len * 0.48, y - 0.04 * scale, "wheel radius fixed", fontsize=4.6, color=COL["wheel"], ha="center")


def exploded_truck(ax, x, y):
    ax.text(x, y + 1.08, "compiled primitive parts", fontsize=5.7, fontweight="bold", ha="left")
    box3d(ax, x + 0.02, y + 0.63, 0.78, 0.20, COL["cargo"], depth=0.055, top="#f5d18f")
    ax.text(x + 0.40, y + 0.91, "cargo box", fontsize=4.7, ha="center", color=COL["warn"])
    box3d(ax, x + 1.02, y + 0.54, 0.34, 0.42, COL["cab"], depth=0.05)
    ax.text(x + 1.19, y + 1.03, "cab box", fontsize=4.7, ha="center", color=COL["cab"])
    ax.add_patch(Rectangle((x + 0.02, y + 0.31), 1.40, 0.055, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.35))
    ax.text(x + 0.72, y + 0.42, "chassis", fontsize=4.7, ha="center", color=COL["muted"])
    for wx in [x + 0.16, x + 0.48, x + 1.07, x + 1.27]:
        wheel(ax, wx, y + 0.12, 0.038)
    ax.text(x + 0.72, y - 0.02, "wheel cylinders/tori", fontsize=4.7, ha="center", color=COL["wheel"])


def recipe_row(ax, y, role, primitive, rule, color):
    ax.add_patch(Rectangle((3.04, y - 0.07), 0.15, 0.15, facecolor=color, edgecolor=COL["ink"], linewidth=0.35))
    ax.text(3.25, y, role, fontsize=5.15, fontweight="bold", ha="left", va="center")
    ax.text(4.20, y, primitive, fontsize=5.0, ha="left", va="center")
    ax.text(5.10, y, rule, fontsize=5.0, color=COL["muted"], ha="left", va="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.25, 4.7), dpi=300)
    ax.set_xlim(0, 10.0)
    ax.set_ylim(0, 6.3)
    ax.axis("off")

    ax.text(0.12, 6.08, "SPPA mechanism: language draft -> reviewed parts -> runtime proxy", fontsize=8.2, fontweight="bold", ha="left", va="top")
    ax.text(
        0.12,
        5.82,
        "Language is used only before deployment to draft candidate recipes; runtime uses a reviewed cache entry and telemetry.",
        fontsize=5.2,
        color=COL["muted"],
        ha="left",
        va="top",
    )

    rounded(ax, 0.18, 3.38, 2.36, 2.05, COL["draft"], dashed=True)
    ax.text(0.34, 5.17, "offline candidate", fontsize=6.1, fontweight="bold", ha="left")
    ax.text(0.34, 4.86, 'tag/prompt: "truck"', fontsize=5.5, fontweight="bold", ha="left")
    ax.text(0.34, 4.48, "draft roles:", fontsize=5.0, fontweight="bold", ha="left")
    for i, item in enumerate(["load/cargo volume", "driver cab", "wheels / axles"]):
        ax.text(0.48, 4.18 - i * 0.28, item, fontsize=4.9, ha="left", color=COL["ink"])
    ax.text(0.34, 3.52, "runtime LLM: off", fontsize=5.0, fontweight="bold", color=COL["warn"], ha="left")

    rounded(ax, 2.82, 3.38, 4.42, 2.05, COL["cache"])
    ax.text(3.02, 5.17, "reviewed cache rule z_c", fontsize=6.1, fontweight="bold", ha="left")
    ax.text(3.04, 4.82, "role", fontsize=4.8, fontweight="bold", ha="left")
    ax.text(4.20, 4.82, "primitive", fontsize=4.8, fontweight="bold", ha="left")
    ax.text(5.10, 4.82, "bounded rule", fontsize=4.8, fontweight="bold", ha="left")
    recipe_row(ax, 4.48, "cargo", "box", "length absorbs L change", COL["cargo"])
    recipe_row(ax, 4.16, "cab", "box", "clamped module", COL["cab"])
    recipe_row(ax, 3.84, "wheels", "cyl/torus", "fixed radius; axle rule", COL["wheel"])
    recipe_row(ax, 3.52, "unknown", "volume", "fallback if no reviewed class", "#d9d9d9")

    rounded(ax, 7.52, 3.38, 2.24, 2.05, COL["runtime"])
    ax.text(7.72, 5.17, "runtime fill", fontsize=6.1, fontweight="bold", ha="left")
    ax.text(7.72, 4.82, "input: label + bbox/mask + track", fontsize=4.85, ha="left", color=COL["muted"])
    ax.text(7.72, 4.45, "q_t: part parameters", fontsize=5.0, fontweight="bold", ha="left")
    ax.text(7.72, 4.10, "xi_t: actor pose", fontsize=5.0, fontweight="bold", ha="left")
    ax.text(7.72, 3.74, "update: transforms / part params", fontsize=4.85, ha="left", color=COL["muted"])
    ax.text(7.72, 3.48, "no mesh generator call", fontsize=4.85, fontweight="bold", ha="left", color=COL["warn"])

    arrow(ax, (2.54, 4.38), (2.82, 4.38), dashed=True)
    arrow(ax, (7.24, 4.38), (7.52, 4.38))

    rounded(ax, 0.18, 0.30, 9.58, 2.70, "white")
    ax.text(0.42, 2.72, "Visual consequence: semantic parts adapt by role, not by root-scaling one box", fontsize=6.25, fontweight="bold", ha="left")

    exploded_truck(ax, 0.52, 1.02)
    arrow(ax, (2.12, 1.68), (2.58, 1.68))

    side_truck(ax, 2.80, 1.28, 0.60, scale=0.86, long=False, label="short truck evidence")
    side_truck(ax, 5.02, 1.28, 1.22, scale=0.86, long=True, label="long truck evidence", annotate=False)
    arrow(ax, (4.36, 1.80), (4.90, 1.80))

    ax.text(7.56, 2.36, "same topology cache", fontsize=5.2, fontweight="bold", ha="left")
    ax.text(7.56, 2.05, "pose_update: reuse parts", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(7.56, 1.78, "shape_param_update: edit q_t", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(7.56, 1.51, "topology change: new cache id", fontsize=4.9, color=COL["muted"], ha="left")
    ax.text(5.24, 2.30, "cargo grows", fontsize=4.6, color=COL["warn"], ha="left")
    ax.text(5.96, 0.96, "wheels fixed", fontsize=4.6, color=COL["wheel"], ha="center")
    ax.text(6.35, 2.47, "cab bounded", fontsize=4.6, color=COL["cab"], ha="center")
    ax.text(7.56, 1.15, "claim: bounded proxy", fontsize=5.0, fontweight="bold", color=COL["warn"], ha="left")
    ax.text(7.56, 0.88, "not reconstruction", fontsize=5.0, fontweight="bold", color=COL["warn"], ha="left")

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
