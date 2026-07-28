from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_model_decomposition_to_3d_v12.png"

COL = {
    "ink": "#222222",
    "muted": "#5b5b5b",
    "line": "#3a3a3a",
    "bg": "#ffffff",
    "input": "#eef4ff",
    "draft": "#fff2c4",
    "cache": "#eef7ed",
    "runtime": "#f4f4f4",
    "cab": "#8598f3",
    "cargo": "#edbd6d",
    "cargo_top": "#f6d69c",
    "chassis": "#8e8e8e",
    "wheel": "#1e1e1e",
    "window": "#82ccd5",
    "accent": "#2f7d46",
    "warn": "#996600",
}


def rounded(ax, x, y, w, h, face, *, edge=None, dashed=False, lw=0.9, radius=0.08):
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


def arrow(ax, start, end, *, dashed=False, label=None, dy=0.14):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.05,
            color=COL["line"],
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=4,
            shrinkB=4,
        )
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2.0,
            (start[1] + end[1]) / 2.0 + dy,
            label,
            fontsize=6.0,
            color=COL["muted"],
            ha="center",
            va="bottom",
        )


def box3d(ax, x, y, w, h, color, *, depth=0.10, top=None):
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=0.6))
    ax.add_patch(
        Polygon(
            [(x, y + h), (x + depth, y + h + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=0.45,
        )
    )
    ax.add_patch(
        Polygon(
            [(x + w, y), (x + w + depth, y + depth * 0.55), (x + w + depth, y + h + depth * 0.55), (x + w, y + h)],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=0.45,
        )
    )


def wheel(ax, x, y, r):
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.45))
    ax.add_patch(Circle((x, y), r * 0.42, facecolor="white", edgecolor=COL["ink"], linewidth=0.32))


def truck(ax, x, y, cargo_len, *, title="", extra_axle=False, scale=1.0):
    cab_w = 0.42 * scale
    cab_h = 0.50 * scale
    gap = 0.04 * scale
    chassis_h = 0.065 * scale
    wheel_r = 0.050 * scale
    box3d(ax, x, y + 0.36 * scale, cargo_len, 0.25 * scale, COL["cargo"], depth=0.07 * scale, top=COL["cargo_top"])
    box3d(ax, x + cargo_len + gap, y + 0.30 * scale, cab_w, cab_h, COL["cab"], depth=0.06 * scale)
    ax.add_patch(
        Rectangle(
            (x + cargo_len + gap + 0.17 * scale, y + 0.50 * scale),
            0.10 * scale,
            0.09 * scale,
            facecolor=COL["window"],
            edgecolor=COL["ink"],
            linewidth=0.35,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + 0.03 * scale, y + 0.23 * scale),
            cargo_len + cab_w + gap,
            chassis_h,
            facecolor=COL["chassis"],
            edgecolor=COL["ink"],
            linewidth=0.45,
        )
    )
    xs = [x + 0.17 * scale, x + max(cargo_len - 0.16 * scale, 0.40 * scale), x + cargo_len + gap + 0.16 * scale, x + cargo_len + gap + 0.34 * scale]
    if extra_axle:
        xs.insert(1, x + cargo_len * 0.58)
    for wx in xs:
        wheel(ax, wx, y + 0.14 * scale, wheel_r)
    if title:
        ax.text(x + (cargo_len + cab_w + gap) / 2.0, y + 0.94 * scale, title, fontsize=6.0, fontweight="bold", ha="center")


