from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_scale_variants" / "20260702_parametric_parts"
CSV_PATH = DATA_DIR / "truck_same_width_height_part_invariance.csv"
JSON_PATH = DATA_DIR / "parametric_part_invariance_check.json"
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_truck_role_adaptation.png"


ROLE_COLORS = {
    "vehicle_body": "#e7b464",
    "vehicle_cab": "#8da2ff",
    "vehicle_tire": "#1e1e1e",
}


def load_parts() -> dict[str, list[dict[str, float | str]]]:
    by_variant: dict[str, list[dict[str, float | str]]] = defaultdict(list)
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item: dict[str, float | str] = {
                "variant": row["variant"],
                "role": row["material_role"],
                "primitive": row["primitive"],
                "cx": float(row["center_x"]),
                "cy": float(row["center_y"]),
                "cz": float(row["center_z"]),
                "sx": float(row["scale_0"]),
                "sy": float(row["scale_1"]),
                "sz": float(row["scale_2"]),
            }
            by_variant[str(item["variant"])].append(item)
    return by_variant


def bounds(parts: list[dict[str, float | str]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for part in parts:
        role = str(part["role"])
        cx = float(part["cx"])
        cy = float(part["cy"])
        sx = float(part["sx"])
        sy = float(part["sy"])
        if role == "vehicle_tire":
            radius = sx
            xs.extend([cx - radius, cx + radius])
            ys.extend([cy - radius, cy + radius])
        else:
            xs.extend([cx - sx / 2.0, cx + sx / 2.0])
            ys.extend([cy - sy / 2.0, cy + sy / 2.0])
    return min(xs), max(xs), min(ys), max(ys)


def draw_side(ax, parts: list[dict[str, float | str]], title: str) -> None:
    for part in parts:
        role = str(part["role"])
        cx = float(part["cx"])
        cz = float(part["cz"])
        sx = float(part["sx"])
        sz = float(part["sz"])
        color = ROLE_COLORS.get(role, "#cccccc")
        if role == "vehicle_tire":
            ax.add_patch(Circle((cx, cz), sx, facecolor=color, edgecolor="white", linewidth=0.9))
            ax.add_patch(Circle((cx, cz), sx * 0.45, facecolor="white", edgecolor=color, linewidth=0.8))
        else:
            ax.add_patch(
                Rectangle(
                    (cx - sx / 2.0, cz - sz / 2.0),
                    sx,
                    sz,
                    facecolor=color,
                    edgecolor="#333333",
                    linewidth=1.1,
                )
            )
    x0, x1, _, _ = bounds(parts)
    ax.plot([x0 - 0.25, x1 + 0.25], [0.1, 0.1], color="#444444", linewidth=1.0)
    ax.set_title(title, fontsize=8.0, fontweight="bold", pad=2)
    ax.set_aspect("equal")
    ax.set_xlim(x0 - 0.45, x1 + 0.45)
    ax.set_ylim(0.0, 3.1)
    ax.axis("off")


def draw_top(ax, parts: list[dict[str, float | str]]) -> None:
    for part in parts:
        role = str(part["role"])
        cx = float(part["cx"])
        cy = float(part["cy"])
        sx = float(part["sx"])
        sy = float(part["sy"])
        color = ROLE_COLORS.get(role, "#cccccc")
        if role == "vehicle_tire":
            ax.add_patch(Circle((cx, cy), sx * 0.55, facecolor=color, edgecolor="white", linewidth=0.8))
        else:
            ax.add_patch(
                Rectangle(
                    (cx - sx / 2.0, cy - sy / 2.0),
                    sx,
                    sy,
                    facecolor=color,
                    edgecolor="#333333",
                    linewidth=1.1,
                )
            )
    x0, x1, y0, y1 = bounds(parts)
    ax.set_aspect("equal")
    ax.set_xlim(x0 - 0.45, x1 + 0.45)
    ax.set_ylim(y0 - 0.45, y1 + 0.45)
    ax.axis("off")


def draw_metric_box(ax, metrics: dict[str, object]) -> None:
    ax.axis("off")
    lines = [
        "Part-invariance check",
        f"cab delta: {metrics['cab_scale_max_abs_delta']:.3f} m",
        f"tire delta: {metrics['tire_scale_max_abs_delta']:.3f} m",
        f"cargo length: +{metrics['cargo_length_delta_m']:.3f} m",
        f"tire count: {metrics['short_tire_count']} -> {metrics['long_tire_count']}",
        "root scale: not used",
    ]
    ax.text(
        0.0,
        1.0,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=6.8,
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#f6f6f6", edgecolor="#777777", linewidth=0.7),
    )


def add_role_legend(fig) -> None:
    labels = [("cargo changes", ROLE_COLORS["vehicle_body"]), ("cab fixed", ROLE_COLORS["vehicle_cab"]), ("tire fixed", ROLE_COLORS["vehicle_tire"])]
    x = 0.20
    for text, color in labels:
        fig.patches.append(Rectangle((x, 0.885), 0.018, 0.026, transform=fig.transFigure, facecolor=color, edgecolor="#333333", linewidth=0.5))
        fig.text(x + 0.024, 0.888, text, fontsize=7.0, va="bottom", ha="left")
        x += 0.19


def main() -> None:
    parts = load_parts()
    metrics = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(7.4, 3.15), dpi=300)
    grid = fig.add_gridspec(3, 3, height_ratios=[0.70, 0.54, 0.28], width_ratios=[1.0, 1.0, 0.78], hspace=0.05, wspace=0.18)

    ax_short_side = fig.add_subplot(grid[0, 0])
    ax_long_side = fig.add_subplot(grid[0, 1])
    ax_short_top = fig.add_subplot(grid[1, 0])
    ax_long_top = fig.add_subplot(grid[1, 1])
    ax_metrics = fig.add_subplot(grid[:, 2])
    ax_arrow = fig.add_subplot(grid[2, 0:2])

    draw_side(ax_short_side, parts["short"], "short: 5.2 m")
    draw_side(ax_long_side, parts["long"], "long: 8.2 m")
    draw_top(ax_short_top, parts["short"])
    draw_top(ax_long_top, parts["long"])
    draw_metric_box(ax_metrics, metrics)

    ax_arrow.axis("off")
    arrow = FancyArrowPatch((0.25, 0.52), (0.75, 0.52), transform=ax_arrow.transAxes, arrowstyle="-|>", mutation_scale=13, linewidth=1.0, color="#444444")
    ax_arrow.add_patch(arrow)
    ax_arrow.text(0.50, 0.74, "same cab/tire scale; cargo absorbs length", transform=ax_arrow.transAxes, ha="center", va="center", fontsize=7.2)

    # The LaTeX caption explains role colors; keeping the bitmap label-free
    # avoids overlap when the figure is scaled to page width.
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.05)
    print(OUT)


if __name__ == "__main__":
    main()
