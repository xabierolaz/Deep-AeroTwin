from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import generate_paper_figures as g


OUT = Path(__file__).resolve().parent / "figure_1_panels"


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _prepare():
    mission = g.load_waypoints()
    traj = g.valid_traj(pd.read_csv(g.STATIC_RUN / "brain" / "trajectory.csv"))
    brain = g.parse_jsonl(g.STATIC_RUN / "brain" / "events.jsonl")
    vision = g.parse_jsonl(g.STATIC_RUN / "vision" / "events.jsonl")

    detect_evt = g.nearest_event(brain, g.STATIC_DETECTION_TS, "decision_snapshot", "tower")
    evasion_evt = g.nearest_event(brain, g.STATIC_EVASION_TS, "evasion_route_generated", "tower")
    detect_vision = g.nearest_event(vision, float(detect_evt["ts"]), "vision_frame", "tower")
    evasion_vision = g.nearest_event(vision, float(evasion_evt["ts"]), "vision_frame", "tower")
    detect_frame = g.nearest_archived_frame(g.STATIC_RUN, int(detect_vision["frame"]))
    evasion_frame = g.nearest_archived_frame(g.STATIC_RUN, int(evasion_vision["frame"]))

    det_row = g.nearest_row(traj, float(detect_evt["ts"]))
    eva_row = g.nearest_row(traj, float(evasion_evt["ts"]))
    lat_ref = float(eva_row["lat"])
    lon_ref = float(eva_row["lon"])
    mission_xy = g.mission_xy_for_ref(lat_ref, lon_ref, mission)
    traj["east"] = traj.apply(lambda r: g.latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[0], axis=1)
    traj["north"] = traj.apply(lambda r: g.latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[1], axis=1)

    det_obs = g.obs_xy_from_event(detect_evt, lat_ref, lon_ref, "tower")
    eva_obs = g.obs_xy_from_event(evasion_vision, lat_ref, lon_ref, "tower")
    raw_tower_obs = [o for o in evasion_vision.get("outgoing", []) if str(o.get("type", "")).lower() == "tower"]
    wp_idx = int(evasion_evt.get("wp_idx", 0) or 0)
    target_wp = mission[min(max(wp_idx, 0), len(mission) - 1)]
    route_xy, occupied, route_cells = g.reconstruct_route(lat_ref, lon_ref, target_wp, raw_tower_obs[:2])

    return {
        "mission_xy": mission_xy,
        "traj": traj,
        "detect_evt": detect_evt,
        "evasion_evt": evasion_evt,
        "det_row": det_row,
        "det_obs": det_obs,
        "eva_obs": eva_obs,
        "route_xy": route_xy,
        "occupied": occupied,
        "route_cells": route_cells,
        "detect_frame": detect_frame,
        "evasion_frame": evasion_frame,
    }


