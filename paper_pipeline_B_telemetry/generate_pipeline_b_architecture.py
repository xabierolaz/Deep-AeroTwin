from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUT_DIR = Path(__file__).resolve().parent / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Journal-oriented palette: low saturation, high contrast, and readable in
# grayscale. Flow type is also encoded with line style, not color alone.
COLORS = {
    "ink": "#1f2933",
    "muted": "#52606d",
    "group_fill": "#f7f9fb",
    "group_edge": "#8995a1",
    "box_fill": "#ffffff",
    "box_edge": "#4b5563",
    "semantic": "#1f4e79",
    "control": "#4b635d",
    "dependency": "#7b8794",
    "object": "#f8f1ef",
    "object_edge": "#8a4b42",
    "pilot_fill": "#f6f2f7",
    "pilot_edge": "#6d5a7a",
}


def add_group(ax, xy, wh, title: str):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        facecolor=COLORS["group_fill"],
        edgecolor=COLORS["group_edge"],
        linewidth=1.0,
        zorder=0,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.14,
        y + h - 0.16,
        title,
        ha="left",
        va="top",
        fontsize=8.4,
        weight="bold",
        color=COLORS["ink"],
        zorder=4,
    )


def add_box(
    ax,
    xy,
    wh,
    text: str,
    *,
    fc: str = COLORS["box_fill"],
    ec: str = COLORS["box_edge"],
    lw: float = 0.9,
    fontsize: float = 7.1,
    weight: str = "normal",
):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.035,rounding_size=0.06",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        weight=weight,
        color=COLORS["ink"],
        linespacing=1.08,
        zorder=5,
    )
    return patch


