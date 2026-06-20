from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image

import generate_paper_figures as g

REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
LATEX_IMAGES = (
    REPO
    / "paper"
    / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
    / "Imagenes"
)
IEEE_LATEX_IMAGES = (
    REPO
    / "paper"
    / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
    / "IEEE"
    / "TII-Articles-LaTeX-template"
    / "Imagenes"
)
LATEX_IMAGE_DIRS = (LATEX_IMAGES, IEEE_LATEX_IMAGES, REPO)

FIG1_NAME = "paper_figure_1_static_tower_sequence.png"
FIG2_NAME = "paper_figure_2_moving_peloton_sequence.png"

FINAL_PELOTON_ARTIFACTS = OUT / "yolo_crossing_precheck" / "final_artifacts"
FIG2_ARTIFACT_MANIFEST = FINAL_PELOTON_ARTIFACTS / "figure2_artifact_manifest.json"
PELOTON_UNREAL_IMAGE = FINAL_PELOTON_ARTIFACTS / "figure_unreal_raw_peloton_crossing.png"
YOLO_UNREAL_IMAGE = FINAL_PELOTON_ARTIFACTS / "figure_yolo_overlay_peloton_crossing_close.png"
YOLO_CROSSING_VIDEO = FINAL_PELOTON_ARTIFACTS / "video_yolo_peloton_crossing_event.mp4"

def _path_from_repo_or_abs(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path

def _fig2_artifact_manifest() -> dict:
    if not FIG2_ARTIFACT_MANIFEST.exists():
        return {}
    try:
        return json.loads(FIG2_ARTIFACT_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

_FIG2_ARTIFACT_META = _fig2_artifact_manifest()

def _fig2_source_run() -> Path:
    override = os.environ.get("PORCE_FIG2_MOVING_RUN")
    if override:
        return REPO / "pipeline" / "logs" / "zero_trust" / override
    manifest_run = _FIG2_ARTIFACT_META.get("source_run")
    if manifest_run:
        return _path_from_repo_or_abs(manifest_run)
    return REPO / "pipeline" / "logs" / "zero_trust" / "20260620_072924"

def _fig2_selected_frame(default: int = 1250) -> int:
    try:
        return int(_FIG2_ARTIFACT_META.get("selected_frame", default))
    except (TypeError, ValueError):
        return default

MOVING_REAL_RUN = _fig2_source_run()
MOVING_REAL_EVASION_TS = None
PELOTON_UNREAL_FRAME = _fig2_selected_frame()
YOLO_UNREAL_FRAME = PELOTON_UNREAL_FRAME

g.MOVING_RUN = MOVING_REAL_RUN
if MOVING_REAL_EVASION_TS is not None:
    g.MOVING_EVASION_TS = MOVING_REAL_EVASION_TS

FIG1_XLIM = (-45.0, 155.0)
FIG1_YLIM = (-160.0, 40.0)


def copy_to_latex_images(source: Path, filename: str) -> list[str]:
    copied = []
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
        target = image_dir / filename
        shutil.copyfile(source, target)
        copied.append(str(target))
    return copied


def _apply_fig1_view(ax) -> None:
    ax.set_xlim(*FIG1_XLIM)
    ax.set_ylim(*FIG1_YLIM)
    ax.set_aspect("equal", adjustable="box")


def _panel_title(ax, panel: str, title: str) -> None:
    ax.text(
        0.02,
        0.965,
        panel,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.24", facecolor=g.INK, edgecolor="none", alpha=0.96),
        zorder=100,
    )
    ax.text(
        0.135,
        0.965,
        title,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.4,
        fontweight="bold",
        color=g.INK,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.88),
        zorder=99,
    )


def _style_axis(ax) -> None:
    g.style_ax(ax)
    ax.tick_params(labelsize=6.8)
    ax.xaxis.label.set_size(7.4)
    ax.yaxis.label.set_size(7.4)


def _base_fig1(ax, d: dict, *, grid: bool = False) -> None:
    if grid:
        g.draw_grid(ax, d["occupied"], d["route_cells"], d["route_xy"], origin_xy=d["plan_origin_xy"])
    g.plot_wp1_wp2_segment(ax, d["mission"], d["lat_ref"], d["lon_ref"])
    _style_axis(ax)
    _apply_fig1_view(ax)


def _draw_uas(ax, xy: tuple[float, float], size: float = 54.0) -> None:
    ax.scatter([xy[0]], [xy[1]], marker="^", s=size, color=g.INK, edgecolor="white", linewidth=0.35, zorder=12)


def _draw_obstacle(ax, obs: list[dict], label_distance: bool = True) -> None:
    for item in obs[:1]:
        ax.add_patch(
            patches.Circle(
                (item["east"], item["north"]),
                g.RS_M,
                facecolor=(0.70, 0.18, 0.15, 0.12),
                edgecolor=g.TOWER,
                linewidth=0.95,
                zorder=4,
            )
        )
        ax.scatter([item["east"]], [item["north"]], marker="x", s=45, color=g.TOWER, linewidth=1.3, zorder=8)
        if label_distance:
            ax.text(
                item["east"] + 4,
                item["north"] + 3,
                f"{item['distance']:.1f} m",
                fontsize=6.6,
                color=g.INK,
                zorder=9,
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.75),
            )


