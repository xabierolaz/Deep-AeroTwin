from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_semantic_recipe_visual_v10.png"

COL = {
    "ink": "#202020",
    "muted": "#555555",
    "pale": "#f7f7f7",
    "draft": "#fff6cc",
    "review": "#eef3ff",
    "runtime": "#eef8ef",
    "cab": "#9da7ff",
    "cargo": "#efbd75",
    "cargo_top": "#f7d79e",
    "chassis": "#8d8d8d",
    "wheel": "#1d1d1d",
    "window": "#8fdce4",
    "fallback": "#d7d7d7",
}


def arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    dashed: bool = False,
    label: str | None = None,
    label_y: float = 0.0,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=18,
            linewidth=1.25,
            color=COL["ink"],
            linestyle=(0, (4, 4)) if dashed else "solid",
            shrinkA=5,
            shrinkB=5,
        )
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2.0,
            (start[1] + end[1]) / 2.0 + label_y,
            label,
            fontsize=7.0,
            color=COL["muted"],
            ha="center",
            va="center",
        )


def rounded(ax, x: float, y: float, w: float, h: float, face: str, *, dashed: bool = False) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.035,rounding_size=0.055",
            linewidth=1.0,
            edgecolor=COL["ink"],
            facecolor=face,
            linestyle=(0, (4, 4)) if dashed else "solid",
        )
    )


def node(ax, x: float, y: float, text: str, color: str, *, w: float = 1.08) -> None:
    rounded(ax, x, y, w, 0.34, "white")
    ax.add_patch(Rectangle((x + 0.07, y + 0.09), 0.16, 0.16, facecolor=color, edgecolor=COL["ink"], linewidth=0.45))
    ax.text(x + 0.29, y + 0.17, text, fontsize=8.4, va="center")


def connector(ax, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.plot(
        [start[0], end[0]],
        [start[1], end[1]],
        color=COL["ink"],
        linewidth=1.0,
        linestyle=(0, (4, 4)),
        alpha=0.75,
        zorder=0,
    )


def wheel(ax, x: float, y: float, r: float) -> None:
    ax.add_patch(Circle((x, y), r, facecolor=COL["wheel"], edgecolor=COL["ink"], linewidth=0.55))
    ax.add_patch(Circle((x, y), r * 0.42, facecolor="white", edgecolor=COL["ink"], linewidth=0.35))


def box3d(ax, x: float, y: float, w: float, h: float, color: str, *, depth: float = 0.10, top: str | None = None) -> None:
    top = top or color
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=COL["ink"], linewidth=0.75))
    ax.add_patch(
        Polygon(
            [
                (x, y + h),
                (x + depth, y + h + depth * 0.55),
                (x + w + depth, y + h + depth * 0.55),
                (x + w, y + h),
            ],
            closed=True,
            facecolor=top,
            edgecolor=COL["ink"],
            linewidth=0.55,
        )
    )
    ax.add_patch(
        Polygon(
            [
                (x + w, y),
                (x + w + depth, y + depth * 0.55),
                (x + w + depth, y + h + depth * 0.55),
                (x + w, y + h),
            ],
            closed=True,
            facecolor=color,
            edgecolor=COL["ink"],
            linewidth=0.55,
        )
    )


def simple_truck(ax, x: float, y: float, cargo_len: float, *, label: str, extra_axle: bool = False) -> None:
    cab_w = 0.48
    cab_h = 0.50
    gap = 0.045

    ax.text(x + (cargo_len + cab_w + gap) / 2.0, y + 0.98, label, fontsize=8.0, fontweight="bold", ha="center")
    box3d(ax, x, y + 0.42, cargo_len, 0.26, COL["cargo"], depth=0.08, top=COL["cargo_top"])
    box3d(ax, x + cargo_len + gap, y + 0.34, cab_w, cab_h, COL["cab"], depth=0.07)
    ax.add_patch(Rectangle((x + cargo_len + gap + 0.18, y + 0.53), 0.12, 0.11, facecolor=COL["window"], edgecolor=COL["ink"], linewidth=0.40))
    ax.add_patch(Rectangle((x + 0.04, y + 0.24), cargo_len + cab_w + gap, 0.085, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.55))

    wheel_xs = [x + 0.22, x + max(cargo_len - 0.20, 0.45), x + cargo_len + gap + 0.17, x + cargo_len + gap + 0.38]
    if extra_axle:
        wheel_xs.insert(1, x + cargo_len * 0.58)
    for wx in wheel_xs:
        wheel(ax, wx, y + 0.17, 0.052)


