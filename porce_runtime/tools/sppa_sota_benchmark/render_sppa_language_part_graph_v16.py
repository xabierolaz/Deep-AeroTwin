from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_language_part_graph_v16.png"

COL = {
    "ink": "#202020",
    "muted": "#5d5d5d",
    "line": "#444444",
    "bg": "#ffffff",
    "tag": "#e9f2ff",
    "llm": "#fff0c8",
    "graph": "#eef7ef",
    "proxy": "#f2f1ff",
    "cargo": "#efc06b",
    "cab": "#8396f2",
    "chassis": "#9c9c9c",
    "wheel": "#202020",
    "window": "#8bd2d8",
    "warn": "#a46a00",
    "reject": "#b5534b",
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


def arrow(ax, start, end, *, dashed=False, color=None, lw=1.0, scale=12):
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


def box3d(ax, x, y, w, h, color, *, depth=0.08, top=None, lw=0.55):
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
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.45))
    ax.add_patch(Circle((x, y), r * 0.42, facecolor="white", edgecolor=COL["ink"], linewidth=0.28))


def side_truck(ax, x, y, cargo_len, *, scale=1.0, long=False, label=None):
    cab_w = 0.44 * scale
    cab_h = 0.48 * scale
    gap = 0.035 * scale
    wheel_r = 0.048 * scale
    chassis_y = y + 0.20 * scale
    box3d(ax, x, y + 0.34 * scale, cargo_len, 0.24 * scale, COL["cargo"], depth=0.06 * scale, top="#f5d18f")
    box3d(ax, x + cargo_len + gap, y + 0.29 * scale, cab_w, cab_h, COL["cab"], depth=0.052 * scale)
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
    wheel_xs = [x + 0.15 * scale, x + max(cargo_len - 0.13 * scale, 0.34 * scale), x + cargo_len + gap + 0.15 * scale, x + cargo_len + gap + 0.34 * scale]
    if long:
        wheel_xs.insert(1, x + cargo_len * 0.55)
    for wx in wheel_xs:
        wheel(ax, wx, y + 0.11 * scale, wheel_r)
    if label:
        ax.text(x, y + 0.91 * scale, label, fontsize=5.8, fontweight="bold", ha="left", va="center")


def node(ax, x, y, text, face, *, w=1.18, h=0.52, fontsize=5.2):
    rounded(ax, x - w / 2, y - h / 2, w, h, face, lw=0.75, radius=0.06)
    ax.text(x, y + 0.06, text.split("|")[0], fontsize=fontsize, fontweight="bold", ha="center", va="center")
    if "|" in text:
        ax.text(x, y - 0.14, text.split("|")[1], fontsize=4.4, color=COL["muted"], ha="center", va="center")


