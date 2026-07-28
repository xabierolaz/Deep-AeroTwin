from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_to_parts_to_3d_v17.png"

COL = {
    "ink": "#202020",
    "muted": "#5e5e5e",
    "line": "#4a4a4a",
    "tag": "#e8f2ff",
    "llm": "#fff0c9",
    "cache": "#eaf6ec",
    "runtime": "#f2f0ff",
    "cargo": "#efc36b",
    "cab": "#8193ee",
    "chassis": "#a8a8a8",
    "wheel": "#202020",
    "window": "#86d1d6",
    "accent": "#a46a00",
    "reject": "#b24e49",
}


def rounded(ax, x, y, w, h, face, *, edge=None, dashed=False, lw=0.9, radius=0.07):
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


def arrow(ax, start, end, *, dashed=False, lw=1.0, color=None, scale=12):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=scale,
            linewidth=lw,
            color=color or COL["line"],
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=3,
            shrinkB=3,
        )
    )


def box3d(ax, x, y, w, h, color, *, depth=0.07, top=None, lw=0.55):
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=lw))
    ax.add_patch(
        Polygon(
            [(x, y + h), (x + depth, y + h + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=lw * 0.85,
        )
    )
    ax.add_patch(
        Polygon(
            [(x + w, y), (x + w + depth, y + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=lw * 0.85,
        )
    )


def wheel(ax, x, y, r):
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.38))
    ax.add_patch(Circle((x, y), r * 0.40, facecolor="white", edgecolor=COL["ink"], linewidth=0.24))


def truck(ax, x, y, cargo_len, *, scale=1.0, long=False, label=None):
    cab_w = 0.42 * scale
    cab_h = 0.46 * scale
    gap = 0.035 * scale
    body_y = y + 0.31 * scale
    chassis_y = y + 0.17 * scale
    box3d(ax, x, body_y, cargo_len, 0.22 * scale, COL["cargo"], depth=0.055 * scale, top="#f5d090")
    box3d(ax, x + cargo_len + gap, y + 0.26 * scale, cab_w, cab_h, COL["cab"], depth=0.048 * scale)
    ax.add_patch(
        Rectangle(
            (x + cargo_len + gap + 0.16 * scale, y + 0.44 * scale),
            0.085 * scale,
            0.075 * scale,
            facecolor=COL["window"],
            edgecolor=COL["ink"],
            linewidth=0.3,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + 0.02 * scale, chassis_y),
            cargo_len + cab_w + gap + 0.02 * scale,
            0.050 * scale,
            facecolor=COL["chassis"],
            edgecolor=COL["ink"],
            linewidth=0.36,
        )
    )
    wheel_xs = [x + 0.15 * scale, x + max(cargo_len - 0.12 * scale, 0.32 * scale), x + cargo_len + gap + 0.14 * scale, x + cargo_len + gap + 0.33 * scale]
    if long:
        wheel_xs.insert(1, x + cargo_len * 0.55)
    for wx in wheel_xs:
        wheel(ax, wx, y + 0.08 * scale, 0.043 * scale)
    if label:
        ax.text(x, y + 0.82 * scale, label, fontsize=5.6, fontweight="bold", ha="left", va="center")


def role_chip(ax, x, y, color, text, subtext):
    ax.add_patch(Rectangle((x, y), 0.16, 0.16, facecolor=color, edgecolor=COL["ink"], linewidth=0.35))
    ax.text(x + 0.22, y + 0.11, text, fontsize=5.0, fontweight="bold", ha="left", va="center")
    ax.text(x + 0.22, y - 0.10, subtext, fontsize=4.25, color=COL["muted"], ha="left", va="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.35, 3.50), dpi=300)
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 5.6)
    ax.axis("off")

    ax.text(0.12, 5.38, "SPPA: language-assisted part decomposition compiled into deterministic 3D primitives", fontsize=7.8, fontweight="bold", ha="left")
    ax.text(0.12, 5.12, "Language can draft the recipe offline; runtime compiles a reviewed versioned recipe plus telemetry.", fontsize=5.15, color=COL["muted"], ha="left")

    # Stage 1: tag and evidence.
    rounded(ax, 0.12, 3.18, 2.10, 1.52, COL["tag"])
    ax.text(0.30, 4.47, "1  YOLO/word input", fontsize=5.55, fontweight="bold", ha="left")
    rounded(ax, 0.56, 3.98, 1.02, 0.36, "white", lw=0.65)
    ax.text(1.07, 4.16, '"truck"', fontsize=5.30, fontweight="bold", ha="center", va="center")
    ax.add_patch(Rectangle((0.66, 3.49), 0.82, 0.30, facecolor="#f8f9fb", edgecolor=COL["line"], linewidth=0.55))
    ax.text(1.07, 3.64, "bbox / track", fontsize=4.35, color=COL["muted"], ha="center", va="center")

    # Stage 2: language draft.
    rounded(ax, 2.66, 3.18, 2.36, 1.52, COL["llm"], dashed=True)
    ax.text(2.86, 4.47, "2  language-model draft", fontsize=5.65, fontweight="bold", ha="left")
    ax.text(2.92, 4.10, "LM proposes parts(truck):", fontsize=4.55, fontweight="bold", ha="left")
    ax.text(3.10, 3.82, "cargo, cab, chassis", fontsize=4.45, ha="left")
    ax.text(3.10, 3.57, "wheels, windows", fontsize=4.45, ha="left")
    ax.text(2.92, 3.30, "constraints: stretch cargo", fontsize=4.35, color=COL["accent"], ha="left")

    # Stage 3: reviewed versioned recipe.
    rounded(ax, 5.46, 3.18, 3.02, 1.52, COL["cache"])
    ax.text(5.68, 4.47, "3  reviewed recipe z_r", fontsize=5.75, fontweight="bold", ha="left")
    role_chip(ax, 5.78, 4.07, COL["cargo"], "cargo box", "variable length")
    role_chip(ax, 5.78, 3.63, COL["cab"], "cab box", "bounded size")
    role_chip(ax, 7.00, 4.07, COL["wheel"], "wheels", "fixed radius")
    role_chip(ax, 7.00, 3.63, COL["chassis"], "chassis", "axle rule")
    ax.text(5.76, 3.31, "unreviewed -> fallback", fontsize=4.10, color=COL["reject"], ha="left")

    # Stage 4: runtime primitive assembly.
    rounded(ax, 8.92, 3.18, 2.92, 1.52, COL["runtime"])
    ax.text(9.14, 4.47, "4  runtime compiler", fontsize=5.75, fontweight="bold", ha="left")
    ax.text(9.14, 4.16, "no runtime LLM call", fontsize=4.65, color=COL["accent"], fontweight="bold", ha="left")
    box3d(ax, 9.16, 3.72, 0.56, 0.18, COL["cargo"], depth=0.043, top="#f5d090")
    box3d(ax, 9.90, 3.62, 0.28, 0.36, COL["cab"], depth=0.040)
    ax.add_patch(Rectangle((9.16, 3.45), 1.12, 0.045, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.32))
    for wx in [9.26, 9.54, 10.00, 10.20]:
        wheel(ax, wx, 3.31, 0.034)
    arrow(ax, (10.48, 3.63), (10.88, 3.63), lw=0.8, scale=10)
    truck(ax, 10.92, 3.16, 0.46, scale=0.60)

    arrow(ax, (2.22, 3.94), (2.66, 3.94), dashed=True, lw=0.85, scale=11)
    arrow(ax, (5.02, 3.94), (5.46, 3.94), dashed=True, lw=0.85, scale=11)
    arrow(ax, (8.48, 3.94), (8.92, 3.94), lw=0.95, scale=12)

    # Lower visual consequence: semantic part update instead of root scale.
    rounded(ax, 0.12, 0.34, 11.72, 2.34, "white", lw=0.95)
    ax.text(0.38, 2.42, "Visual consequence: the part that carries the evidence changes; other parts keep their role priors", fontsize=6.4, fontweight="bold", ha="left")

    ax.text(0.60, 2.03, "primitive parts", fontsize=5.45, fontweight="bold", ha="left")
    box3d(ax, 0.62, 1.58, 0.86, 0.20, COL["cargo"], depth=0.045, top="#f5d090")
    ax.text(0.64, 1.40, "cargo", fontsize=4.25, color=COL["accent"], ha="left")
    box3d(ax, 1.76, 1.48, 0.30, 0.45, COL["cab"], depth=0.042)
    ax.text(1.70, 1.31, "cab", fontsize=4.25, color=COL["cab"], ha="left")
    ax.add_patch(Rectangle((0.62, 1.07), 1.52, 0.050, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.32))
    for wx in [0.74, 1.16, 1.80, 2.05]:
        wheel(ax, wx, 0.83, 0.043)
    ax.text(0.70, 0.62, "wheel radius fixed", fontsize=4.25, color=COL["ink"], ha="left")

    arrow(ax, (2.42, 1.36), (2.88, 1.36), lw=0.9, scale=12)
    truck(ax, 3.02, 1.02, 0.62, scale=0.90, label="short truck")
    ax.text(3.02, 0.58, "cab and wheels unchanged", fontsize=4.35, color=COL["muted"], ha="left")

    arrow(ax, (4.90, 1.36), (5.36, 1.36), lw=0.9, scale=12)
    truck(ax, 5.56, 1.02, 1.20, scale=0.90, long=True, label="long truck")
    ax.text(5.72, 2.10, "cargo length absorbs L", fontsize=4.70, color=COL["accent"], ha="left")
    ax.text(6.86, 0.58, "extra axle allowed by rule", fontsize=4.35, color=COL["muted"], ha="left")

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
