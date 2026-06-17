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

STATIC_RUN = ZERO_TRUST / "20260218_234222"
MOVING_RUN = ZERO_TRUST / "20260612_233504"

STATIC_DETECTION_TS = 1771454604.4209192
STATIC_EVASION_TS = 1771454651.4736636
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
    ax.scatter(mission_xy[:, 0], mission_xy[:, 1], s=18, color="#476f9f", zorder=2)
    for i, (x, y) in enumerate(mission_xy):
        if i == 0:
            txt = "HOME"
        else:
            txt = f"WP{i}"
        ax.text(x + 7, y + 7, txt, fontsize=7, color="#476f9f", zorder=4)


def mission_xy_for_ref(lat_ref: float, lon_ref: float, mission: list[dict]) -> np.ndarray:
    return np.array([latlon_to_enu(lat_ref, lon_ref, wp["lat"], wp["lon"]) for wp in mission])


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


def reconstruct_route(lat_ref: float, lon_ref: float, wp: dict, obs: list[dict]) -> tuple[list[tuple[float, float]], set[tuple[int, int]], list[tuple[int, int]]]:
    import sys

    if str(PIPELINE) not in sys.path:
        sys.path.insert(0, str(PIPELINE))
    from porce_manager import PorcePlanner

    planner = PorcePlanner()
    route = planner.plan_route(
        lat_ref,
        lon_ref,
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
    route_xy: list[tuple[float, float]] = []
    route_cells: list[tuple[int, int]] = []
    for point in route:
        east, north = latlon_to_enu(lat_ref, lon_ref, float(point["lat"]), float(point["lon"]))
        route_xy.append((east, north))
        cell = (int(east / planner.cell_size), int(north / planner.cell_size))
        if not route_cells or route_cells[-1] != cell:
            route_cells.append(cell)
    safety_cells = max(0, int(math.ceil(float(planner.safety_radius_m) / float(planner.cell_size))))
    occupied: set[tuple[int, int]] = set()
    for wp_obs in obs:
        east, north = latlon_to_enu(lat_ref, lon_ref, float(wp_obs["lat"]), float(wp_obs["lon"]))
        seed = (int(east / planner.cell_size), int(north / planner.cell_size))
        for dx in range(-safety_cells, safety_cells + 1):
            for dy in range(-safety_cells, safety_cells + 1):
                occupied.add((seed[0] + dx, seed[1] + dy))
    return route_xy, occupied, route_cells


def draw_grid(ax, occupied: set[tuple[int, int]], route_cells: list[tuple[int, int]], route_xy: list[tuple[float, float]]) -> None:
    half = GRID_RADIUS_CELLS * CELL_SIZE_M
    for v in np.arange(-half, half + CELL_SIZE_M, CELL_SIZE_M):
        ax.axvline(v, color="#dfe5eb", linewidth=0.35, zorder=0)
        ax.axhline(v, color="#dfe5eb", linewidth=0.35, zorder=0)
    for cx, cy in sorted(occupied):
        ax.add_patch(
            patches.Rectangle(
                (cx * CELL_SIZE_M - CELL_SIZE_M / 2, cy * CELL_SIZE_M - CELL_SIZE_M / 2),
                CELL_SIZE_M,
                CELL_SIZE_M,
                facecolor=(0.25, 0.30, 0.35, 0.16),
                edgecolor="#768290",
                linewidth=0.35,
                zorder=2,
            )
        )
    for cx, cy in route_cells:
        ax.add_patch(
            patches.Rectangle(
                (cx * CELL_SIZE_M - CELL_SIZE_M / 2, cy * CELL_SIZE_M - CELL_SIZE_M / 2),
                CELL_SIZE_M,
                CELL_SIZE_M,
                facecolor=(0.72, 0.42, 0.16, 0.20),
                edgecolor=EVASION,
                linewidth=0.6,
                zorder=3,
            )
        )
    if route_xy:
        ax.plot([p[0] for p in route_xy], [p[1] for p in route_xy], color=EVASION, linewidth=1.8, zorder=5, label="A* evasion path")


def build_static_figure() -> dict:
    mission = load_waypoints()
    traj = valid_traj(pd.read_csv(STATIC_RUN / "brain" / "trajectory.csv"))
    brain = parse_jsonl(STATIC_RUN / "brain" / "events.jsonl")
    vision = parse_jsonl(STATIC_RUN / "vision" / "events.jsonl")

    detect_evt = nearest_event(brain, STATIC_DETECTION_TS, "decision_snapshot", "tower")
    evasion_evt = nearest_event(brain, STATIC_EVASION_TS, "evasion_route_generated", "tower")
    detect_vision = nearest_event(vision, float(detect_evt["ts"]), "vision_frame", "tower")
    evasion_vision = nearest_event(vision, float(evasion_evt["ts"]), "vision_frame", "tower")
    detect_frame = nearest_archived_frame(STATIC_RUN, int(detect_vision["frame"]))
    evasion_frame = nearest_archived_frame(STATIC_RUN, int(evasion_vision["frame"]))

    det_row = nearest_row(traj, float(detect_evt["ts"]))
    eva_row = nearest_row(traj, float(evasion_evt["ts"]))
    lat_ref = float(eva_row["lat"])
    lon_ref = float(eva_row["lon"])
    mission_xy = mission_xy_for_ref(lat_ref, lon_ref, mission)
    traj["east"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[0], axis=1)
    traj["north"] = traj.apply(lambda r: latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[1], axis=1)

    det_obs = obs_xy_from_event(detect_evt, lat_ref, lon_ref, "tower")
    eva_obs = obs_xy_from_event(evasion_vision, lat_ref, lon_ref, "tower")
    raw_tower_obs = [o for o in evasion_vision.get("outgoing", []) if str(o.get("type", "")).lower() == "tower"]
    wp_idx = int(evasion_evt.get("wp_idx", 0) or 0)
    target_wp = mission[min(max(wp_idx, 0), len(mission) - 1)]
    route_xy, occupied, route_cells = reconstruct_route(lat_ref, lon_ref, target_wp, raw_tower_obs[:2])

    fig = plt.figure(figsize=(13.2, 8.2))
    gs = fig.add_gridspec(2, 3, wspace=0.18, hspace=0.20)
    ax1, ax2, ax3, ax4, ax5, ax6 = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(3)]

    plot_mission(ax1, mission_xy)
    early = traj[traj["ts"] <= float(detect_evt["ts"])].head(40)
    if len(early):
        ax1.scatter([early["east"].iloc[-1]], [early["north"].iloc[-1]], marker="^", s=60, color=INK, zorder=6, label="UAS")
    draw_label(ax1, "1A", "Initial Stages. Nominal Navigation")
    style_ax(ax1)
    ax1.legend(loc="lower right", fontsize=7)

    draw_unreal_panel(
        ax2,
        detect_frame,
        "1B",
        "Detection Stage. No Safety Action",
        f"tower detected; d={float(detect_evt['nearest_distance_m']):.1f} m > D_react={float(detect_evt['reaction_distance_eval_m']):.1f} m",
    )

    draw_unreal_panel(
        ax3,
        evasion_frame,
        "1C",
        "Evasion Stage. Safety Action",
        f"tower route generated; d={float(evasion_evt['nearest_distance_m']):.1f} m, route={int(evasion_evt['route_points'])} points",
    )

    plot_mission(ax4, mission_xy)
    ax4.plot(traj["east"], traj["north"], color=FLOWN, linewidth=1.0, alpha=0.75, label="Flown path")
    tower_window = traj[(traj["ts"] >= float(evasion_evt["ts"]) - 10) & (traj["ts"] <= float(evasion_evt["ts"]) + 70)]
    if len(tower_window):
        ax4.plot(tower_window["east"], tower_window["north"], color=EVASION, linewidth=2.0, label="Tower evasion window")
    draw_obstacles(ax4, eva_obs[:2], TOWER, radius=True, label="Tower")
    draw_label(ax4, "1D", "Final Stage. Route Summary")
    style_ax(ax4)
    ax4.legend(loc="lower right", fontsize=7)

    plot_mission(ax5, mission_xy)
    det_xy = latlon_to_enu(lat_ref, lon_ref, float(det_row["lat"]), float(det_row["lon"]))
    ax5.scatter([det_xy[0]], [det_xy[1]], marker="^", s=60, color=INK, zorder=8, label="UAS")
    ax5.add_patch(patches.Circle(det_xy, BASE_REACTION_M, fill=False, linestyle="--", edgecolor="#496d8d", linewidth=1.1, label="Base reaction distance"))
    ax5.add_patch(patches.Circle(det_xy, float(detect_evt["reaction_distance_eval_m"]), fill=False, linestyle=":", edgecolor="#2f5d7c", linewidth=1.2, label="Reaction distance"))
    draw_obstacles(ax5, det_obs[:2], TOWER, radius=True, label="Tower")
    draw_label(ax5, "1E", "Detection Stage. No Safety Action")
    style_ax(ax5)
    ax5.legend(loc="lower right", fontsize=6.8)

    draw_grid(ax6, occupied, route_cells, route_xy)
    ax6.scatter([0], [0], marker="^", s=65, color=INK, zorder=9, label="UAS")
    draw_obstacles(ax6, eva_obs[:2], TOWER, radius=True, label="Tower")
    draw_label(ax6, "1F", "Evasion Stage. Safety Action")
    style_ax(ax6)
    ax6.set_xlim(-95, 95)
    ax6.set_ylim(-95, 95)
    ax6.legend(loc="lower right", fontsize=6.8)

    out = OUT / "figure_1_static_tower_multipanel.png"
    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    for src, name in [(detect_frame, "figure_1B_static_tower_unreal_source.jpg"), (evasion_frame, "figure_1C_static_tower_unreal_source.jpg")]:
        if src:
            shutil.copyfile(src, OUT / name)

    return {
        "figure": str(out.name),
        "run": str(STATIC_RUN.relative_to(REPO)),
        "detection_event_ts": float(detect_evt["ts"]),
        "detection_frame": detect_frame.name if detect_frame else None,
        "evasion_event_ts": float(evasion_evt["ts"]),
        "evasion_frame": evasion_frame.name if evasion_frame else None,
        "note": "1D is generated from the available tower episode in this run; the run is not guaranteed to contain only tower obstacles.",
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
        "- `figure_1_static_tower_multipanel.png`: Figura 1, caso estatico con torre, paneles 1A-1F.",
        "- `figure_2_moving_peloton_multipanel.png`: Figura 2 provisional, obstaculo movil tipo peloton/biker, paneles 2A-2C.",
        "- `manifest.json`: trazabilidad de runs, timestamps y frames fuente.",
        "- `reference_historical_porce_six_stage_sequence.png`: figura historica de seis paneles generada por `generate_paper_assets.py`.",
        "- `reference_historical_porce_yolo_future_overlay.png`: figura historica de overlay YOLO/futuro.",
        "",
        "## Lectura critica",
        "",
        "- `tools/make_viz_gif_manual.py` no crea el multipanel: crea un GIF a partir de `pipeline/logs/viz_frames/frame_*.png`.",
        "- El multipanel historico se generaba en `generate_paper_assets.py`, funcion `build_six_stage_sequence_figure(...)`.",
        "- La Figura 1 generada aqui usa un episodio con torre del run disponible `20260218_234222`; 1D resume la ventana de evasion de torre dentro de ese run, no una mision nueva garantizada como solo-torre.",
        "- Las capturas Unreal usadas son frames archivados de vision con HUD/bounding boxes, porque la decision escena limpia vs boxes sigue sin cerrarse.",
    ]
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