def build_final_figure1() -> dict:
    d = g.prepare_static_context()
    traj = d["traj"]
    fig = plt.figure(figsize=(10.8, 7.55))
    gs = fig.add_gridspec(2, 3, wspace=0.16, hspace=0.18)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(3)]

    early = traj[traj["ts"] <= float(d["detect_evt"]["ts"]) - 2.0]
    init_row = early.iloc[-1] if len(early) else d["det_row"]
    init_xy = g.latlon_to_enu(d["lat_ref"], d["lon_ref"], float(init_row["lat"]), float(init_row["lon"]))

    ax = axes[0]
    _base_fig1(ax, d)
    _draw_uas(ax, init_xy)
    _panel_title(ax, "1A", "Nominal navigation")

    ax = axes[1]
    _base_fig1(ax, d)
    _draw_uas(ax, d["detect_xy"])
    _draw_obstacle(ax, d["det_obs"])
    ax.plot(
        [d["detect_xy"][0], d["det_obs"][0]["east"]],
        [d["detect_xy"][1], d["det_obs"][0]["north"]],
        color="#8d99a6",
        linestyle=":",
        linewidth=0.9,
        zorder=3,
    )
    _panel_title(ax, "1B", "Detected, no action")

    ax = axes[2]
    _base_fig1(ax, d)
    det_xy = d["detect_detail_xy"]
    ax.add_patch(
        patches.Circle(
            det_xy,
            g.BASE_REACTION_M,
            fill=False,
            linestyle="--",
            edgecolor="#496d8d",
            linewidth=1.0,
            zorder=3,
        )
    )
    ax.add_patch(
        patches.Circle(
            det_xy,
            float(d["detection_detail_evt"]["reaction_distance_eval_m"]),
            fill=False,
            linestyle=":",
            edgecolor="#2f5d7c",
            linewidth=1.15,
            zorder=3,
        )
    )
    _draw_uas(ax, det_xy)
    _draw_obstacle(ax, d["det_detail_obs"])
    _panel_title(ax, "1C", "Reaction margins")

    ax = axes[3]
    _base_fig1(ax, d, grid=True)
    _draw_uas(ax, d["plan_origin_xy"])
    _draw_obstacle(ax, d["eva_obs"])
    _panel_title(ax, "1D", "Local A* triggered")

    ax = axes[4]
    _base_fig1(ax, d, grid=True)
    flown = traj[(traj["ts"] >= float(d["evasion_evt"]["ts"])) & (traj["ts"] <= float(d["mid_evasion_row"]["ts"]))]
    ax.plot(flown["east"], flown["north"], color=g.FLOWN, linewidth=1.15, alpha=0.82, zorder=7)
    _draw_uas(ax, d["mid_evasion_xy"])
    _draw_obstacle(ax, d["eva_obs"])
    _panel_title(ax, "1E", "Evasion in progress")

    ax = axes[5]
    _base_fig1(ax, d)
    ax.plot(traj["east"], traj["north"], color=g.FLOWN, linewidth=1.15, alpha=0.75, zorder=6)
    tower_window = traj[
        (traj["ts"] >= float(d["evasion_evt"]["ts"]) - 2)
        & (traj["ts"] <= float(d["completion_evt"]["ts"]) + 2)
    ]
    ax.plot(tower_window["east"], tower_window["north"], color=g.EVASION, linewidth=1.65, alpha=0.92, zorder=8)
    _draw_obstacle(ax, d["eva_obs"])
    _panel_title(ax, "1F", "Route recovery")

    handles = [
        Line2D([0], [0], color=g.NOMINAL, linestyle="--", linewidth=1.25, label="Planned path"),
        Line2D([0], [0], color=g.FLOWN, linewidth=1.25, label="Actual trajectory"),
        Line2D([0], [0], color=g.EVASION, linewidth=1.65, label="Active evasion"),
        Line2D([0], [0], color=g.EVASION, linewidth=1.65, label="Local A* path"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor=g.INK, markeredgecolor="white", markersize=7, label="UAS"),
        Line2D([0], [0], marker="x", color=g.TOWER, linestyle="none", markersize=7, markeredgewidth=1.4, label="Tower"),
        Line2D([0], [0], color="#496d8d", linestyle="--", linewidth=1.0, label="Base reaction"),
        Line2D([0], [0], color="#2f5d7c", linestyle=":", linewidth=1.15, label="Dynamic reaction"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=7.2, bbox_to_anchor=(0.5, 0.012))
    fig.subplots_adjust(bottom=0.105, left=0.06, right=0.985, top=0.98)
    out = OUT / FIG1_NAME
    fig.savefig(out, dpi=320, facecolor="white")
    plt.close(fig)
    latex_files = copy_to_latex_images(out, FIG1_NAME)
    return {
        "file": str(out),
        "latex_file": latex_files[0],
        "latex_files": latex_files,
        "view_m": {"xlim": FIG1_XLIM, "ylim": FIG1_YLIM},
        "source_run": str(g.STATIC_RUN.relative_to(REPO)),
    }


def _formation_offsets(count: int = 18, max_per_row: int = 5, longitudinal_m: float = 1.9, lateral_m: float = 1.05):
    offsets = []
    remaining = 0
    row = 0
    capacity = 1
    for rider in range(count):
        remaining = rider
        row = 0
        capacity = 1
        while remaining >= capacity:
            remaining -= capacity
            row += 1
            capacity = min(row + 1, max_per_row)
        distance = row * longitudinal_m
        centered_lane = remaining - ((capacity - 1) * 0.5)
        lateral = centered_lane * lateral_m
        if row % 2 == 1:
            lateral += 0.35
        offsets.append((lateral, -distance))
    return offsets


def _draw_peloton_model(ax) -> None:
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-24, 24)
    ax.set_ylim(-28, 24)
    ax.axis("off")
    ax.add_patch(patches.Rectangle((-6.8, -31), 13.6, 62, angle=-28, facecolor="#eeeae0", edgecolor="none", alpha=0.82, zorder=0))
    ax.plot([-18, 18], [-22, 18], color="#bec7c7", linewidth=1.0, linestyle="--", zorder=1)
    ax.arrow(-18, -22, 30, 33, width=0.18, head_width=1.35, head_length=1.8, color="#52616d", zorder=2, length_includes_head=True)

    theta = math.radians(28)
    rot = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    offsets = np.array(_formation_offsets())
    riders = offsets @ rot.T
    riders[:, 1] -= 2.5

    ax.scatter(riders[:, 0], riders[:, 1], s=68, color="#146c78", edgecolor="white", linewidth=0.55, zorder=5)
    ax.scatter([riders[0, 0]], [riders[0, 1]], s=88, color="#0b3d49", edgecolor="white", linewidth=0.6, zorder=6)

    uas = np.array([-17, 12])
    ax.scatter([uas[0]], [uas[1]], marker="^", s=150, color=g.INK, edgecolor="white", linewidth=0.75, zorder=8)
    ax.add_patch(
        patches.Wedge(
            uas,
            27,
            -42,
            12,
            width=22,
            facecolor="#f2c14e",
            edgecolor="#c9941c",
            alpha=0.16,
            linewidth=1.0,
            zorder=2,
        )
    )
    ax.annotate("", xy=(7.5, 7.2), xytext=(-11.5, 9.8), arrowprops=dict(arrowstyle="->", color="#c9941c", lw=1.1))
    ax.text(-22.3, 20.6, "2A", fontsize=9, fontweight="bold", color="white", bbox=dict(boxstyle="round,pad=0.25", facecolor=g.INK, edgecolor="none"))
    ax.text(-17.5, 20.6, "Moving obstacle model", fontsize=8.4, fontweight="bold", color=g.INK, bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.88))
    ax.text(-21.5, -25.5, "Current peloton", fontsize=6.8, color="#146c78")
    ax.text(5.5, 16.2, "Left-right spline loop", fontsize=6.8, color="#52616d")


