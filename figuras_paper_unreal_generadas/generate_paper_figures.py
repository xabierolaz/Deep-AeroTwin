from __future__ import annotations

import json
import math
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
GRID_MAJOR_STRIDE_CELLS = 3
GRID_DISPLAY_MAJOR_CELLS = 15
GRID_DISPLAY_CELLS = GRID_MAJOR_STRIDE_CELLS * GRID_DISPLAY_MAJOR_CELLS

INK = "#23313f"
NOMINAL = "#7b8794"
FLOWN = "#3f4a54"
EVASION = "#b4682b"
TOWER = "#b23a2f"
BIKE = "#256f8f"
GRID = "#d4dbe2"

LABEL_PLANNED_PATH = "Planned flight path"
LABEL_ACTUAL_TRAJECTORY = "Actual UAS trajectory"
LABEL_LOCAL_EVASION_PATH = "Local A* evasion path"
LABEL_ACTIVE_EVASION = "Active evasion segment"
LABEL_UAS = "UAS"
LABEL_DETECTED_TOWER = "Detected tower obstacle"
LABEL_TOWER = "Tower obstacle"
LABEL_DYNAMIC_REACTION = "Dynamic reaction distance"
LABEL_BASE_REACTION = "Base reaction distance"
LABEL_PELOTON_POSITIONS = "Peloton positions over time"
LABEL_LOCAL_GRID = "Local A* occupancy grid"

FIG1_XLIM = (-100.0, 200.0)
FIG1_YLIM = (-230.0, 70.0)
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


def style_ax(ax, *, map_grid: bool = True) -> None:
    if map_grid:
        ax.grid(color=GRID, linestyle=":", linewidth=0.75)
    else:
        ax.grid(False)
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


def plot_mission(ax, mission_xy: np.ndarray, label: str = LABEL_PLANNED_PATH) -> None:
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
    ax.plot(pts[:, 0], pts[:, 1], "--", color=NOMINAL, linewidth=1.35, label=LABEL_PLANNED_PATH, zorder=1)
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


def _route_graph_points(
    route_xy: list[tuple[float, float]],
    route_cells: list[tuple[int, int]],
    origin_xy: tuple[float, float],
) -> list[tuple[float, float]]:
    ox, oy = origin_xy
    if route_xy:
        points = []
        for x, y in route_xy:
            gx = ox + round((x - ox) / CELL_SIZE_M) * CELL_SIZE_M
            gy = oy + round((y - oy) / CELL_SIZE_M) * CELL_SIZE_M
            points.append((gx, gy))
    else:
        points = [(ox + cx * CELL_SIZE_M, oy + cy * CELL_SIZE_M) for cx, cy in route_cells]
    out: list[tuple[float, float]] = []
    for point in points:
        if not out or point != out[-1]:
            out.append(point)
    return out