def render() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.35, 3.85), dpi=300)
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    ax.text(0.16, 5.78, "SPPA core step: label -> language draft -> part graph -> deterministic 3D proxy", fontsize=7.8, fontweight="bold", ha="left", va="top")
    ax.text(
        0.16,
        5.49,
        "The language model is an offline recipe authoring aid; runtime uses only reviewed cached rules and telemetry.",
        fontsize=5.3,
        color=COL["muted"],
        ha="left",
        va="top",
    )

    # Left: detector tag and offline language draft.
    rounded(ax, 0.18, 0.54, 2.72, 4.58, COL["tag"])
    ax.text(0.38, 4.80, "1  tag + LLM draft", fontsize=5.9, fontweight="bold", ha="left")
    rounded(ax, 0.50, 3.83, 1.75, 0.56, "white", lw=0.7)
    ax.text(1.37, 4.13, 'YOLO tag: "truck"', fontsize=5.8, fontweight="bold", ha="center", va="center")
    ax.add_patch(Rectangle((0.82, 2.88), 1.25, 0.60, facecolor="#f6f8fa", edgecolor=COL["line"], linewidth=0.7))
    ax.text(1.45, 3.18, "bbox + track", fontsize=5.0, ha="center", va="center", color=COL["muted"])

    rounded(ax, 0.42, 0.95, 2.16, 1.48, COL["llm"], dashed=True)
    ax.text(0.62, 2.23, "language-model draft", fontsize=5.25, fontweight="bold", ha="left")
    ax.text(0.62, 1.92, "truck -> parts:", fontsize=5.05, ha="left")
    ax.text(0.78, 1.66, "cab + cargo", fontsize=4.9, ha="left")
    ax.text(0.78, 1.41, "chassis + wheels", fontsize=4.9, ha="left")
    ax.text(0.78, 1.16, "windows", fontsize=4.9, ha="left")
    ax.text(1.55, 0.72, "offline draft only", fontsize=4.9, fontweight="bold", color=COL["warn"], ha="center")

    # Center: reviewed semantic part graph.
    rounded(ax, 3.22, 0.54, 4.18, 4.58, COL["graph"])
    ax.text(3.44, 4.80, "2  reviewed semantic part graph", fontsize=6.1, fontweight="bold", ha="left")
    ax.text(3.44, 4.50, "cache z_c: accepted roles, primitive type, bounded rule", fontsize=4.75, color=COL["muted"], ha="left")

    root = (5.30, 3.15)
    node(ax, root[0], root[1], "truck|archetype", "white", w=1.18, h=0.56)
    parts = {
        "cargo|box: variable L": (4.18, 3.98, COL["cargo"]),
        "cab|box: bounded": (6.42, 3.98, COL["cab"]),
        "chassis|beam": (4.08, 2.16, COL["chassis"]),
        "wheels|cyl: fixed r": (5.28, 1.62, "white"),
        "windows|thin panels": (6.52, 2.16, COL["window"]),
    }
    for text, (x, y, color) in parts.items():
        arrow(ax, root, (x, y), color="#777777", lw=0.55, scale=8)
        node(ax, x, y, text, color, w=1.34, h=0.56, fontsize=4.95)

    rounded(ax, 3.62, 0.86, 1.48, 0.40, "white", lw=0.6)
    ax.text(4.36, 1.06, "hallucinated part -> reject", fontsize=4.4, color=COL["reject"], ha="center", va="center")
    rounded(ax, 5.46, 0.86, 1.48, 0.40, "white", lw=0.6)
    ax.text(6.20, 1.06, "unknown class -> fallback", fontsize=4.4, color=COL["warn"], ha="center", va="center")

    # Right: primitive-to-3D assembly and parametric update.
    rounded(ax, 7.72, 0.54, 4.10, 4.58, COL["proxy"])
    ax.text(7.94, 4.80, "3  runtime primitive assembly", fontsize=6.0, fontweight="bold", ha="left")
    ax.text(7.94, 4.50, "no runtime LLM; no neural mesh generation", fontsize=4.95, color=COL["warn"], fontweight="bold", ha="left")

    ax.text(8.10, 4.07, "parts -> 3D roles", fontsize=5.3, fontweight="bold", ha="left")
    box3d(ax, 8.10, 3.47, 0.62, 0.18, COL["cargo"], depth=0.045, top="#f5d18f")
    box3d(ax, 8.88, 3.38, 0.26, 0.36, COL["cab"], depth=0.04)
    ax.add_patch(Rectangle((8.10, 3.18), 1.10, 0.045, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.32))
    for wx in [8.20, 8.46, 8.94, 9.12]:
        wheel(ax, wx, 3.00, 0.034)
    arrow(ax, (9.34, 3.38), (9.72, 3.22), lw=0.8, scale=10)

    side_truck(ax, 9.84, 2.82, 0.56, scale=0.70, long=False, label="short")
    side_truck(ax, 9.04, 1.22, 1.15, scale=0.70, long=True, label="long")
    ax.text(7.98, 2.03, "role-specific", fontsize=5.2, fontweight="bold", ha="left")
    ax.text(7.98, 1.76, "update", fontsize=5.2, fontweight="bold", ha="left")
    ax.text(7.98, 1.45, "cargo: length", fontsize=4.55, color=COL["warn"], ha="left")
    ax.text(7.98, 1.20, "cab: bounded", fontsize=4.55, color=COL["cab"], ha="left")
    ax.text(7.98, 0.95, "wheels: fixed r", fontsize=4.55, color=COL["ink"], ha="left")

    arrow(ax, (2.90, 2.96), (3.22, 2.96), dashed=True, lw=1.0)
    arrow(ax, (7.40, 2.96), (7.72, 2.96), lw=1.0)

    ax.text(
        6.0,
        0.20,
        "Claim represented by this figure: SPPA decomposes reviewed labels into bounded semantic primitive roles, not a globally scaled mesh.",
        fontsize=5.0,
        color=COL["muted"],
        ha="center",
        va="bottom",
    )

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    render()