def _moving_context() -> dict:
    mission = g.load_waypoints()
    traj = g.valid_traj(pd.read_csv(g.MOVING_RUN / "brain" / "trajectory.csv"))
    brain = g.parse_jsonl(g.MOVING_RUN / "brain" / "events.jsonl")
    vision = g.parse_jsonl(g.MOVING_RUN / "vision" / "events.jsonl")
    route_evt = None
    if brain and MOVING_REAL_EVASION_TS is not None:
        route_evt = g.nearest_event(brain, MOVING_REAL_EVASION_TS, "evasion_route_generated", "bike")
    if route_evt is None:
        obs_rows = traj[traj["obs_count"] > 0]
        if len(obs_rows):
            route_evt = {"kind": "trajectory_obs_trigger", "ts": float(obs_rows.iloc[0]["ts"])}
        else:
            active_rows = traj[traj["evasion_active"] == 1]
            if not len(active_rows):
                raise RuntimeError(f"No moving-obstacle trigger found in {g.MOVING_RUN}")
            route_evt = {"kind": "trajectory_evasion_start", "ts": float(active_rows.iloc[0]["ts"])}
    row = g.nearest_row(traj, float(route_evt["ts"]))
    lat_ref = float(row["lat"])
    lon_ref = float(row["lon"])
    mission_xy = g.mission_xy_for_ref(lat_ref, lon_ref, mission)
    traj["east"] = traj.apply(lambda r: g.latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[0], axis=1)
    traj["north"] = traj.apply(lambda r: g.latlon_to_enu(lat_ref, lon_ref, float(r["lat"]), float(r["lon"]))[1], axis=1)

    snapshots = []
    centroids = []
    if vision:
        for evt in vision:
            if evt.get("kind") != "vision_frame":
                continue
            t_rel = float(evt.get("ts", 0.0)) - float(route_evt["ts"])
            if -4.0 <= t_rel <= 10.0:
                frame_pts = []
                for obs in evt.get("outgoing", []) or []:
                    if str(obs.get("type", "")).lower() not in {"bike", "biker"}:
                        continue
                    if obs.get("lat") is None or obs.get("lon") is None:
                        continue
                    east, north = g.latlon_to_enu(lat_ref, lon_ref, float(obs["lat"]), float(obs["lon"]))
                    row_payload = {"east": east, "north": north, "t": t_rel, "distance": float(obs.get("distance", 0.0) or 0.0)}
                    snapshots.append(row_payload)
                    frame_pts.append(row_payload)
                if frame_pts:
                    centroids.append(
                        {
                            "east": float(np.mean([p["east"] for p in frame_pts])),
                            "north": float(np.mean([p["north"] for p in frame_pts])),
                            "t": t_rel,
                        }
                    )
    if not snapshots:
        posted = traj[
            (traj["ts"] >= float(route_evt["ts"]) - 2.0)
            & (traj["ts"] <= float(route_evt["ts"]) + 12.0)
            & (traj["obs_count"] > 0)
        ]
        for _, obs_row in posted.iterrows():
            snapshots.append(
                {
                    "east": float(obs_row["east"]),
                    "north": float(obs_row["north"]),
                    "t": float(obs_row["ts"]) - float(route_evt["ts"]),
                    "distance": float(obs_row.get("nearest_obs_dist_m", 0.0) or 0.0),
                }
            )
    local = traj[(traj["ts"] >= float(route_evt["ts"]) - 10.0) & (traj["ts"] <= float(route_evt["ts"]) + 32.0)]
    active = local[local["evasion_active"] == 1]
    xs = list(local["east"]) + [s["east"] for s in snapshots]
    ys = list(local["north"]) + [s["north"] for s in snapshots]
    xmid = (min(xs) + max(xs)) / 2.0
    ymid = (min(ys) + max(ys)) / 2.0
    span = max(max(xs) - min(xs), max(ys) - min(ys), 85.0) * 1.22
    limits = (xmid - span / 2.0, xmid + span / 2.0, ymid - span / 2.0, ymid + span / 2.0)
    return {
        "mission": mission,
        "mission_xy": mission_xy,
        "traj": traj,
        "local": local,
        "active": active,
        "snapshots": snapshots,
        "centroids": centroids,
        "route_evt": route_evt,
        "limits": limits,
    }