def main() -> None:
    d = _prepare()
    mission_xy = d["mission_xy"]
    traj = d["traj"]

    fig, ax = plt.subplots(figsize=(5.4, 5.7))
    g.plot_mission(ax, mission_xy)
    early = traj[traj["ts"] <= float(d["detect_evt"]["ts"])].head(40)
    if len(early):
        ax.scatter([early["east"].iloc[-1]], [early["north"].iloc[-1]], marker="^", s=60, color=g.INK, zorder=6, label="UAS")
    g.draw_label(ax, "1A", "Initial Stages. Nominal Navigation")
    g.style_ax(ax)
    ax.legend(loc="lower right", fontsize=7)
    _save(fig, "figure_1_1A_initial_nominal_navigation.png")

    fig, ax = plt.subplots(figsize=(6.2, 4.7))
    g.draw_unreal_panel(
        ax,
        d["detect_frame"],
        "1B",
        "Detection Stage. No Safety Action",
        f"tower detected; d={float(d['detect_evt']['nearest_distance_m']):.1f} m > D_react={float(d['detect_evt']['reaction_distance_eval_m']):.1f} m",
    )
    _save(fig, "figure_1_1B_detection_unreal_no_safety_action.png")

    fig, ax = plt.subplots(figsize=(6.2, 4.7))
    g.draw_unreal_panel(
        ax,
        d["evasion_frame"],
        "1C",
        "Evasion Stage. Safety Action",
        f"tower route generated; d={float(d['evasion_evt']['nearest_distance_m']):.1f} m, route={int(d['evasion_evt']['route_points'])} points",
    )
    _save(fig, "figure_1_1C_evasion_unreal_safety_action.png")

    fig, ax = plt.subplots(figsize=(5.4, 5.7))
    g.plot_mission(ax, mission_xy)
    ax.plot(traj["east"], traj["north"], color=g.FLOWN, linewidth=1.0, alpha=0.75, label="Flown path")
    tower_window = traj[(traj["ts"] >= float(d["evasion_evt"]["ts"]) - 10) & (traj["ts"] <= float(d["evasion_evt"]["ts"]) + 70)]
    if len(tower_window):
        ax.plot(tower_window["east"], tower_window["north"], color=g.EVASION, linewidth=2.0, label="Tower evasion window")
    g.draw_obstacles(ax, d["eva_obs"][:2], g.TOWER, radius=True, label="Tower")
    g.draw_label(ax, "1D", "Final Stage. Route Summary")
    g.style_ax(ax)
    ax.legend(loc="lower right", fontsize=7)
    _save(fig, "figure_1_1D_final_route_summary.png")

    fig, ax = plt.subplots(figsize=(5.8, 5.7))
    g.plot_mission(ax, mission_xy)
    det_xy = g.latlon_to_enu(
        float(g.nearest_row(traj, float(d["detect_evt"]["ts"]))["lat"]),
        float(g.nearest_row(traj, float(d["detect_evt"]["ts"]))["lon"]),
        float(d["det_row"]["lat"]),
        float(d["det_row"]["lon"]),
    )
    # Recompute UAS in the same frame used by the rest of the figure.
    eva_ref = g.nearest_row(traj, float(d["evasion_evt"]["ts"]))
    det_xy = g.latlon_to_enu(float(eva_ref["lat"]), float(eva_ref["lon"]), float(d["det_row"]["lat"]), float(d["det_row"]["lon"]))
    ax.scatter([det_xy[0]], [det_xy[1]], marker="^", s=60, color=g.INK, zorder=8, label="UAS")
    ax.add_patch(plt.Circle(det_xy, g.BASE_REACTION_M, fill=False, linestyle="--", edgecolor="#496d8d", linewidth=1.1, label="Base reaction distance"))
    ax.add_patch(plt.Circle(det_xy, float(d["detect_evt"]["reaction_distance_eval_m"]), fill=False, linestyle=":", edgecolor="#2f5d7c", linewidth=1.2, label="Reaction distance"))
    g.draw_obstacles(ax, d["det_obs"][:2], g.TOWER, radius=True, label="Tower")
    g.draw_label(ax, "1E", "Detection Stage. No Safety Action")
    g.style_ax(ax)
    ax.legend(loc="lower right", fontsize=6.8)
    _save(fig, "figure_1_1E_detection_graph_no_safety_action.png")

    fig, ax = plt.subplots(figsize=(5.9, 5.7))
    g.draw_grid(ax, d["occupied"], d["route_cells"], d["route_xy"])
    ax.scatter([0], [0], marker="^", s=65, color=g.INK, zorder=9, label="UAS")
    g.draw_obstacles(ax, d["eva_obs"][:2], g.TOWER, radius=True, label="Tower")
    g.draw_label(ax, "1F", "Evasion Stage. Safety Action")
    g.style_ax(ax)
    ax.set_xlim(-95, 95)
    ax.set_ylim(-95, 95)
    ax.legend(loc="lower right", fontsize=6.8)
    _save(fig, "figure_1_1F_evasion_graph_safety_action.png")

    print(f"generated {len(list(OUT.glob('figure_1_*.png')))} panels in {OUT}")


if __name__ == "__main__":
    main()
