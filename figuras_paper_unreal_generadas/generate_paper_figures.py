from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PIPELINE = REPO / "pipeline"
ZERO_TRUST = PIPELINE / "logs" / "zero_trust"
WAYPOINTS = PIPELINE / "ejea_default.waypoints"

STATIC_RUN = ZERO_TRUST / "20260220_112052"
MOVING_RUN = ZERO_TRUST / "20260612_233504"
PAPER_WP1_WP2_SUMMARY = PIPELINE / "logs" / "paper_wp1_wp2_tower" / "latest_paper_wp1_wp2_tower_summary.json"

STATIC_DETECTION_TS = 1771582926.738
STATIC_EVASION_TS = 1771582930.894
STATIC_COMPLETION_TS = 1771582988.0
MOVING_EVASION_TS = 1781300494.3

RS_M = 12.0
BASE_REACTION_M = 45.0
CELL_SIZE_M = 6.0
GRID_RADIUS_CELLS = 40

INK = "#23313f"
NOMINAL = "#7b8794"
FLOWN = "#3f4a54"
EVASION = "#b4682b"
TOWER = "#b23a2f"
BIKE = "#256f8f"
GRID = "#d4dbe2"

FIG1_XLIM = (-40.0, 160.0)
FIG1_YLIM = (-190.0, 10.0)
FIG1_PANEL_FIGSIZE = (5.8, 5.8)


def parse_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_waypoints() -> list[dict]:
    rows = WAYPOINTS.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[dict] = []
    for line in rows[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        out.append(
            {
                "idx": int(parts[0]),
                "lat": float(parts[8]),
                "lon": float(parts[9]),
                "alt": float(parts[10]),
            }
        )
    return out

def load_wp1_wp2_static_source() -> dict:
    if not PAPER_WP1_WP2_SUMMARY.exists():
        return {}
    summary = json.loads(PAPER_WP1_WP2_SUMMARY.read_text(encoding="utf-8"))
    best = summary.get("best") or {}
    run_dir = best.get("run_dir")
    validation = best.get("validation") or {}
    obstacle = best.get("obstacle") or {}
    if run_dir:
        global STATIC_RUN, STATIC_DETECTION_TS, STATIC_EVASION_TS, STATIC_COMPLETION_TS
        STATIC_RUN = Path(run_dir)
        STATIC_DETECTION_TS = float(validation.get("selected_detection_ts", STATIC_DETECTION_TS))
        STATIC_EVASION_TS = float(validation.get("selected_plan_ts", STATIC_EVASION_TS))
        STATIC_COMPLETION_TS = float(validation.get("selected_completion_ts", STATIC_COMPLETION_TS))
    return {"summary": summary, "best": best, "obstacle": obstacle, "validation": validation}


def latlon_to_enu(lat_ref: float, lon_ref: float, lat: float, lon: float) -> tuple[float, float]:
    north = math.radians(lat - lat_ref) * 6_371_000.0
    east = math.radians(lon - lon_ref) * 6_371_000.0 * max(math.cos(math.radians(lat_ref)), 1e-6)
    return east, north


def valid_traj(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["lat"].abs() > 1.0) & (df["lon"].abs() > 1.0)].copy()


def nearest_row(df: pd.DataFrame, ts: float) -> pd.Series:
    return df.iloc[(df["ts"] - ts).abs().argmin()]


def nearest_event(events: list[dict], ts: float, kind: str, obs_type: str | None = None) -> dict:
    candidates = [e for e in events if e.get("kind") == kind]
    if obs_type is not None:
        obs_type_l = obs_type.lower()

        def has_type(evt: dict) -> bool:
            if str(evt.get("nearest_type", "")).lower() == obs_type_l:
                return True
            for obs in evt.get("outgoing", []) or evt.get("obs_sample", []) or []:
                if str(obs.get("type", "")).lower() == obs_type_l:
                    return True
            return False

        typed = [e for e in candidates if has_type(e)]
        if typed:
            candidates = typed
    return min(candidates, key=lambda e: abs(float(e.get("ts", 0.0)) - ts))