def _apply_moving_limits(ax, limits) -> None:
    ax.set_xlim(limits[0], limits[1])
    ax.set_ylim(limits[2], limits[3])
    ax.set_aspect("equal", adjustable="box")


def _load_unreal_frame(frame: int) -> Image.Image:
    path = MOVING_REAL_RUN / "vision" / "frames" / f"yolo_{int(frame):06d}.jpg"
    if not path.exists():
        raise FileNotFoundError(path)
    return Image.open(path).convert("RGB")


def _vision_event_for_frame(frame: int) -> dict:
    events_path = MOVING_REAL_RUN / "vision" / "events.jsonl"
    for line in events_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if f'"frame": {int(frame)}' not in line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("kind") == "vision_frame" and int(evt.get("frame", -1)) == int(frame):
            return evt
    return {}


def _draw_image_panel(ax, frame: int, panel: str, title: str, crop: tuple[int, int, int, int] | None = None) -> None:
    img = _load_unreal_frame(frame)
    if crop:
        img = img.crop(crop)
    ax.imshow(img)
    ax.set_axis_off()
    _panel_title(ax, panel, title)


def _draw_image_file_panel(ax, path: Path, panel: str, title: str, crop: tuple[int, int, int, int] | None = None) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    img = Image.open(path).convert("RGB")
    if crop:
        img = img.crop(crop)
    ax.imshow(img)
    ax.set_axis_off()
    _panel_title(ax, panel, title)