def chip(ax, x, y, text, color, w):
    rounded(ax, x, y, w, 0.30, "white", lw=0.6, radius=0.05)
    ax.add_patch(Rectangle((x + 0.05, y + 0.085), 0.13, 0.13, facecolor=color, edgecolor=COL["ink"], linewidth=0.35))
    ax.text(x + 0.23, y + 0.15, text, fontsize=5.7, ha="left", va="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.4, 4.65), dpi=300)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 6.25)
    ax.axis("off")

    ax.text(0.15, 5.88, "SPPA language-to-parts-to-3D path", fontsize=9.2, fontweight="bold", ha="left", va="top")
    ax.text(
        0.15,
        5.60,
        "The language step authors a reviewed recipe offline; runtime only compiles cached parts from telemetry.",
        fontsize=6.0,
        color=COL["muted"],
        ha="left",
        va="top",
    )

    # Runtime input.
    rounded(ax, 0.18, 3.20, 2.00, 1.82, COL["input"], lw=0.9)
    ax.text(0.34, 4.80, "runtime input", fontsize=7.2, fontweight="bold", ha="left", va="top")
    ax.add_patch(Rectangle((0.45, 3.88), 1.22, 0.46, facecolor="white", edgecolor=COL["ink"], linewidth=0.55))
    ax.add_patch(Rectangle((0.66, 4.04), 0.63, 0.15, facecolor="#f7fbff", edgecolor=COL["warn"], linewidth=0.9))
    truck(ax, 0.68, 3.72, 0.36, title="", scale=0.55)
    ax.text(0.36, 3.62, 'label: "truck"', fontsize=6.2, fontweight="bold")
    ax.text(0.36, 3.37, "track, bbox/mask, pose", fontsize=5.8, color=COL["muted"])

    # Offline language recipe.
    rounded(ax, 2.80, 3.10, 2.95, 2.02, COL["draft"], dashed=True, lw=0.9)
    ax.text(2.97, 4.90, "offline LLM / ontology draft", fontsize=7.2, fontweight="bold", ha="left", va="top")
    ax.text(2.97, 4.62, "candidate recipe; then reviewed", fontsize=5.7, color=COL["muted"], ha="left", va="top")
    rounded(ax, 3.10, 3.56, 2.27, 0.78, "white", lw=0.55, radius=0.04)
    recipe = [
        "truck:",
        "  parts = cargo, cab, wheels",
        "  cargo.length = variable",
        "  cab/wheel = fixed priors",
    ]
    for i, line in enumerate(recipe):
        ax.text(3.23, 4.18 - i * 0.16, line, fontsize=5.15, family="monospace", color=COL["ink"], ha="left", va="top")

    chip(ax, 3.02, 3.20, "cargo", COL["cargo"], 0.75)
    chip(ax, 3.92, 3.20, "cab", COL["cab"], 0.62)
    chip(ax, 4.67, 3.20, "wheels", COL["wheel"], 0.82)

    # Reviewed cache.
    rounded(ax, 2.80, 0.92, 2.95, 1.45, COL["cache"], lw=0.9)
    ax.text(2.92, 2.18, "reviewed cache entry", fontsize=7.2, fontweight="bold", ha="left", va="top")
    ax.text(2.92, 1.88, "z_c = vehicle.truck.v03", fontsize=6.3, fontweight="bold", color=COL["ink"], ha="left")
    ax.text(2.92, 1.58, "[ok] allowed primitives", fontsize=5.8, color=COL["accent"], ha="left")
    ax.text(2.92, 1.34, "[ok] part-specific scaling rules", fontsize=5.8, color=COL["accent"], ha="left")
    ax.text(2.92, 1.10, "[ok] no runtime model call", fontsize=5.8, color=COL["accent"], ha="left")

    # Runtime compilation visual.
    rounded(ax, 6.35, 0.78, 3.93, 4.34, COL["runtime"], lw=0.9)
    ax.text(6.52, 4.90, "deterministic 3D compilation", fontsize=7.2, fontweight="bold", ha="left", va="top")
    ax.text(6.52, 4.62, "parts[] become primitive components", fontsize=5.8, color=COL["muted"], ha="left", va="top")

    ax.text(6.55, 4.22, "exploded semantic parts", fontsize=6.1, fontweight="bold", ha="left", va="top")
    box3d(ax, 6.55, 3.55, 0.68, 0.22, COL["cargo"], depth=0.07, top=COL["cargo_top"])
    box3d(ax, 7.43, 3.49, 0.34, 0.42, COL["cab"], depth=0.06)
    ax.add_patch(Rectangle((6.45, 3.24), 1.55, 0.065, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.4))
    for wx in [6.58, 7.02, 7.48, 7.74]:
        wheel(ax, wx, 3.06, 0.043)
    ax.text(8.18, 3.78, "role-labeled", fontsize=5.8, color=COL["muted"], ha="left")
    ax.text(8.18, 3.56, "primitive parts", fontsize=5.8, color=COL["muted"], ha="left")

    ax.text(6.55, 2.72, "short", fontsize=5.9, fontweight="bold", ha="left")
    truck(ax, 6.55, 1.93, 0.58, extra_axle=False)
    ax.text(6.55, 1.58, "long", fontsize=5.9, fontweight="bold", ha="left")
    truck(ax, 6.55, 0.80, 1.06, extra_axle=True)
    ax.plot([8.05, 8.05], [1.91, 2.72], color=COL["cab"], linewidth=1.6)
    ax.plot([8.54, 8.54], [0.78, 1.58], color=COL["cab"], linewidth=1.6)
    ax.text(8.76, 2.20, "same cab prior", fontsize=5.3, color=COL["cab"], ha="left")
    ax.text(8.76, 1.92, "same wheel radius", fontsize=5.3, color=COL["wheel"], ha="left")
    ax.text(8.76, 1.64, "cargo absorbs length", fontsize=5.3, color=COL["warn"], ha="left")

    arrow(ax, (2.18, 4.10), (2.80, 4.10), dashed=True)
    arrow(ax, (4.28, 3.10), (4.28, 2.37), dashed=True, label="review", dy=0.03)
    arrow(ax, (5.75, 1.62), (6.35, 1.62))

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