def nearest_archived_frame(run: Path, frame_idx: int) -> Path | None:
    frames = run / "vision" / "frames"
    for delta in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
        p = frames / f"yolo_{frame_idx + delta:06d}.jpg"
        if p.exists():
            return p
    return None


def style_ax(ax) -> None:
    ax.grid(color=GRID, linestyle=":", linewidth=0.75)
    for spine in ax.spines.values():
        spine.set_color("#8a96a3")
        spine.set_linewidth(0.8)
    ax.tick_params(labelsize=7, colors=INK)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East (m)", fontsize=8)
    ax.set_ylabel("North (m)", fontsize=8)

def apply_figure1_view(ax) -> None:
    ax.set_xlim(*FIG1_XLIM)
    ax.set_ylim(*FIG1_YLIM)
    ax.set_aspect("equal", adjustable="box")


def draw_label(ax, panel: str, title: str) -> None:
    ax.text(
        0.015,
        0.98,
        f"{panel}. {title}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color=INK,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.92),
        zorder=100,
    )


def draw_unreal_panel(ax, image_path: Path | None, panel: str, title: str, note: str) -> None:
    ax.axis("off")
    if image_path and image_path.exists():
        ax.imshow(Image.open(image_path).convert("RGB"))
    else:
        ax.text(0.5, 0.5, "Missing Unreal frame", ha="center", va="center", fontsize=12, color=TOWER)
    ax.text(
        0.015,
        0.98,
        f"{panel}. {title}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        color=INK,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.9),
    )
    ax.text(
        0.015,
        0.08,
        note,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=7,
        color=INK,
        bbox=dict(boxstyle="round,pad=0.16", facecolor="white", edgecolor="none", alpha=0.82),
    )


def plot_mission(ax, mission_xy: np.ndarray, label: str = "Nominal path") -> None:
    ax.plot(mission_xy[:, 0], mission_xy[:, 1], "--", color=NOMINAL, linewidth=1.2, label=label, zorder=1)
    plotted_labels: dict[tuple[float, float], list[str]] = {}
    for i, (x, y) in enumerate(mission_xy):
        key = (round(float(x), 1), round(float(y), 1))
        plotted_labels.setdefault(key, []).append("HOME" if i == 0 else f"WP{i}")
    ax.scatter(
        [key[0] for key in plotted_labels],
        [key[1] for key in plotted_labels],
        s=18,
        color="#476f9f",
        zorder=2,
    )
    for (x, y), labels in plotted_labels.items():
        ax.text(x + 7, y + 7, "/".join(labels), fontsize=7, color="#476f9f", zorder=4, clip_on=True)


def mission_xy_for_ref(lat_ref: float, lon_ref: float, mission: list[dict]) -> np.ndarray:
    return np.array([latlon_to_enu(lat_ref, lon_ref, wp["lat"], wp["lon"]) for wp in mission])

def plot_wp1_wp2_segment(ax, mission: list[dict], lat_ref: float, lon_ref: float) -> np.ndarray:
    idxs = [1, 2]
    pts = np.array([latlon_to_enu(lat_ref, lon_ref, mission[i]["lat"], mission[i]["lon"]) for i in idxs])
    ax.plot(pts[:, 0], pts[:, 1], "--", color=NOMINAL, linewidth=1.35, label="Nominal path", zorder=1)
    ax.scatter(pts[:, 0], pts[:, 1], s=22, color="#476f9f", zorder=2)
    for idx, (x, y) in zip(idxs, pts):
        dy = -9 if idx == 1 else 4
        ax.text(x + 4, y + dy, f"WP{idx}", fontsize=7, color="#476f9f", zorder=4, clip_on=True)
    return pts


def obs_xy_from_event(evt: dict, lat_ref: float, lon_ref: float, obs_type: str) -> list[dict]:
    obs = []
    sources = evt.get("obs_sample") or evt.get("outgoing") or []
    for item in sources:
        if str(item.get("type", "")).lower() != obs_type.lower():
            continue
        if item.get("lat") is None or item.get("lon") is None:
            continue
        east, north = latlon_to_enu(lat_ref, lon_ref, float(item["lat"]), float(item["lon"]))
        obs.append(
            {
                "east": east,
                "north": north,
                "distance": float(item.get("distance", float("nan"))),
                "id": item.get("id", "-"),
                "type": obs_type,
            }
        )
    return obs