def _draw_yolo_overlay_panel(
    ax,
    frame: int,
    panel: str,
    title: str,
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    img = _load_unreal_frame(frame)
    crop_x0 = crop_y0 = 0
    if crop:
        crop_x0, crop_y0, _, _ = crop
        img = img.crop(crop)
    ax.imshow(img)
    ax.set_axis_off()

    evt = _vision_event_for_frame(frame)
    outgoing = list(evt.get("outgoing", []) or [])
    outgoing.sort(key=lambda item: float(item.get("distance", 1e9)))
    drawn = 0
    for item in outgoing[:2]:
        bbox = item.get("bbox") or {}
        try:
            pad = 5.0
            x1 = float(bbox["x1"]) - crop_x0 - pad
            y1 = float(bbox["y1"]) - crop_y0 - pad
            x2 = float(bbox["x2"]) - crop_x0 + pad
            y2 = float(bbox["y2"]) - crop_y0 + pad
        except Exception:
            continue
        if x2 < 0 or y2 < 0 or x1 > img.width or y1 > img.height:
            continue
        x1 = max(0.0, min(float(img.width - 1), x1))
        y1 = max(0.0, min(float(img.height - 1), y1))
        x2 = max(0.0, min(float(img.width - 1), x2))
        y2 = max(0.0, min(float(img.height - 1), y2))
        if x2 <= x1 or y2 <= y1:
            continue
        ax.add_patch(
            patches.Rectangle(
                (x1, y1),
                x2 - x1,
                y2 - y1,
                fill=False,
                linewidth=2.1,
                edgecolor="#00ff66",
                zorder=20,
            )
        )
        drawn += 1
    if drawn == 0:
        ax.text(
            0.5,
            0.5,
            "No YOLO boxes in selected frame",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=8,
            color=g.INK,
        )
    _panel_title(ax, panel, title)


def build_final_figure2() -> dict:
    d = _moving_context()
    fig = plt.figure(figsize=(11.2, 8.15))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.86, 1.0], wspace=0.13, hspace=0.22)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    _draw_image_file_panel(ax1, PELOTON_UNREAL_IMAGE, "2A", "Unreal peloton view", crop=(0, 95, 640, 640))
    _draw_image_file_panel(ax2, YOLO_UNREAL_IMAGE, "2B", "YOLO over Unreal", crop=(0, 220, 640, 640))

    g.plot_mission(ax3, d["mission_xy"])
    ax3.plot(d["local"]["east"], d["local"]["north"], color=g.FLOWN, linewidth=1.2, alpha=0.84, zorder=5)
    sc = ax3.scatter(
        [s["east"] for s in d["snapshots"]],
        [s["north"] for s in d["snapshots"]],
        c=[s["t"] for s in d["snapshots"]],
        cmap="viridis",
        s=17,
        marker="x",
        linewidth=0.9,
        alpha=0.78,
        zorder=8,
    )
    ax3.scatter([0], [0], marker="^", s=58, color=g.INK, edgecolor="white", linewidth=0.35, zorder=10)
    _style_axis(ax3)
    _apply_moving_limits(ax3, d["limits"])
    _panel_title(ax3, "2C", "YOLO obstacle posts")

    g.plot_mission(ax4, d["mission_xy"])
    ax4.plot(d["local"]["east"], d["local"]["north"], color=g.FLOWN, linewidth=1.0, alpha=0.55, zorder=5)
    if len(d["active"]):
        ax4.plot(d["active"]["east"], d["active"]["north"], color=g.EVASION, linewidth=1.9, alpha=0.95, zorder=7)
    if d["snapshots"]:
        ax4.scatter(
            [s["east"] for s in d["snapshots"]],
            [s["north"] for s in d["snapshots"]],
            c=[s["t"] for s in d["snapshots"]],
            cmap="viridis",
            s=18,
            marker="x",
            linewidth=0.9,
            alpha=0.75,
            zorder=8,
        )
    if d["centroids"]:
        cent = pd.DataFrame(d["centroids"]).sort_values("t")
        ax4.plot(cent["east"], cent["north"], color="#2a7f78", linewidth=1.35, alpha=0.9, zorder=6)
        ax4.scatter(cent["east"], cent["north"], c=cent["t"], cmap="viridis", s=16, edgecolor="none", zorder=8)
    ax4.scatter([0], [0], marker="^", s=58, color=g.INK, edgecolor="white", linewidth=0.35, zorder=10)
    _style_axis(ax4)
    _apply_moving_limits(ax4, d["limits"])
    _panel_title(ax4, "2D", "Evasion response")

    cb = fig.colorbar(sc, ax=[ax3, ax4], fraction=0.026, pad=0.012)
    cb.set_label("Time from trigger (s)", fontsize=7.2)
    cb.ax.tick_params(labelsize=6.8)
    handles = [
        Line2D([0], [0], color=g.NOMINAL, linestyle="--", linewidth=1.25, label="Planned path"),
        Line2D([0], [0], color=g.FLOWN, linewidth=1.2, label="Actual trajectory"),
        Line2D([0], [0], color=g.EVASION, linewidth=1.8, label="Active evasion"),
        Line2D([0], [0], marker="x", color="#4c6f9f", linestyle="none", markersize=6, label="YOLO obstacle posts"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor=g.INK, markeredgecolor="white", markersize=7, label="UAS"),
    ]
    if d["centroids"]:
        handles.insert(3, Line2D([0], [0], color="#2a7f78", linewidth=1.35, label="Peloton centroid"))
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False, fontsize=7.1, bbox_to_anchor=(0.5, 0.018))
    fig.subplots_adjust(bottom=0.105, left=0.052, right=0.955, top=0.982)
    out = OUT / FIG2_NAME
    fig.savefig(out, dpi=320, facecolor="white")
    plt.close(fig)
    latex_files = copy_to_latex_images(out, FIG2_NAME)
    return {
        "file": str(out),
        "latex_file": latex_files[0],
        "latex_files": latex_files,
        "source_run": str(g.MOVING_RUN.relative_to(REPO)),
        "route_event_ts": float(d["route_evt"]["ts"]),
        "detections": len(d["snapshots"]),
        "centroids": len(d["centroids"]),
        "unreal_frames": {
            "run": str(MOVING_REAL_RUN.relative_to(REPO)),
            "peloton_frame": PELOTON_UNREAL_FRAME,
            "yolo_overlay_frame": YOLO_UNREAL_FRAME,
            "peloton_image": str(PELOTON_UNREAL_IMAGE.relative_to(REPO)),
            "yolo_overlay_image": str(YOLO_UNREAL_IMAGE.relative_to(REPO)),
            "yolo_crossing_video": str(YOLO_CROSSING_VIDEO.relative_to(REPO)),
        },
    }


