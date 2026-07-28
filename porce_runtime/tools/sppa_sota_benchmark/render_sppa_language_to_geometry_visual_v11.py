from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_to_geometry_visual_v11.png"

COL = {
    "ink": "#202020",
    "muted": "#5a5a5a",
    "evidence": "#f3f7ff",
    "draft": "#fff4c8",
    "review": "#eef6ec",
    "runtime": "#f5f5f5",
    "cab": "#8ea1ff",
    "cargo": "#efbd75",
    "cargo_top": "#f7d79e",
    "chassis": "#8d8d8d",
    "wheel": "#1d1d1d",
    "window": "#86d7df",
    "fallback": "#d9d9d9",
    "ok": "#2f7d46",
    "warn": "#9a6b00",
}


def rounded(ax, x, y, w, h, face, *, dashed=False, lw=1.0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.035,rounding_size=0.055",
            linewidth=lw,
            edgecolor=COL["ink"],
            facecolor=face,
            linestyle=(0, (4, 3)) if dashed else "solid",
        )
    )


def arrow(ax, start, end, *, dashed=False, label=None):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.15,
            color=COL["ink"],
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=5,
            shrinkB=5,
        )
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2.0,
            (start[1] + end[1]) / 2.0 + 0.18,
            label,
            fontsize=7.0,
            color=COL["muted"],
            ha="center",
        )


def title(ax, x, y, text):
    ax.text(x, y, text, fontsize=8.2, fontweight="bold", ha="left", va="top")


def small(ax, x, y, text, *, color=None, weight=None, ha="left"):
    ax.text(x, y, text, fontsize=5.7, color=color or COL["muted"], fontweight=weight, ha=ha, va="top")


def wheel(ax, x, y, r):
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.50))
    ax.add_patch(Circle((x, y), r * 0.43, facecolor="white", edgecolor=COL["ink"], linewidth=0.35))