def obs_xy_from_static_source(static_source: dict, lat_ref: float, lon_ref: float) -> list[dict]:
    obstacle = static_source.get("obstacle") or {}
    if obstacle.get("lat") is None or obstacle.get("lon") is None:
        return []
    east, north = latlon_to_enu(lat_ref, lon_ref, float(obstacle["lat"]), float(obstacle["lon"]))
    return [
        {
            "east": east,
            "north": north,
            "distance": float("nan"),
            "id": "vision:101",
            "type": "tower",
            "lat": float(obstacle["lat"]),
            "lon": float(obstacle["lon"]),
        }
    ]


def draw_obstacles(ax, obs: list[dict], color: str, radius: bool = True, label: str = "Obstacle") -> None:
    first = True
    for item in obs:
        if radius:
            ax.add_patch(
                patches.Circle(
                    (item["east"], item["north"]),
                    RS_M,
                    facecolor=(0.70, 0.18, 0.15, 0.12),
                    edgecolor=color,
                    linewidth=1.0,
                    zorder=4,
                )
            )
        ax.scatter([item["east"]], [item["north"]], marker="x", s=52, color=color, label=label if first else None, zorder=7)
        ax.text(item["east"] + 3, item["north"] + 3, f"{item['type']} {item['distance']:.1f} m", fontsize=7, color=INK, zorder=8)
        first = False


def reconstruct_route(
    start_lat: float,
    start_lon: float,
    wp: dict,
    obs: list[dict],
    output_lat_ref: float | None = None,
    output_lon_ref: float | None = None,
) -> tuple[list[tuple[float, float]], set[tuple[int, int]], list[tuple[int, int]]]:
    import sys

    if str(PIPELINE) not in sys.path:
        sys.path.insert(0, str(PIPELINE))
    from porce_manager import PorcePlanner

    planner = PorcePlanner()
    route = planner.plan_route(
        start_lat,
        start_lon,
        float(wp["lat"]),
        float(wp["lon"]),
        [
            {
                "lat": float(wp_obs["lat"]),
                "lon": float(wp_obs["lon"]),
            }
            for wp_obs in obs
            if "lat" in wp_obs and "lon" in wp_obs
        ],
    )
    xy_lat_ref = start_lat if output_lat_ref is None else output_lat_ref
    xy_lon_ref = start_lon if output_lon_ref is None else output_lon_ref
    route_xy: list[tuple[float, float]] = []
    route_cells: list[tuple[int, int]] = []
    for point in route:
        east, north = latlon_to_enu(xy_lat_ref, xy_lon_ref, float(point["lat"]), float(point["lon"]))
        route_xy.append((east, north))
        local_east, local_north = latlon_to_enu(start_lat, start_lon, float(point["lat"]), float(point["lon"]))
        cell = (int(local_east / planner.cell_size), int(local_north / planner.cell_size))
        if not route_cells or route_cells[-1] != cell:
            route_cells.append(cell)
    safety_cells = max(0, int(math.ceil(float(planner.safety_radius_m) / float(planner.cell_size))))
    occupied: set[tuple[int, int]] = set()
    for wp_obs in obs:
        east, north = latlon_to_enu(start_lat, start_lon, float(wp_obs["lat"]), float(wp_obs["lon"]))
        seed = (int(east / planner.cell_size), int(north / planner.cell_size))
        for dx in range(-safety_cells, safety_cells + 1):
            for dy in range(-safety_cells, safety_cells + 1):
                occupied.add((seed[0] + dx, seed[1] + dy))
    return route_xy, occupied, route_cells


