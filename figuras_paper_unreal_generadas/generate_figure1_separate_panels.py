from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

import generate_paper_figures as g

OUT = Path(__file__).resolve().parent / "figure_1_panels"
CONTACT_SHEET = Path(__file__).resolve().parent / "figure_1_panels_contact_sheet.png"


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _make_contact_sheet() -> None:
    files = sorted(OUT.glob("figure_1_*.png"))
    if not files:
        return
    font = ImageFont.load_default()
    thumbs = []
    for path in files:
        img = Image.open(path).convert("RGB")
        img.thumbnail((520, 520), Image.LANCZOS)
        tile = Image.new("RGB", (540, 560), "white")
        draw = ImageDraw.Draw(tile)
        draw.text((8, 8), path.name, fill=(35, 49, 63), font=font)
        tile.paste(img, ((tile.width - img.width) // 2, 28))
        thumbs.append(tile)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 540, rows * 560), "white")
    for idx, tile in enumerate(thumbs):
        sheet.paste(tile, ((idx % cols) * 540, (idx // cols) * 560))
    sheet.save(CONTACT_SHEET)


def _base_panel(ax, d: dict, *, route: bool = False) -> None:
    if route:
        g.draw_grid(ax, d["occupied"], d["route_cells"], d["route_xy"], origin_xy=d["plan_origin_xy"])
    g.plot_wp1_wp2_segment(ax, d["mission"], d["lat_ref"], d["lon_ref"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("figure_1_*.png"):
        old.unlink()

    d = g.prepare_static_context()
    traj = d["traj"]

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    early = traj[traj["ts"] <= float(d["detect_evt"]["ts"]) - 2.0]
    init_row = early.iloc[-1] if len(early) else d["det_row"]
    _base_panel(ax, d)
    init_xy = g.latlon_to_enu(d["lat_ref"], d["lon_ref"], float(init_row["lat"]), float(init_row["lon"]))
    ax.scatter([init_xy[0]], [init_xy[1]], marker="^", s=65, color=g.INK, zorder=9, label=g.LABEL_UAS)
    g.draw_label(ax, "1A", "Initial Stages. Nominal Navigation")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=7)
    _save(fig, "figure_1_1A_initial_nominal_navigation.png")

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    _base_panel(ax, d)
    ax.scatter([d["detect_xy"][0]], [d["detect_xy"][1]], marker="^", s=65, color=g.INK, zorder=9, label=g.LABEL_UAS)
    g.draw_obstacles(ax, d["det_obs"], g.TOWER, radius=True, label=g.LABEL_DETECTED_TOWER)
    g.draw_label(ax, "1B", "Detection Stage. No Safety Action")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=6.8)
    _save(fig, "figure_1_1B_detection_no_safety_action.png")

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    _base_panel(ax, d)
    det_xy = d["detect_detail_xy"]
    ax.scatter([det_xy[0]], [det_xy[1]], marker="^", s=60, color=g.INK, zorder=8, label=g.LABEL_UAS)
    ax.add_patch(
        plt.Circle(
            det_xy,
            g.BASE_REACTION_M,
            fill=False,
            linestyle="--",
            edgecolor="#496d8d",
            linewidth=1.1,
            label=g.LABEL_BASE_REACTION,
        )
    )
    ax.add_patch(
        plt.Circle(
            det_xy,
            float(d["detection_detail_evt"]["reaction_distance_eval_m"]),
            fill=False,
            linestyle=":",
            edgecolor="#2f5d7c",
            linewidth=1.2,
            label=g.LABEL_DYNAMIC_REACTION,
        )
    )
    g.draw_obstacles(ax, d["det_detail_obs"], g.TOWER, radius=True, label=g.LABEL_TOWER)
    g.draw_label(ax, "1C", "Detection Stage. No Safety Action")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=6.8)
    _save(fig, "figure_1_1C_detection_graph_no_safety_action.png")

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    _base_panel(ax, d, route=True)
    ax.scatter([d["plan_origin_xy"][0]], [d["plan_origin_xy"][1]], marker="^", s=65, color=g.INK, zorder=9, label=g.LABEL_UAS)
    g.draw_obstacles(ax, d["eva_obs"], g.TOWER, radius=True, label=g.LABEL_DETECTED_TOWER)
    g.draw_label(ax, "1D", "Evasion Stage. Safety Action")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=6.8)
    _save(fig, "figure_1_1D_evasion_topdown_safety_action.png")

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    _base_panel(ax, d, route=True)
    flown = traj[(traj["ts"] >= float(d["evasion_evt"]["ts"])) & (traj["ts"] <= float(d["mid_evasion_row"]["ts"]))]
    ax.plot(flown["east"], flown["north"], color=g.FLOWN, linewidth=1.2, alpha=0.75, label=g.LABEL_ACTUAL_TRAJECTORY)
    ax.scatter([d["mid_evasion_xy"][0]], [d["mid_evasion_xy"][1]], marker="^", s=65, color=g.INK, zorder=9, label=g.LABEL_UAS)
    g.draw_obstacles(ax, d["eva_obs"], g.TOWER, radius=True, label=g.LABEL_TOWER)
    g.draw_label(ax, "1E", "Evasion Stage. Safety Action")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=6.8)
    _save(fig, "figure_1_1E_evasion_graph_safety_action.png")

    fig, ax = plt.subplots(figsize=g.FIG1_PANEL_FIGSIZE)
    _base_panel(ax, d)
    ax.plot(traj["east"], traj["north"], color=g.FLOWN, linewidth=1.0, alpha=0.75, label=g.LABEL_ACTUAL_TRAJECTORY)
    tower_window = traj[(traj["ts"] >= float(d["evasion_evt"]["ts"]) - 2) & (traj["ts"] <= float(d["completion_evt"]["ts"]) + 2)]
    if len(tower_window):
        ax.plot(tower_window["east"], tower_window["north"], color=g.EVASION, linewidth=2.0, label=g.LABEL_ACTIVE_EVASION)
    g.draw_obstacles(ax, d["eva_obs"], g.TOWER, radius=True, label=g.LABEL_TOWER)
    g.draw_label(ax, "1F", "Final Stage. Route Summary")
    g.style_ax(ax)
    g.apply_figure1_view(ax)
    ax.legend(loc="lower left", fontsize=7)
    _save(fig, "figure_1_1F_final_route_summary.png")

    _make_contact_sheet()
    print(f"generated {len(list(OUT.glob('figure_1_*.png')))} panels in {OUT}")


if __name__ == "__main__":
    main()