def box3d(ax, x, y, w, h, color, *, depth=0.10, top=None, alpha=1.0):
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=0.65, alpha=alpha))
    ax.add_patch(
        Polygon(
            [(x, y + h), (x + depth, y + h + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=0.45,
            alpha=alpha,
        )
    )
    ax.add_patch(
        Polygon(
            [(x + w, y), (x + w + depth, y + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=0.45,
            alpha=alpha,
        )
    )


def part_node(ax, x, y, label, color, *, w=0.78):
    rounded(ax, x, y, w, 0.32, "white", lw=0.65)
    ax.add_patch(Rectangle((x + 0.06, y + 0.09), 0.14, 0.14, facecolor=color, edgecolor=COL["ink"], linewidth=0.4))
    ax.text(x + 0.26, y + 0.16, label, fontsize=5.8, va="center", ha="left")


def truck_side(ax, x, y, cargo_len, *, label, extra_axle=False):
    cab_w = 0.42
    cab_h = 0.48
    gap = 0.04
    box3d(ax, x, y + 0.35, cargo_len, 0.25, COL["cargo"], depth=0.07, top=COL["cargo_top"])
    box3d(ax, x + cargo_len + gap, y + 0.29, cab_w, cab_h, COL["cab"], depth=0.06)
    ax.add_patch(
        Rectangle(
            (x + cargo_len + gap + 0.17, y + 0.48),
            0.10,
            0.09,
            facecolor=COL["window"],
            edgecolor=COL["ink"],
            linewidth=0.35,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + 0.03, y + 0.22),
            cargo_len + cab_w + gap,
            0.07,
            facecolor=COL["chassis"],
            edgecolor=COL["ink"],
            linewidth=0.45,
        )
    )
    xs = [x + 0.18, x + max(cargo_len - 0.18, 0.42), x + cargo_len + gap + 0.16, x + cargo_len + gap + 0.34]
    if extra_axle:
        xs.insert(1, x + cargo_len * 0.58)
    for wx in xs:
        wheel(ax, wx, y + 0.13, 0.047)
    ax.text(x + (cargo_len + cab_w + gap) / 2.0, y + 0.88, label, fontsize=5.8, fontweight="bold", ha="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.4, 5.6), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.6)
    ax.axis("off")

    rounded(ax, 0.25, 4.12, 2.85, 3.12, COL["evidence"])
    rounded(ax, 3.55, 4.12, 2.85, 3.12, COL["draft"], dashed=True)
    rounded(ax, 0.25, 0.32, 2.85, 3.36, COL["review"])
    rounded(ax, 3.55, 0.32, 6.18, 3.36, COL["runtime"])

    title(ax, 0.42, 7.02, "1. detector evidence")
    small(ax, 0.42, 6.73, "same input as asset backend")
    ax.add_patch(Rectangle((0.55, 5.30), 1.95, 0.92, facecolor="white", edgecolor=COL["ink"], linewidth=0.70))
    ax.add_patch(Rectangle((0.92, 5.56), 1.05, 0.34, facecolor="#f7fbff", edgecolor=COL["warn"], linewidth=1.0))
    truck_side(ax, 0.88, 5.20, 0.58, label="", extra_axle=False)
    ax.text(0.70, 6.07, "YOLO tag: truck", fontsize=6.4, fontweight="bold")
    small(ax, 0.48, 4.97, "track id, confidence, bbox")
    small(ax, 0.48, 4.70, "optional mask / calibrated scale")
    small(ax, 0.48, 4.43, "pose and yaw evidence")

    title(ax, 3.72, 7.02, "2. offline recipe draft")
    small(ax, 3.72, 6.73, "offline only; no runtime LLM")
    rounded(ax, 3.86, 6.10, 1.60, 0.38, "white")
    ax.text(4.66, 6.29, '"truck"', fontsize=8.0, family="monospace", fontweight="bold", ha="center", va="center")
    ax.plot([4.66, 4.66], [6.10, 5.88], color=COL["ink"], linewidth=0.7, linestyle=(0, (3, 2)))
    part_node(ax, 3.82, 5.48, "cab", COL["cab"], w=0.78)
    part_node(ax, 5.20, 5.48, "cargo", COL["cargo"], w=0.92)
    part_node(ax, 3.82, 4.96, "chassis", COL["chassis"], w=1.02)
    part_node(ax, 5.20, 4.96, "wheels", COL["wheel"], w=0.96)
    part_node(ax, 4.43, 4.45, "windows?", COL["window"], w=1.10)
    small(ax, 3.74, 4.30, "candidate part graph + relations", color=COL["ink"])

    arrow(ax, (2.98, 5.66), (3.55, 5.66), dashed=True)
    arrow(ax, (4.96, 4.10), (2.96, 3.68), dashed=True)

    title(ax, 0.42, 3.42, "3. reviewed cache")
    small(ax, 0.42, 3.12, "z_c = vehicle.truck.v03", color=COL["ink"], weight="bold")
    checks = ["[ok] allowed primitives", "[ok] role-specific rules", "[ok] triangle budget", "[ok] no runtime LLM"]
    y = 2.75
    for item in checks:
        ax.text(0.52, y, item, fontsize=5.9, color=COL["ok"], ha="left", va="top")
        y -= 0.34
    ax.add_patch(Rectangle((0.52, 0.75), 2.12, 0.74, facecolor="white", edgecolor="#d0d0d0", linewidth=0.55))
    ax.text(0.64, 1.28, "cargo: length absorbs delta", fontsize=5.8, color=COL["ink"])
    ax.text(0.64, 1.06, "cab: bounded dimensions", fontsize=5.8, color=COL["ink"])
    ax.text(0.64, 0.84, "wheel: fixed radius rule", fontsize=5.8, color=COL["ink"])

    arrow(ax, (3.10, 2.00), (3.55, 2.00))

    title(ax, 3.72, 3.42, "4. compile to 3D primitive parts")
    small(ax, 3.72, 3.14, "parts[] -> primitive actor")
    small(ax, 3.72, 2.94, "pose/material can update per frame")
    ax.add_patch(Rectangle((3.85, 2.05), 2.16, 0.54, facecolor="white", edgecolor="#d0d0d0", linewidth=0.55))
    ax.text(3.98, 2.40, "parts[]: cargo box, cab box,", fontsize=5.8, color=COL["ink"])
    ax.text(3.98, 2.18, "chassis box, wheel cylinders", fontsize=5.8, color=COL["ink"])

    ax.text(6.34, 2.84, "exploded roles", fontsize=5.9, fontweight="bold")
    box3d(ax, 6.35, 2.36, 0.72, 0.22, COL["cargo"], depth=0.07, top=COL["cargo_top"])
    box3d(ax, 7.34, 2.31, 0.34, 0.44, COL["cab"], depth=0.06)
    ax.add_patch(Rectangle((6.24, 2.08), 1.58, 0.07, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.4))
    for wx in [6.40, 6.88, 7.36, 7.63]:
        wheel(ax, wx, 1.90, 0.045)

    truck_side(ax, 8.16, 2.08, 0.58, label="short")
    truck_side(ax, 8.16, 0.78, 1.02, label="long", extra_axle=True)
    small(ax, 3.72, 0.78, "role-preserving adaptation: cargo/chassis change;", color=COL["ink"])
    small(ax, 3.72, 0.58, "cab dimensions and wheel radius stay bounded", color=COL["ink"])

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