def draw_grid(
    ax,
    occupied: set[tuple[int, int]],
    route_cells: list[tuple[int, int]],
    route_xy: list[tuple[float, float]],
    origin_xy: tuple[float, float] = (0.0, 0.0),
) -> None:
    ox, oy = origin_xy
    half = GRID_RADIUS_CELLS * CELL_SIZE_M
    for v in np.arange(-half, half + CELL_SIZE_M, CELL_SIZE_M):
        is_major = abs((v / CELL_SIZE_M) % 10) < 1e-6
        ax.axvline(ox + v, color="#dfe5eb", linewidth=0.45 if is_major else 0.25, alpha=0.45 if is_major else 0.18, zorder=0)
        ax.axhline(oy + v, color="#dfe5eb", linewidth=0.45 if is_major else 0.25, alpha=0.45 if is_major else 0.18, zorder=0)
    for cx, cy in sorted(occupied):
        ax.add_patch(
            patches.Rectangle(
                (ox + cx * CELL_SIZE_M - CELL_SIZE_M / 2, oy + cy * CELL_SIZE_M - CELL_SIZE_M / 2),
                CELL_SIZE_M,
                CELL_SIZE_M,
                facecolor=(0.25, 0.30, 0.35, 0.16),
                edgecolor="#768290",
                linewidth=0.35,
                zorder=2,
            )
        )
    if route_xy:
        ax.plot([p[0] for p in route_xy], [p[1] for p in route_xy], color=EVASION, linewidth=1.8, zorder=5, label="A* evasion path")

def select_unique_obstacle(obs: list[dict]) -> list[dict]:
    valid = [item for item in obs if math.isfinite(float(item.get("distance", float("nan"))))]
    if valid:
        return [min(valid, key=lambda item: float(item.get("distance", float("inf"))))]
    return obs[:1]

def add_grid_background(ax, origin_xy: tuple[float, float] = (0.0, 0.0)) -> None:
    draw_grid(ax, set(), [], [], origin_xy=origin_xy)

def plot_local_mission(ax, mission: list[dict], lat_ref: float, lon_ref: float, label: str = "Nominal path") -> np.ndarray:
    mission_xy = mission_xy_for_ref(lat_ref, lon_ref, mission)
    plot_mission(ax, mission_xy, label=label)
    return mission_xy

def add_uas(ax, label: str = "UAS") -> None:
    ax.scatter([0], [0], marker="^", s=65, color=INK, zorder=9, label=label)