def add_arrow(
    ax,
    start,
    end,
    *,
    color: str,
    lw: float = 1.0,
    style: str = "-",
    rad: float = 0.0,
    ms: float = 10.0,
    z: int = 7,
):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=ms,
        color=color,
        linewidth=lw,
        linestyle=style,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=4,
        shrinkB=4,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def add_label(ax, xy, text: str, *, color=None, fontsize=6.2, ha="center", va="center", weight="normal"):
    ax.text(
        xy[0],
        xy[1],
        text,
        ha=ha,
        va=va,
        fontsize=fontsize,
        color=color or COLORS["muted"],
        weight=weight,
        linespacing=1.05,
        zorder=8,
    )


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    # Single full-width journal figure. The caption, not the artwork, carries
    # the long explanatory title.
    fig, ax = plt.subplots(figsize=(7.25, 4.25), dpi=300)
    ax.set_xlim(0, 12.0)
    ax.set_ylim(0, 6.15)
    ax.axis("off")

    # Groups.
    add_group(ax, (0.25, 0.78), (3.05, 4.92), "A. Real UAV")
    add_group(ax, (3.58, 2.54), (1.55, 2.25), "B. Link")
    add_group(ax, (5.42, 0.78), (2.18, 4.92), "C. Ground backend")
    add_group(ax, (7.92, 0.78), (3.82, 4.92), "D. Digital twin / pilot")

    # Onboard perception.
    add_box(ax, (0.55, 4.34), (1.0, 0.55), "Camera\nframe", fontsize=6.7)
    add_box(ax, (1.95, 4.34), (1.05, 0.55), "YOLO\nobjects", fontsize=6.7)
    add_box(
        ax,
        (0.55, 3.28),
        (1.0, 0.62),
        "UAV pose\nGPS + attitude",
        fontsize=6.45,
    )
    add_box(
        ax,
        (1.86, 3.04),
        (1.14, 0.86),
        "Geometric\nlocalization\nimage ray to\nworld pose",
        fontsize=5.85,
    )
    add_box(
        ax,
        (0.55, 2.03),
        (2.45, 0.58),
        "Observed object\nclass + image position",
        fc=COLORS["object"],
        ec=COLORS["object_edge"],
        fontsize=6.45,
    )
    add_box(
        ax,
        (0.55, 1.06),
        (2.45, 0.5),
        "Real UAV flight state",
        fc="#fbfcfd",
        ec="#b8c4d0",
        fontsize=6.4,
    )

    # Semantic link.
    add_box(
        ax,
        (3.8, 3.28),
        (1.1, 0.98),
        "Semantic packet\n\nclass, ID,\nworld pose,\nvolume, conf.",
        fc="#fffdf7",
        ec=COLORS["semantic"],
        fontsize=5.35,
        lw=1.0,
    )
    add_label(
        ax,
        (4.35, 2.84),
        "no continuous video\non long-range link",
        color=COLORS["semantic"],
        fontsize=5.85,
        weight="bold",
    )

    # Ground backend.
    add_box(ax, (5.77, 4.12), (1.48, 0.66), "Brain API\nentity state", fontsize=6.45)
    add_box(ax, (5.77, 1.35), (1.48, 0.66), "ArduPilot /\nMAVLink", fontsize=6.45)

    # Digital twin and pilot interface.
    add_box(
        ax,
        (8.28, 4.02),
        (2.95, 0.86),
        "Unreal Engine 5 + Cesium\nstatic terrain + dynamic 3D actors",
        fontsize=6.55,
    )
    add_box(
        ax,
        (8.28, 2.86),
        (2.95, 0.62),
        "Live UAV pose + attitude\nsets the virtual viewpoint",
        fontsize=6.35,
    )
    add_box(
        ax,
        (8.52, 1.31),
        (2.45, 0.72),
        "Human pilot\nVR goggles",
        fc=COLORS["pilot_fill"],
        ec=COLORS["pilot_edge"],
        fontsize=6.55,
    )

    # Semantic telemetry path: solid, dark blue.
    add_arrow(ax, (1.55, 4.61), (1.95, 4.61), color=COLORS["semantic"], lw=1.15)
    add_arrow(ax, (2.48, 4.34), (2.48, 3.9), color=COLORS["semantic"], lw=1.05)
    add_arrow(ax, (3.0, 3.47), (3.8, 4.05), color=COLORS["semantic"], lw=1.25, rad=0.02)
    add_arrow(ax, (4.9, 4.05), (5.77, 4.48), color=COLORS["semantic"], lw=1.25, rad=-0.02)
    add_arrow(ax, (7.25, 4.45), (8.28, 4.45), color=COLORS["semantic"], lw=1.25)

    # Local geometric dependencies: thin gray.
    add_arrow(ax, (1.55, 3.59), (1.86, 3.44), color=COLORS["dependency"], lw=0.85, ms=8)
    add_arrow(ax, (1.78, 2.61), (2.18, 3.04), color=COLORS["dependency"], lw=0.85, ms=8)

    # Flight-control and pose loop: dashed, muted green-gray.
    add_arrow(
        ax,
        (6.52, 2.01),
        (8.28, 3.22),
        color=COLORS["control"],
        lw=1.05,
        style="--",
        rad=-0.04,
    )
    add_arrow(ax, (9.76, 4.02), (9.76, 3.48), color=COLORS["dependency"], lw=0.95, ms=8)
    add_arrow(ax, (9.76, 2.86), (9.76, 2.03), color=COLORS["dependency"], lw=0.95, ms=8)
    add_label(ax, (10.78, 2.43), "rendered view", color=COLORS["muted"], fontsize=5.65)
    add_arrow(
        ax,
        (8.52, 1.63),
        (7.25, 1.68),
        color=COLORS["control"],
        lw=1.05,
        style="--",
    )
    add_arrow(
        ax,
        (5.77, 1.58),
        (3.0, 1.28),
        color=COLORS["control"],
        lw=1.0,
        style="--",
        rad=0.02,
    )

    # Legend.
    legend_y = 0.42
    ax.plot([0.55, 0.98], [legend_y, legend_y], color=COLORS["semantic"], lw=1.4)
    add_label(
        ax,
        (1.12, legend_y),
        "semantic object telemetry",
        color=COLORS["semantic"],
        fontsize=5.75,
        ha="left",
    )
    ax.plot([3.55, 3.98], [legend_y, legend_y], color=COLORS["control"], lw=1.15, linestyle="--")
    add_label(
        ax,
        (4.12, legend_y),
        "flight control / pose",
        color=COLORS["control"],
        fontsize=5.75,
        ha="left",
    )
    ax.plot([6.05, 6.48], [legend_y, legend_y], color=COLORS["dependency"], lw=1.0)
    add_label(
        ax,
        (6.62, legend_y),
        "local dependency",
        color=COLORS["muted"],
        fontsize=5.75,
        ha="left",
    )

    fig.tight_layout(pad=0.1)
    for ext in ("pdf", "svg", "png"):
        path = OUT_DIR / f"pipeline_b_architecture.{ext}"
        if ext == "png":
            fig.savefig(path, dpi=420, bbox_inches="tight", facecolor="white")
        else:
            fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