def _grid_display_window(
    route_graph_xy: list[tuple[float, float]],
    occupied: set[tuple[int, int]],
    origin_xy: tuple[float, float],
) -> tuple[int, int, int, int]:
    ox, oy = origin_xy
    content_cells = list(occupied)
    content_cells.extend(
        (
            int(round((x - ox) / CELL_SIZE_M)),
            int(round((y - oy) / CELL_SIZE_M)),
        )
        for x, y in route_graph_xy
    )
    if content_cells:
        min_content_x = min(cx for cx, _ in content_cells) - GRID_MAJOR_STRIDE_CELLS
        max_content_x = max(cx for cx, _ in content_cells) + GRID_MAJOR_STRIDE_CELLS
        min_content_y = min(cy for _, cy in content_cells) - GRID_MAJOR_STRIDE_CELLS
        max_content_y = max(cy for _, cy in content_cells) + GRID_MAJOR_STRIDE_CELLS
        center_x = int(round((min_content_x + max_content_x) / 2))
        center_y = int(round((min_content_y + max_content_y) / 2))
    else:
        center_x = 0
        center_y = 0
        min_content_x = max_content_x = min_content_y = max_content_y = 0

    span = max(
        GRID_DISPLAY_CELLS,
        max_content_x - min_content_x,
        max_content_y - min_content_y,
    )
    span = int(math.ceil(span / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS)
    min_cell_x = int(math.floor((center_x - span / 2) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS)
    min_cell_y = int(math.floor((center_y - span / 2) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS)
    max_cell_x = min_cell_x + span
    max_cell_y = min_cell_y + span

    if min_cell_x > min_content_x:
        shift = math.ceil((min_cell_x - min_content_x) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
        min_cell_x -= shift
        max_cell_x -= shift
    if max_cell_x < max_content_x:
        shift = math.ceil((max_content_x - max_cell_x) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
        min_cell_x += shift
        max_cell_x += shift
    if min_cell_y > min_content_y:
        shift = math.ceil((min_cell_y - min_content_y) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
        min_cell_y -= shift
        max_cell_y -= shift
    if max_cell_y < max_content_y:
        shift = math.ceil((max_content_y - max_cell_y) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
        min_cell_y += shift
        max_cell_y += shift

    return min_cell_x, max_cell_x, min_cell_y, max_cell_y


def _snap_cell_to_display_grid(cell: int, min_cell: int) -> int:
    offset = round((cell - min_cell) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
    return min_cell + offset


def _snap_route_to_display_grid(
    route_graph_xy: list[tuple[float, float]],
    origin_xy: tuple[float, float],
    min_cell_x: int,
    min_cell_y: int,
) -> list[tuple[float, float]]:
    ox, oy = origin_xy
    out: list[tuple[float, float]] = []
    for x, y in route_graph_xy:
        cell_x = int(round((x - ox) / CELL_SIZE_M))
        cell_y = int(round((y - oy) / CELL_SIZE_M))
        snapped_x = _snap_cell_to_display_grid(cell_x, min_cell_x)
        snapped_y = _snap_cell_to_display_grid(cell_y, min_cell_y)
        point = (ox + snapped_x * CELL_SIZE_M, oy + snapped_y * CELL_SIZE_M)
        if not out or point != out[-1]:
            out.append(point)
    return out


def _display_block_for_cell(cell: tuple[int, int], min_cell_x: int, min_cell_y: int) -> tuple[int, int]:
    cx, cy = cell
    bx = min_cell_x + math.floor((cx - min_cell_x) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
    by = min_cell_y + math.floor((cy - min_cell_y) / GRID_MAJOR_STRIDE_CELLS) * GRID_MAJOR_STRIDE_CELLS
    return int(bx), int(by)


def _display_grid_cell_for_xy(xy: tuple[float, float], grid_spec: dict) -> tuple[int, int]:
    ox, oy = grid_spec["origin_xy"]
    cell_x = int(round((xy[0] - ox) / CELL_SIZE_M))
    cell_y = int(round((xy[1] - oy) / CELL_SIZE_M))
    snapped_x = _snap_cell_to_display_grid(cell_x, int(grid_spec["min_cell_x"]))
    snapped_y = _snap_cell_to_display_grid(cell_y, int(grid_spec["min_cell_y"]))
    snapped_x = min(max(snapped_x, int(grid_spec["min_cell_x"])), int(grid_spec["max_cell_x"]))
    snapped_y = min(max(snapped_y, int(grid_spec["min_cell_y"])), int(grid_spec["max_cell_y"]))
    return snapped_x, snapped_y


def _bresenham_indices(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    out: list[tuple[int, int]] = []
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return out


def _display_grid_path_cells(start_cell: tuple[int, int], end_cell: tuple[int, int], grid_spec: dict) -> list[tuple[int, int]]:
    stride = GRID_MAJOR_STRIDE_CELLS
    min_cell_x = int(grid_spec["min_cell_x"])
    min_cell_y = int(grid_spec["min_cell_y"])
    start_idx = ((start_cell[0] - min_cell_x) // stride, (start_cell[1] - min_cell_y) // stride)
    end_idx = ((end_cell[0] - min_cell_x) // stride, (end_cell[1] - min_cell_y) // stride)
    return [(min_cell_x + ix * stride, min_cell_y + iy * stride) for ix, iy in _bresenham_indices(start_idx, end_idx)]


def _cells_to_xy(cells: list[tuple[int, int]], origin_xy: tuple[float, float]) -> list[tuple[float, float]]:
    ox, oy = origin_xy
    return [(ox + cx * CELL_SIZE_M, oy + cy * CELL_SIZE_M) for cx, cy in cells]


def draw_grid(
    ax,
    occupied: set[tuple[int, int]],
    route_cells: list[tuple[int, int]],
    route_xy: list[tuple[float, float]],
    origin_xy: tuple[float, float] = (0.0, 0.0),
) -> dict:
    ox, oy = origin_xy
    route_graph_xy_raw = _route_graph_points(route_xy, route_cells, origin_xy)
    min_cell_x, max_cell_x, min_cell_y, max_cell_y = _grid_display_window(route_graph_xy_raw, occupied, origin_xy)
    route_graph_xy = _snap_route_to_display_grid(route_graph_xy_raw, origin_xy, min_cell_x, min_cell_y)
    grid_spec = {
        "origin_xy": origin_xy,
        "min_cell_x": min_cell_x,
        "max_cell_x": max_cell_x,
        "min_cell_y": min_cell_y,
        "max_cell_y": max_cell_y,
    }
    min_x, max_x = ox + min_cell_x * CELL_SIZE_M, ox + max_cell_x * CELL_SIZE_M
    min_y, max_y = oy + min_cell_y * CELL_SIZE_M, oy + max_cell_y * CELL_SIZE_M
    ax.add_patch(
        patches.Rectangle(
            (min_x, min_y),
            max_x - min_x,
            max_y - min_y,
            facecolor=(0.91, 0.95, 0.98, 0.11),
            edgecolor="#7d8da0",
            linewidth=0.9,
            zorder=-1,
        )
    )
    for cell_x in range(min_cell_x, max_cell_x + 1, GRID_MAJOR_STRIDE_CELLS):
        x = ox + cell_x * CELL_SIZE_M
        ax.plot([x, x], [min_y, max_y], color="#9fb0c0", linewidth=0.62, alpha=0.68, zorder=0)
    for cell_y in range(min_cell_y, max_cell_y + 1, GRID_MAJOR_STRIDE_CELLS):
        y = oy + cell_y * CELL_SIZE_M
        ax.plot([min_x, max_x], [y, y], color="#9fb0c0", linewidth=0.62, alpha=0.68, zorder=0)
    if route_xy or occupied:
        ax.plot([], [], color="#9aa6b2", linewidth=0.8, alpha=0.8, label=LABEL_LOCAL_GRID)
    display_occupied = sorted({_display_block_for_cell(cell, min_cell_x, min_cell_y) for cell in occupied})
    for cx, cy in display_occupied:
        if not (min_cell_x <= cx < max_cell_x and min_cell_y <= cy < max_cell_y):
            continue
        ax.add_patch(
            patches.Rectangle(
                (ox + cx * CELL_SIZE_M, oy + cy * CELL_SIZE_M),
                GRID_MAJOR_STRIDE_CELLS * CELL_SIZE_M,
                GRID_MAJOR_STRIDE_CELLS * CELL_SIZE_M,
                facecolor=(0.25, 0.30, 0.35, 0.16),
                edgecolor="#768290",
                linewidth=0.35,
                zorder=2,
            )
        )
    if route_graph_xy:
        xs = [p[0] for p in route_graph_xy]
        ys = [p[1] for p in route_graph_xy]
        ax.plot(
            xs,
            ys,
            color=EVASION,
            linewidth=2.0,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=6,
            label=LABEL_LOCAL_EVASION_PATH,
        )
        ax.scatter(xs, ys, s=13, facecolor="#fff8ee", edgecolor=EVASION, linewidth=0.65, zorder=7)
        arrow_step = max(1, len(route_graph_xy) // 7)
        for idx in range(0, len(route_graph_xy) - 1, arrow_step):
            ax.add_patch(
                patches.FancyArrowPatch(
                    route_graph_xy[idx],
                    route_graph_xy[idx + 1],
                    arrowstyle="-|>",
                    mutation_scale=7.0,
                    color=EVASION,
                    linewidth=0.75,
                    alpha=0.82,
                    zorder=8,
                    shrinkA=2.0,
                    shrinkB=2.0,
                )
            )
    return grid_spec


def plot_grid_planned_segment(
    ax,
    start_xy: tuple[float, float],
    target_xy: tuple[float, float],
    grid_spec: dict,
    target_label: str = "WP2",
) -> list[tuple[float, float]]:
    start_cell = _display_grid_cell_for_xy(start_xy, grid_spec)
    target_cell = _display_grid_cell_for_xy(target_xy, grid_spec)
    path_cells = _display_grid_path_cells(start_cell, target_cell, grid_spec)
    path_xy = _cells_to_xy(path_cells, grid_spec["origin_xy"])
    xs = [p[0] for p in path_xy]
    ys = [p[1] for p in path_xy]
    ax.plot(xs, ys, "--", color=NOMINAL, linewidth=1.25, zorder=3, label=LABEL_PLANNED_PATH)
    ax.scatter(xs, ys, s=10, facecolor="white", edgecolor=NOMINAL, linewidth=0.55, zorder=4)
    if path_xy:
        target = path_xy[-1]
        ax.scatter([target[0]], [target[1]], s=22, color="#476f9f", zorder=5)
        ax.text(target[0] + 4, target[1] + 4, target_label, fontsize=7, color="#476f9f", zorder=6, clip_on=True)
    return path_xy

def select_unique_obstacle(obs: list[dict]) -> list[dict]:
    valid = [item for item in obs if math.isfinite(float(item.get("distance", float("nan"))))]
    if valid:
        return [min(valid, key=lambda item: float(item.get("distance", float("inf"))))]
    return obs[:1]

def add_grid_background(ax, origin_xy: tuple[float, float] = (0.0, 0.0)) -> None:
    draw_grid(ax, set(), [], [], origin_xy=origin_xy)

def plot_local_mission(ax, mission: list[dict], lat_ref: float, lon_ref: float, label: str = LABEL_PLANNED_PATH) -> np.ndarray:
    mission_xy = mission_xy_for_ref(lat_ref, lon_ref, mission)
    plot_mission(ax, mission_xy, label=label)
    return mission_xy

def add_uas(ax, label: str = LABEL_UAS) -> None:
    ax.scatter([0], [0], marker="^", s=65, color=INK, zorder=9, label=label)

def prepare_static_context() -> dict:
    static_source = load_wp1_wp2_static_source()
    mission = load_waypoints()
    traj = valid_traj(pd.read_csv(STATIC_RUN / "brain" / "trajectory.csv"))
    brain = parse_jsonl(STATIC_RUN / "brain" / "events.jsonl")

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
    detect_evt = no_action_events[-4] if len(no_action_events) >= 4 else nearest_event(brain, STATIC_DETECTION_TS, "decision_snapshot", "tower")
    detection_detail_evt = no_action_events[-2] if len(no_action_events) >= 2 else detect_evt

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
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        init_xy = latlon_to_enu(d["lat_ref"], d["lon_ref"], float(init_row["lat"]), float(init_row["lon"]))
        ax.scatter([init_xy[0]], [init_xy[1]], marker="^", s=65, color=INK, zorder=9, label=LABEL_UAS)
        draw_label(ax, "1A", "Initial Stages. Nominal Navigation")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=7)

    def draw_detection(ax, panel: str, with_reaction_radii: bool, evt: dict, xy: tuple[float, float], obs: list[dict]) -> None:
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        ax.scatter([xy[0]], [xy[1]], marker="^", s=65, color=INK, zorder=9, label=LABEL_UAS)
        if with_reaction_radii:
            ax.add_patch(
                patches.Circle(
                    xy,
                    BASE_REACTION_M,
                    fill=False,
                    linestyle="--",
                    edgecolor="#496d8d",
                    linewidth=1.1,
                    label=LABEL_BASE_REACTION,
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
                    label=LABEL_DYNAMIC_REACTION,
                )
            )
        draw_obstacles(ax, obs, TOWER, radius=True, label=LABEL_DETECTED_TOWER if not with_reaction_radii else LABEL_TOWER)
        draw_label(ax, panel, "Detection Stage. No Safety Action")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=6.8)

    def draw_evasion(ax, panel: str, tower_label: str, uas_xy: tuple[float, float], show_flown: bool = False) -> None:
        grid_spec = draw_grid(ax, occupied, route_cells, route_xy, origin_xy=plan_origin_xy)
        wp2_xy = latlon_to_enu(d["lat_ref"], d["lon_ref"], mission[2]["lat"], mission[2]["lon"])
        plot_grid_planned_segment(ax, plan_origin_xy, wp2_xy, grid_spec)
        if show_flown:
            flown = traj[(traj["ts"] >= float(evasion_evt["ts"])) & (traj["ts"] <= float(d["mid_evasion_row"]["ts"]))]
            ax.plot(flown["east"], flown["north"], color=FLOWN, linewidth=1.2, alpha=0.75, label=LABEL_ACTUAL_TRAJECTORY)
        ax.scatter([uas_xy[0]], [uas_xy[1]], marker="^", s=65, color=INK, zorder=9, label=LABEL_UAS)
        draw_obstacles(ax, eva_obs, TOWER, radius=True, label=tower_label)
        draw_label(ax, panel, "Evasion Stage. Safety Action")
        style_ax(ax, map_grid=False)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=6.8)

    def draw_summary(ax) -> None:
        plot_wp1_wp2_segment(ax, mission, d["lat_ref"], d["lon_ref"])
        ax.plot(traj["east"], traj["north"], color=FLOWN, linewidth=1.45, alpha=0.85, label=LABEL_ACTUAL_TRAJECTORY)
        tower_window = traj[(traj["ts"] >= float(evasion_evt["ts"]) - 2) & (traj["ts"] <= float(d["completion_evt"]["ts"]) + 2)]
        if len(tower_window):
            ax.plot(tower_window["east"], tower_window["north"], color=EVASION, linewidth=1.55, alpha=0.78, label=LABEL_ACTIVE_EVASION)
        draw_obstacles(ax, eva_obs, TOWER, radius=True, label=LABEL_TOWER)
        draw_label(ax, "1F", "Final Stage. Route Summary")
        style_ax(ax)
        apply_figure1_view(ax)
        ax.legend(loc="lower left", fontsize=7)

    draw_nominal(ax1)
    draw_detection(ax2, "1B", with_reaction_radii=False, evt=detect_evt, xy=d["detect_xy"], obs=det_obs)
    draw_detection(ax3, "1C", with_reaction_radii=True, evt=d["detection_detail_evt"], xy=d["detect_detail_xy"], obs=d["det_detail_obs"])
    draw_evasion(ax4, "1D", LABEL_DETECTED_TOWER, plan_origin_xy)
    draw_evasion(ax5, "1E", LABEL_TOWER, d["mid_evasion_xy"], show_flown=True)
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
        "note": "Figure 1 panels are top-down maps over WP1->WP2 with a fixed 200 m x 200 m frame. The local 81x81 A* occupancy grid is shown only after evasion planning starts.",
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
    ax2.plot(local["east"], local["north"], color=FLOWN, linewidth=1.2, label=LABEL_ACTUAL_TRAJECTORY)
    if snapshots:
        sc = ax2.scatter([s["east"] for s in snapshots], [s["north"] for s in snapshots], c=[s["t"] for s in snapshots], cmap="viridis", s=28, marker="x", label=LABEL_PELOTON_POSITIONS, zorder=8)
        plt.colorbar(sc, ax=ax2, fraction=0.045, pad=0.02).set_label("t rel. (s)", fontsize=7)
    draw_label(ax2, "2B", "UAS and Peloton Motion")
    style_ax(ax2)
    ax2.legend(loc="lower right", fontsize=7)

    plot_mission(ax3, mission_xy)
    ax3.plot(local["east"], local["north"], color=FLOWN, linewidth=1.0, alpha=0.7, label=LABEL_ACTUAL_TRAJECTORY)
    active = local[local["evasion_active"] == 1]
    if len(active):
        ax3.plot(active["east"], active["north"], color=EVASION, linewidth=2.0, label=LABEL_ACTIVE_EVASION)
    if snapshots:
        sc2 = ax3.scatter([s["east"] for s in snapshots], [s["north"] for s in snapshots], c=[s["t"] for s in snapshots], cmap="viridis", s=18, marker="x", alpha=0.7, zorder=7)
    draw_label(ax3, "2C", "Moving Obstacle Evasion Summary")
    style_ax(ax3)
    ax3.legend(loc="lower right", fontsize=7)

    out = OUT / "figure_2_moving_peloton_multipanel.png"
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return {
        "figure": str(out.name),
        "run": str(MOVING_RUN.relative_to(REPO)),
        "route_event_ts": float(route_evt["ts"]),
        "frame": frame.name if frame else None,
        "snapshots": len(snapshots),
    }


def main() -> None:
    raise SystemExit(
        "generate_paper_figures.py is a shared context module. "
        "Use generate_final_latex_figures.py and generate_validation_latex_figures.py."
    )


if __name__ == "__main__":
    main()