def prepare_static_context() -> dict:
    static_source = load_wp1_wp2_static_source()
    mission = load_waypoints()
    traj = valid_traj(pd.read_csv(STATIC_RUN / "brain" / "trajectory.csv"))
    brain = parse_jsonl(STATIC_RUN / "brain" / "events.jsonl")

    detect_evt = nearest_event(brain, STATIC_DETECTION_TS, "decision_snapshot", "tower")
    evasion_evt = nearest_event(brain, STATIC_EVASION_TS, "evasion_route_generated", "tower")
    completion_evt = nearest_event(brain, STATIC_COMPLETION_TS, "evasion_completed")
    no_action_events = [
        event
        for event in brain
        if event.get("kind") == "decision_snapshot"
        and event.get("nearest_type") == "tower"
        and event.get("decision_reason") == "distance_above_reaction"
        and float(event.get("ts", 0.0)) < float(evasion_evt["ts"])
    ]
    detection_detail_evt = max(no_action_events, key=lambda event: float(event["ts"])) if no_action_events else detect_evt

    det_row = nearest_row(traj, float(detect_evt["ts"]))
    det_detail_row = nearest_row(traj, float(detection_detail_evt["ts"]))
    eva_row = nearest_row(traj, float(evasion_evt["ts"]))
    completion_row = nearest_row(traj, float(completion_evt["ts"]))

    wp1 = mission[1]
    wp2 = mission[2]
    lat_ref = float(wp1["lat"])
    lon_ref = float(wp1["lon"])
    mission_xy = mission_xy_for_ref(lat_ref, lon_ref, mission)
    traj["east"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[0], axis=1)
    traj["north"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[1], axis=1)

    obs = obs_xy_from_static_source(static_source, lat_ref, lon_ref)
    det_obs = [dict(item) for item in obs]
    det_detail_obs = [dict(item) for item in obs]
    eva_obs = [dict(item) for item in obs]
    if det_obs:
        det_obs[0]["distance"] = float(detect_evt["nearest_distance_m"])
    if det_detail_obs:
        det_detail_obs[0]["distance"] = float(detection_detail_evt["nearest_distance_m"])
    if eva_obs:
        eva_obs[0]["distance"] = float(evasion_evt["nearest_distance_m"])
    raw_obs = [
        {"lat": float(item["lat"]), "lon": float(item["lon"])}
        for item in obs
        if "lat" in item and "lon" in item
    ]
    wp_idx = int(evasion_evt.get("wp_idx", 2) or 2)
    target_wp = mission[min(max(wp_idx, 0), len(mission) - 1)]
    route_xy, occupied, route_cells = reconstruct_route(
        float(eva_row["lat"]),
        float(eva_row["lon"]),
        target_wp,
        raw_obs,
        output_lat_ref=lat_ref,
        output_lon_ref=lon_ref,
    )
    plan_origin_xy = latlon_to_enu(lat_ref, lon_ref, float(eva_row["lat"]), float(eva_row["lon"]))
    detect_xy = latlon_to_enu(lat_ref, lon_ref, float(det_row["lat"]), float(det_row["lon"]))
    detect_detail_xy = latlon_to_enu(lat_ref, lon_ref, float(det_detail_row["lat"]), float(det_detail_row["lon"]))
    completion_xy = latlon_to_enu(lat_ref, lon_ref, float(completion_row["lat"]), float(completion_row["lon"]))
    active = traj[(traj["ts"] >= float(evasion_evt["ts"])) & (traj["ts"] <= float(completion_evt["ts"])) & (traj["evasion_active"] == 1)]
    mid_evasion_row = active.iloc[len(active) // 2] if len(active) else eva_row
    mid_evasion_xy = latlon_to_enu(lat_ref, lon_ref, float(mid_evasion_row["lat"]), float(mid_evasion_row["lon"]))

    return {
        "static_source": static_source,
        "mission": mission,
        "mission_xy": mission_xy,
        "traj": traj,
        "detect_evt": detect_evt,
        "detection_detail_evt": detection_detail_evt,
        "evasion_evt": evasion_evt,
        "completion_evt": completion_evt,
        "det_row": det_row,
        "det_detail_row": det_detail_row,
        "eva_row": eva_row,
        "mid_evasion_row": mid_evasion_row,
        "completion_row": completion_row,
        "det_obs": det_obs,
        "det_detail_obs": det_detail_obs,
        "eva_obs": eva_obs,
        "route_xy": route_xy,
        "occupied": occupied,
        "route_cells": route_cells,
        "plan_origin_xy": plan_origin_xy,
        "detect_xy": detect_xy,
        "detect_detail_xy": detect_detail_xy,
        "mid_evasion_xy": mid_evasion_xy,
        "completion_xy": completion_xy,
        "lat_ref": lat_ref,
        "lon_ref": lon_ref,
        "wp1": wp1,
        "wp2": wp2,
    }


def build_static_figure() -> dict:
    d = prepare_static_context()
    mission = d["mission"]
    traj = d["traj"]
    detect_evt = d["detect_evt"]
    evasion_evt = d["evasion_evt"]
    det_obs = d["det_obs"]
    eva_obs = d["eva_obs"]
    route_xy = d["route_xy"]
    occupied = d["occupied"]
    route_cells = d["route_cells"]
    plan_origin_xy = d["plan_origin_xy"]
    detect_xy = d["detect_xy"]

    fig = plt.figure(figsize=(13.2, 9.0))
    gs = fig.add_gridspec(2, 3, wspace=0.18, hspace=0.24)
    ax1, ax2, ax3, ax4, ax5, ax6 = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(3)]

    def draw_nominal(ax) -> None:
        early = traj[traj["ts"] <= float(detect_evt["ts"]) - 2.0]
        init_row = early.iloc[-1] if len(early) else d["det_row"]
        add_grid_background(ax, origin_xy=plan_origin_xy)
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        init_xy = latlon_to_enu(d["lat_ref"], d["lon_ref"], float(init_row["lat"]), float(init_row["lon"]))
        ax.scatter([init_xy[0]], [init_xy[1]], marker="^", s=65, color=INK, zorder=9, label="UAS")
        draw_label(ax, "1A", "Initial Stages. Nominal Navigation")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=7)

    def draw_detection(ax, panel: str, with_reaction_radii: bool, evt: dict, xy: tuple[float, float], obs: list[dict]) -> None:
        add_grid_background(ax, origin_xy=plan_origin_xy)
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        ax.scatter([xy[0]], [xy[1]], marker="^", s=65, color=INK, zorder=9, label="UAS")
        if with_reaction_radii:
            ax.add_patch(
                patches.Circle(
                    xy,
                    BASE_REACTION_M,
                    fill=False,
                    linestyle="--",
                    edgecolor="#496d8d",
                    linewidth=1.1,
                    label="Base reaction distance",
                )
            )
            ax.add_patch(
                patches.Circle(
                    xy,
                    float(evt["reaction_distance_eval_m"]),
                    fill=False,
                    linestyle=":",
                    edgecolor="#2f5d7c",
                    linewidth=1.2,
                    label="Reaction distance",
                )
            )
        draw_obstacles(ax, obs, TOWER, radius=True, label="Tower detection" if not with_reaction_radii else "Tower")
        draw_label(ax, panel, "Detection Stage. No Safety Action")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=6.8)

    def draw_evasion(ax, panel: str, tower_label: str, uas_xy: tuple[float, float], show_flown: bool = False) -> None:
        draw_grid(ax, occupied, route_cells, route_xy, origin_xy=plan_origin_xy)
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        if show_flown:
            flown = traj[(traj["ts"] >= float(evasion_evt["ts"])) & (traj["ts"] <= float(d["mid_evasion_row"]["ts"]))]
            ax.plot(flown["east"], flown["north"], color=FLOWN, linewidth=1.2, alpha=0.75, label="Flown path")
        ax.scatter([uas_xy[0]], [uas_xy[1]], marker="^", s=65, color=INK, zorder=9, label="UAS")
        draw_obstacles(ax, eva_obs, TOWER, radius=True, label=tower_label)
        draw_label(ax, panel, "Evasion Stage. Safety Action")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=6.8)

    def draw_summary(ax) -> None:
        add_grid_background(ax, origin_xy=plan_origin_xy)
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        ax.plot(traj["east"], traj["north"], color=FLOWN, linewidth=1.0, alpha=0.75, label="Flown path")
        tower_window = traj[(traj["ts"] >= float(evasion_evt["ts"]) - 2) & (traj["ts"] <= float(d["completion_evt"]["ts"]) + 2)]
        if len(tower_window):
            ax.plot(tower_window["east"], tower_window["north"], color=EVASION, linewidth=2.0, label="Tower evasion window")
        draw_obstacles(ax, eva_obs, TOWER, radius=True, label="Tower")
        draw_label(ax, "1F", "Final Stage. Route Summary")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=7)

    draw_nominal(ax1)
    draw_detection(ax2, "1B", with_reaction_radii=False, evt=detect_evt, xy=d["detect_xy"], obs=det_obs)
    draw_detection(ax3, "1C", with_reaction_radii=True, evt=d["detection_detail_evt"], xy=d["detect_detail_xy"], obs=d["det_detail_obs"])
    draw_evasion(ax4, "1D", "Tower detection", plan_origin_xy)
    draw_evasion(ax5, "1E", "Tower", d["mid_evasion_xy"], show_flown=True)
    draw_summary(ax6)

    out = OUT / "figure_1_static_tower_multipanel.png"
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "figure": str(out.name),
        "run": str(STATIC_RUN.relative_to(REPO)),
        "detection_event_ts": float(detect_evt["ts"]),
        "evasion_event_ts": float(evasion_evt["ts"]),
        "completion_event_ts": float(d["completion_evt"]["ts"]),
        "obstacle": d["static_source"].get("obstacle", {}),
        "validation": d["static_source"].get("validation", {}),
        "note": "Figure 1 panels are top-down maps over WP1->WP2 with a fixed 200 m x 200 m frame, the planner 81x81 grid overlaid, and a single tower detection.",
    }