def _missing_figure2_inputs() -> list[str]:
    required = [PELOTON_UNREAL_IMAGE, YOLO_UNREAL_IMAGE]
    return [str(path.relative_to(REPO)) for path in required if not path.exists()]


def main() -> None:
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "figure_1_final": build_final_figure1(),
        "unreal_staging": {
            "profile": "paper_all_obstacles",
            "script": "Unreal/Scripts/paper_peloton_stage.py",
            "note": "Figure 2 must use a current Unreal/SITL/YOLO run. Override PORCE_FIG2_MOVING_RUN only for audited recaptures; legacy 20260617 assets are not canonical.",
        },
    }
    missing_fig2 = _missing_figure2_inputs()
    require_fig2 = os.environ.get("PORCE_REQUIRE_FIG2", "0").strip().lower() in {"1", "true", "yes", "on"}
    if missing_fig2:
        meta["figure_2_final_pending"] = {
            "missing_inputs": missing_fig2,
            "source_run": str(MOVING_REAL_RUN.relative_to(REPO)),
            "hint": "Run the current Unreal + ArduPilot + YOLO capture and place the selected raw/YOLO panels in yolo_crossing_precheck/final_artifacts, or set PORCE_REQUIRE_FIG2=1 to fail hard.",
        }
        if require_fig2:
            raise FileNotFoundError("Missing Figure 2 inputs: " + ", ".join(missing_fig2))
    else:
        meta["figure_2_final"] = build_final_figure2()
    (OUT / "final_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