def primitive_row(ax, x: float, y: float, role: str, primitive: str, rule: str, color: str, *, kind: str = "box") -> None:
    ax.add_patch(Rectangle((x, y), 3.10, 0.52, facecolor="white", edgecolor="#d7d7d7", linewidth=0.55))
    if kind == "wheel":
        wheel(ax, x + 0.22, y + 0.26, 0.075)
    elif kind == "fallback":
        ax.add_patch(Rectangle((x + 0.12, y + 0.17), 0.24, 0.18, facecolor=color, edgecolor=COL["ink"], linewidth=0.50, linestyle=(0, (3, 2))))
    else:
        ax.add_patch(Rectangle((x + 0.10, y + 0.17), 0.28, 0.18, facecolor=color, edgecolor=COL["ink"], linewidth=0.50))
    ax.text(x + 0.52, y + 0.34, role, fontsize=8.2, fontweight="bold", va="center")
    ax.text(x + 0.52, y + 0.14, f"{primitive}; {rule}", fontsize=7.3, color=COL["muted"], va="center")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11.4, 4.80), dpi=300)
    ax.set_xlim(0, 14.4)
    ax.set_ylim(0, 4.55)
    ax.axis("off")

    rounded(ax, 0.18, 0.26, 3.65, 4.05, COL["draft"], dashed=True)
    rounded(ax, 4.38, 0.26, 3.88, 4.05, COL["review"])
    rounded(ax, 8.82, 0.26, 5.28, 4.05, COL["runtime"])

    ax.text(0.38, 3.98, "1. Offline semantic draft", fontsize=11.0, fontweight="bold")
    ax.text(0.38, 3.62, "tag/prompt: truck", fontsize=9.0, color=COL["muted"])
    rounded(ax, 0.52, 3.00, 1.10, 0.46, "white")
    ax.text(1.07, 3.23, "truck", fontsize=13.0, fontweight="bold", family="monospace", ha="center", va="center")
    ax.text(0.38, 2.66, "draft output roles", fontsize=8.7, color=COL["muted"])
    for end in [(0.99, 2.28), (2.52, 2.28), (0.88, 1.60), (2.50, 1.60), (1.66, 1.04)]:
        connector(ax, (1.07, 2.58), end)
    node(ax, 0.36, 2.20, "cargo body", COL["cargo"], w=1.34)
    node(ax, 2.08, 2.20, "cab", COL["cab"], w=0.92)
    node(ax, 0.36, 1.43, "chassis", COL["chassis"], w=1.12)
    node(ax, 1.96, 1.43, "wheels", COL["wheel"], w=1.14)
    node(ax, 1.08, 0.78, "windows?", COL["window"], w=1.24)
    ax.text(0.38, 0.42, "not queried in flight", fontsize=8.0, color=COL["muted"])

    ax.text(4.62, 3.98, "2. Reviewed recipe cache", fontsize=11.0, fontweight="bold")
    ax.text(4.62, 3.62, "z_c = vehicle.truck.v03", fontsize=9.2, family="monospace", fontweight="bold")
    ax.text(4.85, 3.24, "role -> primitive rule", fontsize=8.0, fontweight="bold")
    primitive_row(ax, 4.72, 2.66, "cargo", "box", "absorbs length", COL["cargo"])
    primitive_row(ax, 4.72, 2.04, "cab", "box", "size bounded", COL["cab"])
    primitive_row(ax, 4.72, 1.42, "wheel", "cylinder", "radius fixed", COL["wheel"], kind="wheel")
    primitive_row(ax, 4.72, 0.80, "window", "box cue", "if observed", COL["window"])
    primitive_row(ax, 4.72, 0.28, "unknown", "volume", "fallback only", COL["fallback"], kind="fallback")

    ax.text(9.05, 3.98, "3. Runtime primitive actor", fontsize=11.0, fontweight="bold")
    ax.text(9.05, 3.62, "detection -> cache lookup -> parts[]", fontsize=8.7, color=COL["muted"])

    ax.text(9.10, 3.14, "exploded primitive parts", fontsize=8.6, fontweight="bold")
    box3d(ax, 9.05, 2.62, 1.04, 0.25, COL["cargo"], depth=0.08, top=COL["cargo_top"])
    box3d(ax, 10.38, 2.55, 0.42, 0.48, COL["cab"], depth=0.07)
    ax.add_patch(Rectangle((10.54, 2.73), 0.11, 0.10, facecolor=COL["window"], edgecolor=COL["ink"], linewidth=0.35))
    ax.add_patch(Rectangle((8.98, 2.34), 1.94, 0.09, facecolor=COL["chassis"], edgecolor=COL["ink"], linewidth=0.50))
    for wx in [9.26, 9.86, 10.46, 10.72]:
        wheel(ax, wx, 2.15, 0.055)

    simple_truck(ax, 11.55, 2.35, 0.62, label="short")
    simple_truck(ax, 11.55, 1.12, 1.08, label="long", extra_axle=True)
    ax.text(9.05, 0.76, "no text-to-3D call; no mesh optimization", fontsize=8.2, fontweight="bold")
    ax.text(9.05, 0.50, "cargo/chassis adapt; cab and wheel radius fixed", fontsize=7.9, color=COL["muted"])

    arrow(ax, (3.83, 2.28), (4.38, 2.28), dashed=True)
    arrow(ax, (8.26, 2.28), (8.82, 2.28))

    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