def build_moving_figure() -> dict:
    mission = load_waypoints()
    traj = valid_traj(pd.read_csv(MOVING_RUN / "brain" / "trajectory.csv"))
    brain = parse_jsonl(MOVING_RUN / "brain" / "events.jsonl")
    vision = parse_jsonl(MOVING_RUN / "vision" / "events.jsonl")
    route_evt = nearest_event(brain, MOVING_EVASION_TS, "evasion_route_generated", "bike")
    vision_evt = nearest_event(vision, float(route_evt["ts"]), "vision_frame", "bike")
    frame = nearest_archived_frame(MOVING_RUN, int(vision_evt["frame"]))

    row = nearest_row(traj, float(route_evt["ts"]))
    lat_ref = float(row["lat"])
    lon_ref = float(row["lon"])
    mission_xy = mission_xy_for_ref(lat_ref, lon_ref, mission)
    traj["east"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[0], axis=1)
    traj["north"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[1], axis=1)

    snapshots = []
    for evt in vision:
        if evt.get("kind") != "vision_frame":
            continue
        t_rel = float(evt.get("ts", 0.0)) - float(route_evt["ts"])
        if -1.5 <= t_rel <= 4.0:
            for obs in evt.get("outgoing", []) or []:
                if str(obs.get("type", "")).lower() not in {"bike", "biker"}:
                    continue
                if obs.get("lat") is None or obs.get("lon") is None:
                    continue
                east, north = latlon_to_enu(lat_ref, lon_ref, float(obs["lat"]), float(obs["lon"]))
                snapshots.append({"east": east, "north": north, "t": t_rel, "distance": float(obs.get("distance", 0.0) or 0.0)})

    fig = plt.figure(figsize=(13.2, 4.3))
    gs = fig.add_gridspec(1, 3, wspace=0.22)
    ax1, ax2, ax3 = [fig.add_subplot(gs[0, i]) for i in range(3)]

    draw_unreal_panel(
        ax1,
        frame,
        "2A",
        "Moving Obstacle Detection",
        f"peloton/biker source run; frame {int(vision_evt['frame'])}",
    )

    plot_mission(ax2, mission_xy)
    local = traj[(traj["ts"] >= float(route_evt["ts"]) - 6) & (traj["ts"] <= float(route_evt["ts"]) + 25)]
    ax2.plot(local["east"], local["north"], color=FLOWN, linewidth=1.2, label="UAS path")
    if snapshots:
        sc = ax2.scatter([s["east"] for s in snapshots], [s["north"] for s in snapshots], c=[s["t"] for s in snapshots], cmap="viridis", s=28, marker="x", label="Peloton ghost positions", zorder=8)
        plt.colorbar(sc, ax=ax2, fraction=0.045, pad=0.02).set_label("t rel. (s)", fontsize=7)
    draw_label(ax2, "2B", "UAS and Peloton Motion")
    style_ax(ax2)
    ax2.legend(loc="lower right", fontsize=7)

    plot_mission(ax3, mission_xy)
    ax3.plot(local["east"], local["north"], color=FLOWN, linewidth=1.0, alpha=0.7, label="Flown path")
    active = local[local["evasion_active"] == 1]
    if len(active):
        ax3.plot(active["east"], active["north"], color=EVASION, linewidth=2.0, label="PORCE active")
    if snapshots:
        sc2 = ax3.scatter([s["east"] for s in snapshots], [s["north"] for s in snapshots], c=[s["t"] for s in snapshots], cmap="viridis", s=18, marker="x", alpha=0.7, zorder=7)
    draw_label(ax3, "2C", "Moving Obstacle Evasion Summary")
    style_ax(ax3)
    ax3.legend(loc="lower right", fontsize=7)

    out = OUT / "figure_2_moving_peloton_multipanel.png"
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    if frame:
        shutil.copyfile(frame, OUT / "figure_2A_moving_peloton_unreal_source.jpg")
    return {
        "figure": str(out.name),
        "run": str(MOVING_RUN.relative_to(REPO)),
        "route_event_ts": float(route_evt["ts"]),
        "frame": frame.name if frame else None,
        "snapshots": len(snapshots),
    }


def copy_reference_assets() -> list[str]:
    copied = []
    refs = [
        REPO
        / "historico"
        / "2026-06-16_porce_pre_porce_last"
        / "paper"
        / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
        / "figures"
        / "porce_six_stage_sequence.png",
        REPO
        / "historico"
        / "2026-06-16_porce_pre_porce_last"
        / "paper"
        / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
        / "figures"
        / "porce_yolo_future_overlay.png",
    ]
    for src in refs:
        if src.exists():
            dst = OUT / f"reference_historical_{src.name}"
            shutil.copyfile(src, dst)
            copied.append(dst.name)
    return copied


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "figure_1": build_static_figure(),
        "figure_2": build_moving_figure(),
        "reference_assets": copy_reference_assets(),
        "script_note": "Generated from local audited logs and archived Unreal/vision frames. Review unresolved paper decisions before replacing final LaTeX assets.",
    }
    (OUT / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    readme = [
        "# Figuras generadas para el paper Unreal/PORCE",
        "",
        "Esta carpeta contiene las figuras compuestas pedidas en la conversacion.",
        "",
        "## Archivos principales",
        "",
        "- `figure_1_static_tower_multipanel.png`: Figura 1, caso estatico con torre, paneles 1A-1F, todos en vista cenital.",
        "- `figure_1_panels/`: los seis paneles de Figura 1 por separado, recomendados para componer la figura final manualmente.",
        "- `figure_2_moving_peloton_multipanel.png`: Figura 2 provisional, obstaculo movil tipo peloton/biker, paneles 2A-2C.",
        "- `manifest.json`: trazabilidad de runs, timestamps y frames fuente.",
        "- `generate_figure1_separate_panels.py`: regenerador de los seis paneles separados de Figura 1.",
        "- `reference_historical_porce_six_stage_sequence.png`: figura historica de seis paneles generada por `generate_paper_assets.py`.",
        "- `reference_historical_porce_yolo_future_overlay.png`: figura historica de overlay YOLO/futuro.",
        "",
        "## Lectura critica",
        "",
        "- `tools/make_viz_gif_manual.py` no crea el multipanel: crea un GIF a partir de `pipeline/logs/viz_frames/frame_*.png`.",
        "- El multipanel historico se generaba en `generate_paper_assets.py`, funcion `build_six_stage_sequence_figure(...)`.",
        "- La Figura 1 generada aqui usa un episodio continuo con torre del run `20260220_112052`; todos los paneles corresponden a la misma torre y se ordenan como secuencia temporal.",
        "- Orden activo de lectura: `1A` navegacion nominal, `1B` deteccion sin accion, `1C` detalle de deteccion con radios, `1D` evasion activa, `1E` detalle/grid de evasion, `1F` resumen final de ruta.",
        "- Decision actual: los seis paneles de Figura 1 deben ser cenitales/top-down, con el grid real `81 x 81` superpuesto y deteccion unica de torre. `1B` y `1C` ya no deben ser capturas oblicuas Unreal/HUD.",
        "- Los seis paneles usan el mismo encuadre fijo activo: eje X `[-200, 400]` m y eje Y `[-400, 200]` m, con las mismas etiquetas `East (m)` y `North (m)`. Es un encuadre cuadrado `1:1` centrado para aprovechar la diagonal `WP0/WP1` a `WP4`.",
        "- La version amplia anterior se conserva como contexto en `figure_1_panels_wide_context/`, `figure_1_static_tower_multipanel_wide_context.png` y `figure_1_panels_contact_sheet_wide_context.png`.",
        "- La version cercana anterior se conserva como contexto en `figure_1_panels_close_context/`, `figure_1_static_tower_multipanel_close_context.png` y `figure_1_panels_contact_sheet_close_context.png`.",
    ]
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
