from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
PAPER_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = PAPER_ROOT / "figures"
DATA_DIR = PAPER_ROOT / "data"

PIPELINE_DIR = REPO_ROOT / "pipeline"
ZERO_TRUST_ROOT = PIPELINE_DIR / "logs" / "zero_trust"
E2E_ROOT = PIPELINE_DIR / "logs" / "e2e"

# Case study run (2026-06-12: real SITL + live UE5.7 viewer + PrintWindow capture;
# planner_obs_ids serialized by the D3 audit patch).
CASE_RUN = ZERO_TRUST_ROOT / "20260612_214341"
# WP5 trigger with the UE5.7 peloton crossing the corridor: 16 planner obstacles,
# nearest 37.7 m, 21 route points, completion +70.2 s.
CASE_ROUTE_TS = 1781293720.29
CASE_BRAIN_EVENTS = CASE_RUN / "brain" / "events.jsonl"
CASE_TRAJECTORY = CASE_RUN / "brain" / "trajectory.csv"
CASE_VISION_EVENTS = CASE_RUN / "vision" / "events.jsonl"
CASE_FRAMES_DIR = CASE_RUN / "vision" / "frames"

# The brain canonicalizes the detector class "biker" to "bike"; both label the
# same human-adjacent obstacle family in logs from different components.
BIKER_TYPES = {"bike", "biker"}


def is_biker_type(value) -> bool:
    return str(value or "").strip().lower() in BIKER_TYPES

E2E_RUNS = {
    "PORCE on + detections": E2E_ROOT / "porce_on_with_detections_20260217_142707" / "brain.log",
    "PORCE off + detections": E2E_ROOT / "porce_off_with_detections_20260217_142339" / "brain.log",
    "PORCE on + no detections": E2E_ROOT / "porce_on_no_detections_20260217_142012" / "brain.log",
    "PORCE off + no detections": E2E_ROOT / "porce_off_no_detections_20260217_141645" / "brain.log",
}

# Statistical campaign (2026-06-12, tools/e2e_campaign.py): 10 runs x 4 scenarios.
E2E_CAMPAIGN_PREFIXES = {
    "PORCE on + detections": "porce_on_with_detections_20260612_",
    "PORCE off + detections": "porce_off_with_detections_20260612_",
    "PORCE on + no detections": "porce_on_no_detections_20260612_",
    "PORCE off + no detections": "porce_off_no_detections_20260612_",
}


def discover_campaign_runs() -> dict[str, list[Path]]:
    runs: dict[str, list[Path]] = {}
    for label, prefix in E2E_CAMPAIGN_PREFIXES.items():
        logs = sorted(
            p / "brain.log"
            for p in E2E_ROOT.glob(prefix + "*")
            if (p / "brain.log").exists()
        )
        runs[label] = logs
    return runs


plt.rcParams.update(
    {
        "font.size": 11,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "legend.fontsize": 9,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.dpi": 160,
        "savefig.dpi": 200,
    }
)


PAPER_INK = "#24303d"
PAPER_LINE = "#5f6c78"
PAPER_GRID = "#d9e0e6"
PAPER_BOX = "#f6f8fa"
PAPER_COOL = "#edf2f6"
PAPER_WARM = "#f3efe8"
PAPER_ACCENT = "#e4ebf2"


@dataclass
class MissionPoint:
    index: int
    lat: float
    lon: float
    alt_m: float


def ensure_dirs() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def should_generate_structural_png(stem: str) -> bool:
    return not (FIGURES_DIR / f"{stem}.drawio").exists()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def latlon_to_enu(lat_ref: float, lon_ref: float, lat: float, lon: float) -> tuple[float, float]:
    north = math.radians(lat - lat_ref) * 6_371_000.0
    east = math.radians(lon - lon_ref) * 6_371_000.0 * max(math.cos(math.radians(lat_ref)), 1e-6)
    return east, north


def cumulative_path_length(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        total += haversine_m(lat1, lon1, lat2, lon2)
    return total


def load_waypoints(path: Path) -> list[MissionPoint]:
    rows = path.read_text(encoding="utf-8").splitlines()
    mission: list[MissionPoint] = []
    for line in rows[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        mission.append(
            MissionPoint(
                index=int(parts[0]),
                lat=float(parts[8]),
                lon=float(parts[9]),
                alt_m=float(parts[10]),
            )
        )
    return mission


def parse_e2e_status_log(path: Path) -> pd.DataFrame:
    pattern = re.compile(
        r"^(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d).+?GPS: (?P<lat>[-0-9.]+), (?P<lon>[-0-9.]+) "
        r"Alt: (?P<alt>[-0-9.]+)m .*?\| WP: (?P<wp>\d+) \| Obs: (?P<obs>\d+)"
    )
    rows: list[dict[str, float | int]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        t_abs = int(match.group("h")) * 3600 + int(match.group("m")) * 60 + int(match.group("s"))
        rows.append(
            {
                "t_abs_s": t_abs,
                "lat": float(match.group("lat")),
                "lon": float(match.group("lon")),
                "alt_m": float(match.group("alt")),
                "wp_idx": int(match.group("wp")),
                "obs_count": int(match.group("obs")),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["t_s"] = df["t_abs_s"] - df["t_abs_s"].iloc[0]
    df["segment_m"] = 0.0
    for idx in range(1, len(df)):
        df.loc[idx, "segment_m"] = haversine_m(
            float(df.loc[idx - 1, "lat"]),
            float(df.loc[idx - 1, "lon"]),
            float(df.loc[idx, "lat"]),
            float(df.loc[idx, "lon"]),
        )
    return df


def parse_jsonl(path: Path) -> list[dict]:
    items = []
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def style_paper_axes(ax) -> None:
    ax.grid(color=PAPER_GRID, alpha=0.9, linestyle=":", linewidth=0.85)
    for spine in ax.spines.values():
        spine.set_color("#6f7a85")
        spine.set_linewidth(0.9)
    ax.tick_params(colors=PAPER_INK)


def sorted_biker_outgoing(evt: dict, limit: int | None = None) -> list[dict]:
    tracks = sorted(
        [
            obs
            for obs in evt.get("outgoing", [])
            if is_biker_type(obs.get("type")) and obs.get("bbox")
        ],
        key=lambda obs: float(obs.get("distance", 1e9)),
    )
    return tracks if limit is None else tracks[:limit]


def frame_counts(evt: dict) -> dict:
    counts = evt.get("counts", {}) or {}
    return {
        "raw": int(counts.get("raw_boxes", 0) or 0),
        "projected": int(counts.get("accepted_frame_dets", 0) or 0),
        "active": int(counts.get("tracks_active", 0) or 0),
        "published": int(counts.get("published_outgoing", 0) or 0),
    }


def draw_logged_bbox(
    ax,
    obs: dict,
    *,
    label: str,
    color: str,
    linewidth: float = 1.7,
    text_offset: tuple[float, float] = (2.0, -2.0),
) -> None:
    bbox = obs.get("bbox", {})
    x1 = float(bbox.get("x1", 0.0))
    y1 = float(bbox.get("y1", 0.0))
    x2 = float(bbox.get("x2", x1 + 1.0))
    y2 = float(bbox.get("y2", y1 + 1.0))
    ax.add_patch(
        patches.Rectangle(
            (x1, y1),
            max(1.0, x2 - x1),
            max(1.0, y2 - y1),
            fill=False,
            edgecolor=color,
            linewidth=linewidth,
            zorder=8,
        )
    )
    ax.text(
        x1 + text_offset[0],
        max(5.0, y1 + text_offset[1]),
        label,
        fontsize=7.0,
        color="white",
        bbox=dict(boxstyle="round,pad=0.13", facecolor=color, edgecolor="none", alpha=0.94),
        zorder=9,
    )


def draw_pixel_space_detections(
    ax,
    frame_evt: dict,
    *,
    max_tracks: int,
    selected_count: int = 3,
    title_note: str = "",
    show_table: bool = True,
    show_counts: bool = True,
) -> list[str]:
    ax.set_xlim(0, 640)
    ax.set_ylim(640, 0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("#f5f7f9")
    for spine in ax.spines.values():
        spine.set_color("#6f7a85")
        spine.set_linewidth(0.9)
    ax.set_xticks([0, 160, 320, 480, 640])
    ax.set_yticks([0, 160, 320, 480, 640])
    ax.grid(color=PAPER_GRID, alpha=0.9, linestyle=":", linewidth=0.85)
    ax.set_xlabel("Image x (px)")
    ax.set_ylabel("Image y (px)")

    legend_rows: list[str] = []
    label_offsets = [(2.0, -3.0), (2.0, 14.0), (2.0, -19.0), (2.0, 10.0)]
    for idx, obs in enumerate(sorted_biker_outgoing(frame_evt, max_tracks), start=1):
        color = "#00a7d8" if idx <= selected_count else "#e38925"
        text_offset = label_offsets[(idx - 1) % len(label_offsets)]
        draw_logged_bbox(
            ax,
            obs,
            label=f"B{idx}",
            color=color,
            linewidth=1.9 if idx <= selected_count else 1.25,
            text_offset=text_offset,
        )
        bbox = obs.get("bbox", {})
        cx = (float(bbox.get("x1", 0.0)) + float(bbox.get("x2", 0.0))) / 2.0
        cy = (float(bbox.get("y1", 0.0)) + float(bbox.get("y2", 0.0))) / 2.0
        ax.scatter([cx], [cy], s=9, color=color, zorder=9)
        status = "planner" if idx <= selected_count else "pruned"
        legend_rows.append(
            f"B{idx}: id {obs.get('id', '-')}, c={float(obs.get('confidence', 0.0)):.2f}, "
            f"d={float(obs.get('distance', 0.0)):.1f} m, {status}"
        )

    counts = frame_counts(frame_evt)
    if show_counts:
        ax.text(
            0.02,
            0.97,
            f"frame {int(frame_evt['frame'])} | raw {counts['raw']} -> projected {counts['projected']} -> published {counts['published']}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7.45,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.92),
            zorder=12,
        )
    if title_note:
        ax.text(
            0.02,
            0.055,
            title_note,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=7.2,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.88),
            zorder=12,
        )
    if show_table and legend_rows:
        ax.text(
            0.02,
            0.17 if title_note else 0.045,
            "\n".join(legend_rows[:max_tracks]),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=6.75,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.88),
            zorder=12,
        )
    return legend_rows


def build_yolo_scene_overlay(
    route_evt: dict,
    trigger_vision_evt: dict,
    track_snapshots: list[dict],
    origin_row: pd.Series,
    output_path: Path,
) -> None:
    rel_alt = float(origin_row["rel_alt"]) if "rel_alt" in origin_row else float("nan")
    alt_msl = float(origin_row["alt_msl"]) if "alt_msl" in origin_row else float("nan")

    fig = plt.figure(figsize=(12.7, 5.7))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.08], wspace=0.19)
    ax_frame = fig.add_subplot(grid[0, 0])
    ax_metric = fig.add_subplot(grid[0, 1])

    # Archived viewer frame (raw PrintWindow capture of the UE window at the
    # trigger instant). Falls back to the schematic background if missing.
    frame_idx = int(trigger_vision_evt.get("frame", -1))
    frame_path = CASE_FRAMES_DIR / f"yolo_{frame_idx:06d}.jpg"
    if not frame_path.exists():
        # archived every N frames; look for the nearest archived neighbour
        for delta in (1, -1, 2, -2, 3, -3):
            cand = CASE_FRAMES_DIR / f"yolo_{frame_idx + delta:06d}.jpg"
            if cand.exists():
                frame_path = cand
                break
    frame_archived = frame_path.exists()
    if frame_archived:
        ax_frame.imshow(plt.imread(frame_path), extent=[0, 640, 640, 0], zorder=1)
        note = (
            "Archived Unreal viewer frame with logged YOLO boxes\n"
            f"trigger delta t={float(trigger_vision_evt['ts']) - float(route_evt['ts']):+.3f} s"
        )
        # keep a copy next to the figures for the supplementary material
        try:
            import shutil

            shutil.copyfile(frame_path, FIGURES_DIR / "porce_case_viewer_frame.jpg")
        except Exception:
            pass
    else:
        note = (
            "Reconstructed from logged YOLO boxes; no Unreal window screenshot\n"
            f"trigger delta t={float(trigger_vision_evt['ts']) - float(route_evt['ts']):+.3f} s"
        )

    legend_rows = draw_pixel_space_detections(
        ax_frame,
        trigger_vision_evt,
        max_tracks=8,
        selected_count=int(route_evt["planner_obs_count"]),
        show_table=False,
        title_note=note,
    )
    ax_frame.set_title(
        "Viewer Frame with Logged Detections" if frame_archived else "Logged Pixel-Space Detections",
        fontsize=11.5,
        color=PAPER_INK,
        pad=6,
    )
    ax_frame.text(
        0.02,
        0.58,
        "\n".join(legend_rows[:8]),
        transform=ax_frame.transAxes,
        ha="left",
        va="top",
        fontsize=6.9,
        color=PAPER_INK,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.86),
        zorder=12,
    )

    if track_snapshots:
        snap_df = pd.DataFrame(track_snapshots)
        ax_metric.scatter(
            snap_df["east_m"],
            snap_df["north_m"],
            c=snap_df["t_rel_s"],
            cmap="viridis",
            marker="x",
            s=42,
            linewidths=1.55,
            label="published biker detections",
            zorder=5,
        )
        centroids = (
            snap_df.groupby("frame")
            .agg({"t_rel_s": "mean", "east_m": "mean", "north_m": "mean", "distance_m": "min"})
            .sort_values("t_rel_s")
        )
        ax_metric.plot(
            centroids["east_m"],
            centroids["north_m"],
            color="#256f8f",
            linewidth=2.0,
            marker="o",
            label="observed centroid trace",
            zorder=6,
        )
        if len(centroids) >= 2:
            last = centroids.iloc[-1]
            prev = centroids.iloc[-2]
            dt = max(float(last["t_rel_s"] - prev["t_rel_s"]), 1e-3)
            vx = float(last["east_m"] - prev["east_m"]) / dt
            vy = float(last["north_m"] - prev["north_m"]) / dt
            future_t = np.array([0.5, 1.0, 1.5])
            future_x = float(last["east_m"]) + vx * future_t
            future_y = float(last["north_m"]) + vy * future_t
            ax_metric.plot(
                [float(last["east_m"]), *future_x.tolist()],
                [float(last["north_m"]), *future_y.tolist()],
                color="#b9802b",
                linestyle="--",
                linewidth=1.8,
                marker=">",
                label="linear forecast from logged trace",
                zorder=6,
            )
        for row in centroids.itertuples():
            ax_metric.text(float(row.east_m) + 1.0, float(row.north_m) + 1.0, f"{float(row.t_rel_s):+.1f}s", fontsize=7.2, color=PAPER_INK)

    ax_metric.scatter([0.0], [0.0], s=44, color="#24303d", label="drone at trigger", zorder=7)
    ax_metric.set_title("Logged Ground Projection and Forecast", fontsize=11.5, color=PAPER_INK, pad=6)
    ax_metric.set_xlabel("Local east (m)")
    ax_metric.set_ylabel("Local north (m)")
    ax_metric.set_aspect("equal", adjustable="box")
    style_paper_axes(ax_metric)
    ax_metric.legend(loc="lower left", framealpha=0.94, fontsize=7.6)

    info = (
        f"Run {CASE_RUN.name} | WP{int(route_evt.get('wp_idx', 0))} | rel-alt {rel_alt:.1f} m | MSL {alt_msl:.1f} m\n"
        f"trigger: nearest {float(route_evt['nearest_distance_m']):.2f} m, planner subset {int(route_evt['planner_obs_count'])}, "
        f"route {int(route_evt['route_points'])} points\n"
        f"vision frame {int(trigger_vision_evt['frame'])}: raw {frame_counts(trigger_vision_evt)['raw']}, "
        f"projected {frame_counts(trigger_vision_evt)['projected']}, published {frame_counts(trigger_vision_evt)['published']}"
    )
    fig.text(
        0.012,
        0.985,
        info,
        ha="left",
        va="top",
        fontsize=9.0,
        color=PAPER_INK,
        bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor="#5f6c78", alpha=0.96),
    )
    fig.subplots_adjust(left=0.045, right=0.985, top=0.79, bottom=0.11)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def build_six_stage_sequence_figure(
    mission_xy: np.ndarray,
    waypoint_idx: int,
    waypoint_xy: tuple[float, float],
    route_evt: dict,
    vision_evt: dict,
    published_xy: list[dict],
    planner_xy: list[dict],
    occupied_cells: set[tuple[int, int]],
    route_cells: list[tuple[int, int]],
    route_cell_centers: list[tuple[float, float]],
    full_df: pd.DataFrame,
    evasion_df: pd.DataFrame,
    cell_size: float,
    start_ts: float,
    end_ts: float,
    reaction_m: float,
    speed_mps: float,
    track_snapshots: list[dict],
    output_path: Path,
) -> None:
    fig = plt.figure(figsize=(12.9, 8.25))
    grid = fig.add_gridspec(2, 3, wspace=0.22, hspace=0.26)
    axes = [fig.add_subplot(grid[row, col]) for row in range(2) for col in range(3)]

    context_x = [
        0.0,
        waypoint_xy[0],
        *evasion_df["east_m"].tolist(),
        *[obs["east_m"] for obs in published_xy],
        *[obs["east_m"] for obs in planner_xy],
        *[pt[0] for pt in route_cell_centers],
        *[snap["east_m"] for snap in track_snapshots],
        *[cell[0] * cell_size for cell in occupied_cells],
    ]
    context_y = [
        0.0,
        waypoint_xy[1],
        *evasion_df["north_m"].tolist(),
        *[obs["north_m"] for obs in published_xy],
        *[obs["north_m"] for obs in planner_xy],
        *[pt[1] for pt in route_cell_centers],
        *[snap["north_m"] for snap in track_snapshots],
        *[cell[1] * cell_size for cell in occupied_cells],
    ]
    pad = max(10.0, cell_size * 1.8)
    xlim = (min(context_x) - pad, max(context_x) + pad)
    ylim = (min(context_y) - pad, max(context_y) + pad)

    def panel_title(ax, step: int, title: str, subtitle: str) -> None:
        ax.text(
            0.015,
            0.985,
            f"{step}. {title}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10.6,
            fontweight="bold",
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.92),
            zorder=20,
        )
        ax.text(
            0.015,
            0.86,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=7.35,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.9),
            zorder=20,
        )

    def draw_cell(axis, cell_x: int, cell_y: int, facecolor, edgecolor: str, linewidth: float, zorder: int) -> None:
        axis.add_patch(
            patches.Rectangle(
                (cell_x * cell_size - cell_size / 2.0, cell_y * cell_size - cell_size / 2.0),
                cell_size,
                cell_size,
                facecolor=facecolor,
                edgecolor=edgecolor,
                linewidth=linewidth,
                zorder=zorder,
            )
        )

    def apply_common_view(ax) -> None:
        style_paper_axes(ax)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xlabel("East from trigger (m)")
        ax.set_ylabel("North from trigger (m)")

    def draw_common_context(ax, *, executed: bool = False) -> None:
        if len(mission_xy) > 1:
            ax.plot(mission_xy[:, 0], mission_xy[:, 1], "--", color="#98a2ab", linewidth=1.05, alpha=0.78, zorder=1)
        ax.plot([0.0, waypoint_xy[0]], [0.0, waypoint_xy[1]], "--", color="#87929d", linewidth=1.0, alpha=0.82, zorder=2)
        if executed:
            ax.plot(full_df["east_m"], full_df["north_m"], color="#66727c", linewidth=1.05, alpha=0.58, zorder=3)
        ax.scatter([0.0], [0.0], s=36, color="#24303d", zorder=10)
        ax.scatter([waypoint_xy[0]], [waypoint_xy[1]], marker="*", s=115, color="#b9802b", zorder=10)
        ax.text(waypoint_xy[0] + 1.8, waypoint_xy[1] + 1.8, f"WP{waypoint_idx}", fontsize=7.2, color=PAPER_INK, zorder=11)

    def draw_published_tracks(ax, *, selected_only: bool = False, labels: bool = False, faint: bool = False) -> None:
        for idx, obs in enumerate(published_xy, start=1):
            if selected_only and not obs["selected"]:
                continue
            if obs["selected"]:
                color = "#a94d3e"
                marker = "o"
                size = 34
                alpha = 0.92 if not faint else 0.42
            else:
                color = "#8c9aa5"
                marker = "x"
                size = 32
                alpha = 0.86 if not faint else 0.34
            ax.scatter([obs["east_m"]], [obs["north_m"]], s=size, color=color, marker=marker, alpha=alpha, zorder=8)
            if labels:
                label = f"T{idx}\n{obs['distance_m']:.1f} m"
                ax.text(
                    obs["east_m"] + 1.9,
                    obs["north_m"] + 1.6,
                    label,
                    fontsize=7.0,
                    color=PAPER_INK,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.88),
                    zorder=12,
                )

    def draw_safety_regions(ax, *, alpha: float = 0.13) -> None:
        for obs in planner_xy:
            ax.add_patch(
                patches.Circle(
                    (obs["east_m"], obs["north_m"]),
                    12.0,
                    facecolor=(0.69, 0.19, 0.16, alpha),
                    edgecolor="#a94d3e",
                    linewidth=1.0,
                    zorder=5,
                )
            )
            ax.scatter([obs["east_m"]], [obs["north_m"]], s=32, color="#a94d3e", zorder=8)

    def draw_grid_overlay(ax, *, route: bool) -> None:
        for cell_x, cell_y in sorted(occupied_cells):
            draw_cell(ax, cell_x, cell_y, (0.36, 0.40, 0.45, 0.10), "#7b8792", 0.55, 3)
        if route:
            for cell_x, cell_y in route_cells:
                draw_cell(ax, cell_x, cell_y, (0.69, 0.47, 0.16, 0.13), "#a06a2a", 0.95, 5)
            if route_cell_centers:
                ax.plot(
                    [pt[0] for pt in route_cell_centers],
                    [pt[1] for pt in route_cell_centers],
                    color="#8f5b1d",
                    linewidth=1.55,
                    zorder=6,
                )

    ax = axes[0]
    draw_common_context(ax)
    draw_published_tracks(ax, labels=False, faint=True)
    apply_common_view(ax)
    panel_title(
        ax,
        1,
        "Detect",
        f"frame {int(vision_evt['frame'])}: {frame_counts(vision_evt)['raw']} raw boxes\n"
        f"{frame_counts(vision_evt)['projected']} projected; mapped to local frame",
    )

    ax = axes[1]
    draw_common_context(ax)
    draw_published_tracks(ax, labels=True)
    apply_common_view(ax)
    panel_title(
        ax,
        2,
        "Label and Track",
        f"{frame_counts(vision_evt)['published']} outgoing tracks in trigger frame\n"
        f"{int(route_evt['planner_obs_count'])} nearest tracks kept for planning",
    )

    ax = axes[2]
    draw_common_context(ax)
    draw_published_tracks(ax, labels=False, faint=True)
    draw_safety_regions(ax)
    ax.add_patch(
        patches.Circle(
            (0.0, 0.0),
            reaction_m,
            fill=False,
            edgecolor="#496d8d",
            linewidth=1.35,
            linestyle="--",
            zorder=4,
        )
    )
    nearest = min(planner_xy, key=lambda obs: obs["distance_m"])
    ax.plot([0.0, nearest["east_m"]], [0.0, nearest["north_m"]], color="#496d8d", linewidth=1.05, zorder=6)
    ax.text(
        nearest["east_m"] + 2.0,
        nearest["north_m"] + 2.2,
        f"nearest {float(route_evt['nearest_distance_m']):.2f} m",
        fontsize=7.0,
        color=PAPER_INK,
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.9),
        zorder=12,
    )
    apply_common_view(ax)
    panel_title(
        ax,
        3,
        "Measure Risk",
        f"d_nearest={float(route_evt['nearest_distance_m']):.2f} m < D_react={reaction_m:.1f} m\n"
        f"speed={speed_mps:.1f} m/s",
    )

    ax = axes[3]
    draw_common_context(ax)
    draw_safety_regions(ax, alpha=0.08)
    draw_grid_overlay(ax, route=True)
    apply_common_view(ax)
    panel_title(
        ax,
        4,
        "Plan Bypass",
        f"A* on {int(2 * 40 + 1)}x{int(2 * 40 + 1)} grid, cell={cell_size:.0f} m\n"
        f"route={int(route_evt['route_points'])} points / {len(route_cell_centers)} cells",
    )

    ax = axes[4]
    draw_common_context(ax, executed=True)
    draw_grid_overlay(ax, route=True)
    if len(evasion_df) > 2:
        evasion_xy = evasion_df[["east_m", "north_m"]].to_numpy()
        segments = np.concatenate([evasion_xy[:-1, None, :], evasion_xy[1:, None, :]], axis=1)
        lc = LineCollection(segments, cmap="plasma", linewidth=2.0, zorder=7)
        lc.set_array(np.linspace(0.0, 1.0, len(segments)))
        ax.add_collection(lc)
    if track_snapshots:
        tx = [snap["east_m"] for snap in track_snapshots]
        ty = [snap["north_m"] for snap in track_snapshots]
        tt = [snap["t_rel_s"] for snap in track_snapshots]
        ax.scatter(tx, ty, c=tt, cmap="viridis", s=30, marker="x", linewidths=1.4, zorder=8)
    ax.scatter([evasion_df["east_m"].iloc[0]], [evasion_df["north_m"].iloc[0]], s=32, color="#24303d", zorder=8)
    ax.scatter([evasion_df["east_m"].iloc[len(evasion_df) // 2]], [evasion_df["north_m"].iloc[len(evasion_df) // 2]], s=38, color="#a06a2a", marker="s", zorder=8)
    apply_common_view(ax)
    panel_title(
        ax,
        5,
        "Recalculate",
        "successive frames update the biker trace\nwhile the active bypass is executed",
    )

    ax = axes[5]
    draw_common_context(ax, executed=True)
    draw_published_tracks(ax, selected_only=True, labels=False, faint=True)
    ax.plot(full_df["east_m"], full_df["north_m"], color="#66727c", linewidth=1.15, alpha=0.9, label="executed flight", zorder=5)
    ax.plot(evasion_df["east_m"], evasion_df["north_m"], color="#a06a2a", linewidth=2.05, label="PORCE active", zorder=7)
    ax.scatter([evasion_df["east_m"].iloc[0]], [evasion_df["north_m"].iloc[0]], s=38, color="#24303d", zorder=8)
    ax.scatter([evasion_df["east_m"].iloc[-1]], [evasion_df["north_m"].iloc[-1]], s=42, color="#a06a2a", marker="s", zorder=8)
    apply_common_view(ax)
    panel_title(
        ax,
        6,
        "Rejoin",
        f"evasion active for {end_ts - start_ts:.2f} s\nnominal WP{waypoint_idx} tracking resumes",
    )

    sequence_legend = [
        Line2D([0], [0], color="#87929d", linestyle="--", linewidth=1.1, label="Nominal corridor"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#24303d", markeredgecolor="#24303d", markersize=6, label="Trigger / drone"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor="#b9802b", markeredgecolor="#b9802b", markersize=9, label=f"WP{waypoint_idx}"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#a94d3e", markeredgecolor="#a94d3e", markersize=6, label="Planner track"),
        patches.Patch(facecolor=(0.69, 0.19, 0.16, 0.13), edgecolor="#a94d3e", label="12 m protected region"),
        patches.Patch(facecolor=(0.36, 0.40, 0.45, 0.10), edgecolor="#7b8792", label="Occupied planner cells"),
        patches.Patch(facecolor=(0.69, 0.47, 0.16, 0.13), edgecolor="#a06a2a", label="Bypass cells"),
        Line2D([0], [0], color="#a06a2a", linewidth=2.0, label="Executed evasion"),
    ]
    fig.legend(
        handles=sequence_legend,
        loc="lower center",
        ncol=4,
        framealpha=0.96,
        bbox_to_anchor=(0.5, 0.008),
        fontsize=8.2,
    )
    fig.subplots_adjust(left=0.055, right=0.985, top=0.975, bottom=0.13)
    fig.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_architecture_figure(output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.6, 6.2))
    ax.set_xlim(0.2, 15.4)
    ax.set_ylim(0.55, 8.0)
    ax.axis("off")

    def section_label(x: float, y: float, text: str) -> None:
        ax.text(x, y, text.upper(), fontsize=9, fontweight="bold", color="#6b7580", ha="left", va="bottom")
        ax.plot([x, x + 1.7], [y - 0.12, y - 0.12], color="#c6cfd8", linewidth=1.0)

    def box(x: float, y: float, w: float, h: float, text: str, fc: str, fontsize: float = 9.8) -> None:
        rect = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.14,rounding_size=0.08",
            linewidth=1.0,
            edgecolor=PAPER_LINE,
            facecolor=fc,
            zorder=3.0,
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2.0,
            y + h / 2.0,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            color=PAPER_INK,
            linespacing=1.25,
            zorder=4.0,
        )

    def poly_arrow(
        points: list[tuple[float, float]],
        *,
        label: str = "",
        linestyle: str = "-",
        label_xy: tuple[float, float] | None = None,
        label_va: str = "bottom",
    ) -> None:
        if len(points) < 2:
            return
        for p1, p2 in zip(points[:-2], points[1:-1]):
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=PAPER_LINE, lw=1.15, linestyle=linestyle, zorder=1.0)
        ann = ax.annotate(
            "",
            xy=points[-1],
            xytext=points[-2],
            arrowprops=dict(arrowstyle="->", lw=1.15, color=PAPER_LINE, linestyle=linestyle, shrinkA=0, shrinkB=0),
        )
        ann.set_zorder(5.0)
        if label:
            lx, ly = label_xy if label_xy is not None else points[len(points) // 2]
            ax.text(
                lx,
                ly,
                label,
                ha="center",
                va=label_va,
                fontsize=8.45,
                color=PAPER_INK,
                bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.94),
                zorder=6.0,
            )

    section_label(0.7, 7.4, "Inputs")
    section_label(4.1, 7.4, "Runtime")
    section_label(12.1, 7.4, "Audit")

    box(0.7, 5.55, 2.45, 0.98, "Mission file\npipeline/ejea_default.waypoints", PAPER_BOX, fontsize=9.25)
    box(0.7, 3.55, 2.45, 0.98, "Viewport or video source\nCesium / Unreal capture", PAPER_BOX, fontsize=9.25)
    box(0.7, 1.55, 2.45, 0.98, "MAVLink telemetry\nSITL vehicle state", PAPER_BOX, fontsize=9.25)
    box(
        4.1,
        4.55,
        3.75,
        1.55,
        "Brain\nflight_controller.py\nWaypoint logic, obstacle tracks,\ndynamic reaction horizon, and failsafe",
        PAPER_COOL,
        fontsize=9.45,
    )
    box(
        4.1,
        1.55,
        3.75,
        1.35,
        "Vision system\nvision_system.py + GeoProjector\nYOLO detections and ground projection",
        PAPER_COOL,
        fontsize=9.2,
    )
    box(8.9, 4.75, 2.55, 1.05, "PORCE planner\nporce_manager.py\nBounded local A*", PAPER_WARM, fontsize=9.4)
    box(8.9, 1.75, 2.55, 1.15, "Autopilot and SITL\nmission execution", PAPER_BOX, fontsize=9.2)
    box(12.1, 5.15, 3.0, 0.98, "Shared state API\n/api/state/latest and UI status", PAPER_BOX, fontsize=9.0)
    box(
        12.1,
        1.6,
        3.0,
        1.72,
        "Zero-trust artifacts\nvision events.jsonl + saved frames\nbrain events.jsonl + trajectory.csv",
        PAPER_BOX,
        fontsize=8.9,
    )

    poly_arrow([(3.15, 6.04), (3.62, 6.04), (3.62, 5.32), (4.1, 5.32)], label="active waypoint", label_xy=(3.62, 6.24))
    poly_arrow([(3.15, 4.04), (3.55, 4.04), (3.55, 2.22), (4.1, 2.22)], label="image stream", label_xy=(3.46, 4.24))
    poly_arrow([(3.15, 2.04), (3.72, 2.04), (3.72, 4.84), (4.1, 4.84)], label="telemetry", label_xy=(3.42, 3.34))
    poly_arrow([(5.75, 4.55), (5.75, 2.9)], label="fused state", label_xy=(5.08, 3.74))
    poly_arrow([(6.8, 2.9), (6.8, 4.55)], label="published tracks", label_xy=(7.48, 3.78))
    poly_arrow([(7.85, 5.72), (8.24, 5.72), (8.24, 6.34), (8.62, 6.34), (8.62, 5.62), (8.9, 5.62)], label="route request", label_xy=(8.44, 6.5))
    poly_arrow([(8.9, 5.06), (8.52, 5.06), (8.52, 4.58), (7.85, 4.58)], label="local route", label_xy=(8.38, 4.34), label_va="top")
    poly_arrow([(7.85, 4.78), (8.22, 4.78), (8.22, 3.26), (10.18, 3.26), (10.18, 2.9)], label="setpoints", label_xy=(8.66, 3.42))
    poly_arrow([(10.0, 2.9), (10.0, 4.18), (8.58, 4.18), (8.58, 5.18), (7.85, 5.18)], label="telemetry", label_xy=(10.46, 3.46))
    poly_arrow([(7.85, 5.92), (8.34, 5.92), (8.34, 6.56), (11.55, 6.56), (11.55, 5.64), (12.1, 5.64)], label="UI state", label_xy=(10.05, 6.72))
    poly_arrow([(7.85, 5.0), (8.16, 5.0), (8.16, 4.34), (11.45, 4.34), (11.45, 3.08), (12.1, 3.08)], linestyle="--", label="brain audit", label_xy=(10.18, 4.5))
    poly_arrow([(7.85, 2.12), (11.2, 2.12), (11.2, 2.55), (12.1, 2.55)], linestyle="--", label="vision audit", label_xy=(10.05, 1.84))

    ax.plot([0.8, 1.45], [0.92, 0.92], color=PAPER_LINE, lw=1.15)
    ax.text(1.6, 0.92, "runtime data and control", fontsize=8.6, color=PAPER_INK, va="center")
    ax.plot([5.0, 5.65], [0.92, 0.92], color=PAPER_LINE, lw=1.15, linestyle="--")
    ax.text(5.8, 0.92, "audit and observability", fontsize=8.6, color=PAPER_INK, va="center")

    fig.subplots_adjust(left=0.03, right=0.98, top=0.96, bottom=0.06)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def build_porce_method_figure(output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.6, 6.45))
    ax.set_xlim(0.2, 15.8)
    ax.set_ylim(0.05, 7.95)
    ax.axis("off")

    def box(x: float, y: float, w: float, h: float, text: str, fc: str, fontsize: float = 10.0) -> None:
        rect = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.14,rounding_size=0.08",
            linewidth=1.0,
            edgecolor=PAPER_LINE,
            facecolor=fc,
            zorder=3.0,
        )
        ax.add_patch(rect)
        ax.text(
            x + w / 2.0,
            y + h / 2.0,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            color=PAPER_INK,
            linespacing=1.23,
            zorder=4.0,
        )

    def diamond(cx: float, cy: float, w: float, h: float, text: str) -> None:
        poly = patches.Polygon(
            [(cx, cy + h / 2.0), (cx + w / 2.0, cy), (cx, cy - h / 2.0), (cx - w / 2.0, cy)],
            closed=True,
            linewidth=1.0,
            edgecolor=PAPER_LINE,
            facecolor="#eef2f6",
            zorder=3.0,
        )
        ax.add_patch(poly)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=9.15, color=PAPER_INK, linespacing=1.15, zorder=4.0)

    def poly_arrow(
        points: list[tuple[float, float]],
        *,
        label: str = "",
        linestyle: str = "-",
        label_xy: tuple[float, float] | None = None,
        label_va: str = "bottom",
    ) -> None:
        if len(points) < 2:
            return
        for p1, p2 in zip(points[:-2], points[1:-1]):
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=PAPER_LINE, lw=1.15, linestyle=linestyle, zorder=1.0)
        ann = ax.annotate(
            "",
            xy=points[-1],
            xytext=points[-2],
            arrowprops=dict(arrowstyle="->", lw=1.15, color=PAPER_LINE, linestyle=linestyle, shrinkA=0, shrinkB=0),
        )
        ann.set_zorder(5.0)
        if label:
            lx, ly = label_xy if label_xy is not None else points[len(points) // 2]
            ax.text(
                lx,
                ly,
                label,
                ha="center",
                va=label_va,
                fontsize=8.45,
                color=PAPER_INK,
                bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.94),
                zorder=6.0,
            )

    ax.text(0.7, 7.28, "CONTROL LOOP", fontsize=9, fontweight="bold", color="#6b7580", ha="left")
    ax.plot([0.7, 2.18], [7.14, 7.14], color="#c6cfd8", linewidth=1.0)
    ax.text(0.7, 1.26, "AUDIT OUTPUTS", fontsize=9, fontweight="bold", color="#6b7580", ha="left")
    ax.plot([0.7, 2.18], [1.12, 1.12], color="#c6cfd8", linewidth=1.0)

    box(0.55, 5.88, 2.3, 1.02, "Refresh telemetry,\nactive waypoint,\nand obstacle tracks", PAPER_BOX, fontsize=9.3)
    box(3.12, 5.88, 2.48, 1.02, "Canonicalize\nperson / bicycle /\nbiker into protected tracks", PAPER_COOL, fontsize=9.25)
    box(5.88, 5.88, 2.68, 1.02, "Compute dynamic\nreaction horizon\nand nearest obstacle", PAPER_COOL, fontsize=9.2)
    diamond(9.95, 6.39, 2.35, 1.7, "Obstacle inside\nreaction horizon?")
    box(12.35, 5.88, 2.55, 1.02, "Keep nominal\nwaypoint tracking", PAPER_BOX, fontsize=9.1)

    box(5.6, 3.55, 2.75, 1.08, "Build bounded planner subset\nmax 55 m, up to 16 tracks", PAPER_COOL, fontsize=9.15)
    box(8.78, 3.55, 2.75, 1.08, "Run PORCE A*\n81 x 81 grid, 6 m cells,\ngoal = current waypoint", PAPER_WARM, fontsize=9.0)
    diamond(12.55, 4.09, 1.95, 1.34, "Valid\nlocal route?")
    box(9.25, 2.35, 2.8, 0.94, "Failsafe ladder\nhold, lateral replan,\nLAND or RTL", PAPER_WARM, fontsize=8.9)
    box(11.25, 0.98, 3.15, 0.94, "Execute PORCE sub-goals\nand rejoin current waypoint", PAPER_COOL, fontsize=8.9)

    box(0.78, 0.22, 2.55, 0.72, "decision_snapshot", PAPER_BOX, fontsize=8.95)
    box(3.78, 0.22, 3.05, 0.72, "evasion_route_generated\nplanner_obs_count and route_points", PAPER_BOX, fontsize=8.75)
    box(7.28, 0.22, 2.85, 0.72, "trajectory.csv\nand evasion progress", PAPER_BOX, fontsize=8.95)
    box(10.58, 0.22, 3.35, 0.72, "evasion_completed\nor failsafe event", PAPER_BOX, fontsize=8.95)

    poly_arrow([(2.85, 6.39), (3.12, 6.39)])
    poly_arrow([(5.6, 6.39), (5.88, 6.39)])
    poly_arrow([(8.56, 6.39), (8.78, 6.39)])
    poly_arrow([(11.12, 6.39), (12.35, 6.39)], label="no", label_xy=(11.72, 6.56))
    poly_arrow([(9.95, 5.54), (9.95, 4.95), (6.98, 4.95), (6.98, 4.63)], label="yes", label_xy=(8.45, 5.14))
    poly_arrow([(8.35, 4.09), (8.78, 4.09)])
    poly_arrow([(11.53, 4.09), (11.88, 4.09)])
    poly_arrow([(13.52, 4.09), (14.3, 4.09), (14.3, 3.45), (10.65, 3.45), (10.65, 3.29)], label="no", label_xy=(14.0, 4.28))
    poly_arrow([(12.55, 3.42), (12.55, 2.05), (12.82, 2.05), (12.82, 1.92)], label="yes", label_xy=(12.14, 2.52), label_va="top")
    poly_arrow([(14.4, 1.45), (15.25, 1.45), (15.25, 6.39), (14.9, 6.39)], label="rejoin", label_xy=(15.02, 3.98))

    poly_arrow([(1.7, 5.88), (1.95, 0.94)], linestyle="--")
    poly_arrow([(10.15, 3.55), (10.15, 3.36), (8.45, 3.36), (8.45, 0.94), (5.3, 0.94)], linestyle="--")
    poly_arrow([(12.8, 0.98), (12.8, 0.94), (8.7, 0.94)], linestyle="--")
    poly_arrow([(10.65, 2.35), (10.65, 0.82), (12.25, 0.82), (12.25, 0.94)], linestyle="--")

    fig.subplots_adjust(left=0.03, right=0.98, top=0.97, bottom=0.04)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def build_e2e_ablation_figure(mission: list[MissionPoint], output_path: Path) -> dict:
    frames = {label: parse_e2e_status_log(path) for label, path in E2E_RUNS.items()}

    home = mission[0]
    mission_xy = [latlon_to_enu(home.lat, home.lon, wp.lat, wp.lon) for wp in mission]

    fig, ax = plt.subplots(figsize=(7.4, 5.5))
    mx = [p[0] for p in mission_xy]
    my = [p[1] for p in mission_xy]
    ax.plot(mx, my, linestyle="--", color="#7f8c8d", linewidth=1.3, label="Mission waypoints")
    ax.scatter(mx, my, color="#7f8c8d", s=18)

    styles = {
        "PORCE on + detections": {"color": "#b25f36", "lw": 2.3, "label": "PORCE on + detections"},
        "PORCE off + detections": {"color": "#496d8d", "lw": 1.8, "label": "PORCE off + detections"},
        "PORCE on + no detections": {"color": "#688475", "lw": 1.4, "label": "PORCE on + no detections"},
        "PORCE off + no detections": {"color": "#9aa4ad", "lw": 1.2, "label": "PORCE off + no detections"},
    }

    # Statistical campaign runs (faint, drawn first so representative runs stay on top).
    campaign = discover_campaign_runs()
    campaign_stats: dict[str, dict] = {}
    for label, logs in campaign.items():
        durations: list[float] = []
        lengths: list[float] = []
        completed = 0
        for log_path in logs:
            cdf = parse_e2e_status_log(log_path)
            if cdf.empty:
                continue
            xy = np.array([latlon_to_enu(home.lat, home.lon, lat, lon) for lat, lon in zip(cdf["lat"], cdf["lon"])])
            ax.plot(
                xy[:, 0],
                xy[:, 1],
                color=styles[label]["color"],
                linewidth=0.7,
                alpha=0.28,
                zorder=2,
            )
            durations.append(float(cdf["t_s"].iloc[-1]))
            lengths.append(float(cdf["segment_m"].sum()))
            if int(cdf["wp_idx"].max()) >= 12:
                completed += 1
        if durations:
            campaign_stats[label] = {
                "runs": len(durations),
                "completed": completed,
                "duration_mean_s": round(float(np.mean(durations)), 1),
                "duration_std_s": round(float(np.std(durations, ddof=1)) if len(durations) > 1 else 0.0, 1),
                "path_mean_m": round(float(np.mean(lengths)), 1),
                "path_std_m": round(float(np.std(lengths, ddof=1)) if len(lengths) > 1 else 0.0, 1),
            }

    metrics_rows: list[dict] = []
    for label, df in frames.items():
        if df.empty:
            continue
        xy = np.array([latlon_to_enu(home.lat, home.lon, lat, lon) for lat, lon in zip(df["lat"], df["lon"])])
        ax.plot(
            xy[:, 0],
            xy[:, 1],
            color=styles[label]["color"],
            linewidth=styles[label]["lw"],
            label=styles[label]["label"],
            zorder=4,
        )
        metrics_rows.append(
            {
                "scenario": label,
                "duration_s": round(float(df["t_s"].iloc[-1]), 1),
                "path_length_m": round(float(df["segment_m"].sum()), 1),
                "max_wp_idx": int(df["wp_idx"].max()),
                "mean_obstacles": round(float(df["obs_count"].mean()), 2),
            }
        )

    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    style_paper_axes(ax)
    ax.legend(loc="lower left", frameon=True, framealpha=0.96)
    ax.set_aspect("equal", adjustable="box")

    zoom_pad = 45.0
    ax.set_xlim(min(mx) - 20.0, max(mx[:3]) + zoom_pad)
    ax.set_ylim(min(my[:3]) - zoom_pad, max(my[:3]) + 20.0)

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    save_csv(
        DATA_DIR / "e2e_ablation_metrics.csv",
        metrics_rows,
        ["scenario", "duration_s", "path_length_m", "max_wp_idx", "mean_obstacles"],
    )
    if campaign_stats:
        stat_rows = [
            {
                "scenario": label,
                "runs": stats["runs"],
                "completed": stats["completed"],
                "duration_mean_s": stats["duration_mean_s"],
                "duration_std_s": stats["duration_std_s"],
                "path_mean_m": stats["path_mean_m"],
                "path_std_m": stats["path_std_m"],
            }
            for label, stats in campaign_stats.items()
        ]
        save_csv(
            DATA_DIR / "e2e_campaign_stats.csv",
            stat_rows,
            ["scenario", "runs", "completed", "duration_mean_s", "duration_std_s", "path_mean_m", "path_std_m"],
        )
    out = {row["scenario"]: row for row in metrics_rows}
    for label, stats in campaign_stats.items():
        out.setdefault(label, {})
        out[label] = {**out.get(label, {}), "campaign": stats}
    return out


def build_case_study_assets(mission: list[MissionPoint]) -> dict:
    traj = pd.read_csv(CASE_TRAJECTORY)
    brain_events = parse_jsonl(CASE_BRAIN_EVENTS)
    vision_events = parse_jsonl(CASE_VISION_EVENTS)
    route_evt = min(
        (evt for evt in brain_events if evt.get("kind") == "evasion_route_generated"),
        key=lambda evt: abs(float(evt["ts"]) - float(CASE_ROUTE_TS)),
    )
    start_ts = float(route_evt["ts"])
    end_evt = next(
        evt for evt in brain_events if evt.get("kind") == "evasion_completed" and float(evt["ts"]) >= start_ts
    )
    end_ts = float(end_evt["ts"])

    planner_obs_count = max(1, int(route_evt.get("planner_obs_count", 1) or 1))
    nearest_type = str(route_evt.get("nearest_type") or "").strip().lower()

    def matches_nearest(value) -> bool:
        v = str(value or "").strip().lower()
        if v == nearest_type:
            return True
        # brain canonicalizes "biker" -> "bike"; vision logs the detector class
        return nearest_type in BIKER_TYPES and v in BIKER_TYPES

    candidate_vision = [
        evt
        for evt in vision_events
        if evt.get("kind") == "vision_frame"
        and isinstance(evt.get("outgoing"), list)
        and evt.get("outgoing")
        and abs(float(evt["ts"]) - start_ts) <= 0.75
    ]
    vision_evt = min(
        candidate_vision,
        key=lambda evt: (
            0 if any(matches_nearest(obs.get("type")) for obs in evt.get("outgoing", [])) else 1,
            abs(float(evt["ts"]) - start_ts),
            len(evt.get("outgoing", [])),
        ),
    )

    published_tracks = sorted(
        [obs for obs in vision_evt.get("outgoing", []) if matches_nearest(obs.get("type"))],
        key=lambda obs: float(obs.get("distance", 1e9)),
    )
    planner_tracks = published_tracks[:planner_obs_count]

    pretrigger_traj = traj[traj["ts"] <= start_ts]
    if pretrigger_traj.empty:
        origin_row = traj.iloc[(traj["ts"] - start_ts).abs().argmin()]
    else:
        origin_row = pretrigger_traj.iloc[-1]

    lat_ref = float(origin_row["lat"])
    lon_ref = float(origin_row["lon"])
    waypoint_idx = int(route_evt.get("wp_idx", 0) or 0)
    waypoint = mission[min(max(0, waypoint_idx), len(mission) - 1)]
    waypoint_xy = latlon_to_enu(lat_ref, lon_ref, waypoint.lat, waypoint.lon)

    traj["east_m"] = traj.apply(lambda row: latlon_to_enu(lat_ref, lon_ref, float(row["lat"]), float(row["lon"]))[0], axis=1)
    traj["north_m"] = traj.apply(lambda row: latlon_to_enu(lat_ref, lon_ref, float(row["lat"]), float(row["lon"]))[1], axis=1)

    evasion_df = traj[(traj["ts"] >= start_ts) & (traj["ts"] <= end_ts) & (traj["evasion_active"] == 1)].copy()
    full_df = traj[(traj["ts"] >= start_ts - 8.0) & (traj["ts"] <= end_ts + 6.0)].copy()
    mission_segment = mission[max(0, waypoint_idx - 1) : min(len(mission), waypoint_idx + 2)]
    mission_xy = np.array([latlon_to_enu(lat_ref, lon_ref, wp.lat, wp.lon) for wp in mission_segment])

    planner_xy = []
    for idx, obs in enumerate(planner_tracks, start=1):
        east, north = latlon_to_enu(lat_ref, lon_ref, float(obs["lat"]), float(obs["lon"]))
        planner_xy.append(
            {
                "label": f"{nearest_type} {idx}",
                "east_m": east,
                "north_m": north,
                "distance_m": float(obs["distance"]),
                "type": str(obs.get("type") or nearest_type),
                "confidence": float(obs.get("confidence", 0.0) or 0.0),
                "id": obs.get("id", idx),
                "bbox": dict(obs.get("bbox", {})),
            }
        )

    published_xy = []
    for obs in published_tracks:
        east, north = latlon_to_enu(lat_ref, lon_ref, float(obs["lat"]), float(obs["lon"]))
        published_xy.append(
            {
                "east_m": east,
                "north_m": north,
                "distance_m": float(obs["distance"]),
                "bbox": dict(obs.get("bbox", {})),
                "selected": obs in planner_tracks,
                "type": str(obs.get("type") or nearest_type),
                "confidence": float(obs.get("confidence", 0.0) or 0.0),
                "id": obs.get("id", "-"),
            }
        )

    reaction_events = [
        evt
        for evt in brain_events
        if evt.get("kind") == "decision_snapshot"
        and evt.get("reaction_distance_eval_m") is not None
        and abs(float(evt["ts"]) - start_ts) <= 1.0
    ]
    reaction_evt = min(reaction_events, key=lambda evt: abs(float(evt["ts"]) - start_ts)) if reaction_events else {}
    reaction_m = float(reaction_evt.get("reaction_distance_eval_m", 45.0))
    speed_mps = float(reaction_evt.get("speed_mps", 0.0) or 0.0)

    track_snapshots: list[dict] = []
    for evt in vision_events:
        if evt.get("kind") != "vision_frame" or not isinstance(evt.get("outgoing"), list) or not evt.get("outgoing"):
            continue
        t_rel = float(evt["ts"]) - start_ts
        if t_rel < -0.35 or t_rel > 1.65:
            continue
        frame_tracks = sorted(
            [
                obs
                for obs in evt.get("outgoing", [])
                if matches_nearest(obs.get("type")) and obs.get("lat") is not None and obs.get("lon") is not None
            ],
            key=lambda obs: float(obs.get("distance", 1e9)),
        )[:3]
        for obs in frame_tracks:
            east, north = latlon_to_enu(lat_ref, lon_ref, float(obs["lat"]), float(obs["lon"]))
            track_snapshots.append(
                {
                    "frame": int(evt.get("frame", 0) or 0),
                    "t_rel_s": t_rel,
                    "east_m": east,
                    "north_m": north,
                    "distance_m": float(obs.get("distance", 0.0) or 0.0),
                    "confidence": float(obs.get("confidence", 0.0) or 0.0),
                    "id": obs.get("id", "-"),
                }
            )

    import sys

    if str(PIPELINE_DIR) not in sys.path:
        sys.path.insert(0, str(PIPELINE_DIR))
    from porce_manager import PorcePlanner

    proxy_planner = PorcePlanner()
    proxy_path = proxy_planner.plan_route(
        lat_ref,
        lon_ref,
        waypoint.lat,
        waypoint.lon,
        [{"lat": float(obs["lat"]), "lon": float(obs["lon"])} for obs in planner_tracks],
    )
    if not proxy_path:
        raise RuntimeError("Unable to reconstruct proxy planner path for audited case study.")

    cell_size = float(proxy_planner.cell_size)
    safety_cells = max(0, int(math.ceil(float(proxy_planner.safety_radius_m) / cell_size)))

    def to_cell(east_m: float, north_m: float) -> tuple[int, int]:
        return int(east_m / cell_size), int(north_m / cell_size)

    route_cells: list[tuple[int, int]] = []
    route_xy: list[tuple[float, float]] = []
    for point in proxy_path:
        east, north = latlon_to_enu(lat_ref, lon_ref, float(point["lat"]), float(point["lon"]))
        route_xy.append((east, north))
        cell = to_cell(east, north)
        if not route_cells or route_cells[-1] != cell:
            route_cells.append(cell)

    occupied_cells: set[tuple[int, int]] = set()
    seed_groups: dict[tuple[int, int], list[dict]] = {}
    for obs in planner_xy:
        seed = to_cell(float(obs["east_m"]), float(obs["north_m"]))
        seed_groups.setdefault(seed, []).append(obs)
        for dx in range(-safety_cells, safety_cells + 1):
            for dy in range(-safety_cells, safety_cells + 1):
                occupied_cells.add((seed[0] + dx, seed[1] + dy))

    route_cell_centers = [(cell_x * cell_size, cell_y * cell_size) for cell_x, cell_y in route_cells]

    build_yolo_scene_overlay(
        route_evt,
        vision_evt,
        track_snapshots,
        origin_row,
        FIGURES_DIR / "porce_yolo_future_overlay.png",
    )
    build_six_stage_sequence_figure(
        mission_xy,
        waypoint_idx,
        waypoint_xy,
        route_evt,
        vision_evt,
        published_xy,
        planner_xy,
        occupied_cells,
        route_cells,
        route_cell_centers,
        full_df,
        evasion_df,
        cell_size,
        start_ts,
        end_ts,
        reaction_m,
        speed_mps,
        track_snapshots,
        FIGURES_DIR / "porce_six_stage_sequence.png",
    )

    fig = plt.figure(figsize=(12.8, 6.35))
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 4.0], wspace=0.34, hspace=0.24)
    ax_top = fig.add_subplot(grid[0, :])
    ax_cam = fig.add_subplot(grid[1, 0])
    ax_geo = fig.add_subplot(grid[1, 1])
    ax_grid = fig.add_subplot(grid[1, 2])

    ax_top.set_xlim(0, 12.3)
    ax_top.set_ylim(0, 1.8)
    ax_top.axis("off")

    def top_box(x: float, text: str) -> None:
        rect = patches.FancyBboxPatch(
            (x, 0.46),
            2.25,
            0.76,
            boxstyle="round,pad=0.12,rounding_size=0.08",
            linewidth=1.0,
            edgecolor=PAPER_LINE,
            facecolor=PAPER_BOX,
        )
        ax_top.add_patch(rect)
        ax_top.text(x + 1.125, 0.84, text, ha="center", va="center", fontsize=9.1, color=PAPER_INK)

    ladder = [
        (0.25, f"Raw boxes\n{int(vision_evt['counts']['raw_boxes'])}"),
        (3.15, f"Projected detections\n{int(vision_evt['counts']['accepted_frame_dets'])}"),
        (6.05, f"Published biker tracks\n{len(published_tracks)}"),
        (8.95, f"Planner subset\n{planner_obs_count} nearest"),
    ]
    for idx, (x_pos, text) in enumerate(ladder):
        top_box(x_pos, text)
        if idx < len(ladder) - 1:
            ax_top.annotate(
                "",
                xy=(ladder[idx + 1][0] - 0.12, 0.84),
                xytext=(x_pos + 2.38, 0.84),
                arrowprops=dict(arrowstyle="->", lw=1.15, color=PAPER_LINE, shrinkA=4, shrinkB=4),
            )
    ax_top.text(
        0.25,
        1.47,
        f"Trigger-side audit chain: frame {int(vision_evt['frame'])} at t = {float(vision_evt['ts']) - start_ts:+.3f} s",
        fontsize=8.9,
        color=PAPER_INK,
        ha="left",
    )
    ax_top.text(
        12.05,
        1.47,
        "same detections viewed in pixel, metric, and grid space",
        fontsize=8.8,
        color=PAPER_INK,
        ha="right",
    )

    ax_cam.set_xlim(0, 640)
    ax_cam.set_ylim(640, 0)
    ax_cam.set_facecolor("#f5f7f9")
    for spine in ax_cam.spines.values():
        spine.set_color("#6f7a85")
        spine.set_linewidth(0.9)
    ax_cam.set_xticks([0, 160, 320, 480, 640])
    ax_cam.set_yticks([0, 160, 320, 480, 640])
    ax_cam.grid(color=PAPER_GRID, alpha=0.85, linestyle=":", linewidth=0.8)
    ax_cam.set_title("Pixel Space: Published Tracks", fontsize=11, color=PAPER_INK)
    ax_cam.set_xlabel("Image x (px)")
    ax_cam.set_ylabel("Image y (px)")

    camera_offsets = [(8, 0), (18, -12), (18, 14), (8, 0)]
    for idx, obs in enumerate(published_xy):
        bbox = obs["bbox"]
        x1 = int(bbox.get("x1", 0))
        y1 = int(bbox.get("y1", 0))
        width = max(1, int(bbox.get("x2", 0)) - x1)
        height = max(1, int(bbox.get("y2", 0)) - y1)
        edge = "#a94d3e" if obs["selected"] else "#8c9aa5"
        face = (0.66, 0.30, 0.24, 0.10) if obs["selected"] else (0.55, 0.61, 0.66, 0.06)
        rect = patches.Rectangle((x1, y1), width, height, linewidth=1.4, edgecolor=edge, facecolor=face)
        ax_cam.add_patch(rect)
        dx, dy = camera_offsets[min(idx, len(camera_offsets) - 1)]
        ax_cam.text(
            x1 + width + dx,
            y1 + height / 2.0 + dy,
            f"{obs['distance_m']:.1f} m",
            fontsize=8.4,
            color=PAPER_INK,
            va="center",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.92),
        )
    ax_cam.text(
        14,
        616,
        "Only these 4 tracks leave the vision module",
        fontsize=8.1,
        color=PAPER_INK,
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.92),
    )

    ax_geo.plot([0.0, waypoint_xy[0]], [0.0, waypoint_xy[1]], linestyle="--", color="#93a0aa", linewidth=1.25)
    ax_geo.scatter([0.0], [0.0], s=42, color="#3d566e", label="Start / drone", zorder=5)
    ax_geo.scatter([waypoint_xy[0]], [waypoint_xy[1]], marker="*", s=160, color="#b9802b", label=f"WP{waypoint_idx} target", zorder=6)
    ground_offsets = [(2.2, -0.8), (-14.5, -8.0), (-14.5, 7.0), (2.4, 1.8)]
    for idx, obs in enumerate(published_xy):
        color = "#a94d3e" if obs["selected"] else "#8c9aa5"
        marker = "o" if obs["selected"] else "x"
        ax_geo.scatter(obs["east_m"], obs["north_m"], s=34, color=color, marker=marker, zorder=6)
        dx, dy = ground_offsets[min(idx, len(ground_offsets) - 1)]
        ax_geo.text(
            obs["east_m"] + dx,
            obs["north_m"] + dy,
            f"{obs['distance_m']:.1f}",
            fontsize=8.0,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.88),
        )
    ax_geo.set_title("Metric Space: Projection and Pruning", fontsize=11, color=PAPER_INK)
    ax_geo.set_xlabel("Local east (m)")
    ax_geo.set_ylabel("Local north (m)")
    style_paper_axes(ax_geo)
    ax_geo.set_aspect("equal", adjustable="box")
    geo_x = [0.0, waypoint_xy[0], *[obs["east_m"] for obs in published_xy]]
    geo_y = [0.0, waypoint_xy[1], *[obs["north_m"] for obs in published_xy]]
    ax_geo.set_xlim(min(geo_x) - 16.0, max(geo_x) + 16.0)
    ax_geo.set_ylim(min(geo_y) - 16.0, max(geo_y) + 16.0)
    geo_handles, geo_labels = ax_geo.get_legend_handles_labels()
    geo_handles.extend(
        [
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#a94d3e", markeredgecolor="#a94d3e", markersize=6, label="planner track"),
            Line2D([0], [0], marker="x", color="#8c9aa5", linestyle="none", markersize=6, label="published/pruned track"),
        ]
    )
    geo_labels.extend(["planner track", "published/pruned track"])
    ax_geo.legend(geo_handles, geo_labels, loc="upper left", framealpha=0.96, fontsize=7.7)

    def draw_cell(
        axis,
        cell_x: int,
        cell_y: int,
        *,
        facecolor: str | tuple,
        edgecolor: str,
        linewidth: float = 0.9,
        alpha: float = 1.0,
        zorder: int = 1,
    ) -> None:
        axis.add_patch(
            patches.Rectangle(
                (cell_x * cell_size - cell_size / 2.0, cell_y * cell_size - cell_size / 2.0),
                cell_size,
                cell_size,
                facecolor=facecolor,
                edgecolor=edgecolor,
                linewidth=linewidth,
                alpha=alpha,
                zorder=zorder,
            )
        )

    extent_cells = [*occupied_cells, *route_cells, (0, 0)]
    min_cell_x = min(cell[0] for cell in extent_cells) - 1
    max_cell_x = max(cell[0] for cell in extent_cells) + 1
    min_cell_y = min(cell[1] for cell in extent_cells) - 1
    max_cell_y = max(cell[1] for cell in extent_cells) + 1

    x_min = (min_cell_x - 0.5) * cell_size
    x_max = (max_cell_x + 0.5) * cell_size
    y_min = (min_cell_y - 0.5) * cell_size
    y_max = (max_cell_y + 0.5) * cell_size

    for boundary_x in np.arange((min_cell_x - 0.5) * cell_size, (max_cell_x + 1.0) * cell_size, cell_size):
        ax_grid.axvline(boundary_x, color=PAPER_GRID, linewidth=0.8, zorder=0)
    for boundary_y in np.arange((min_cell_y - 0.5) * cell_size, (max_cell_y + 1.0) * cell_size, cell_size):
        ax_grid.axhline(boundary_y, color=PAPER_GRID, linewidth=0.8, zorder=0)

    for cell_x, cell_y in sorted(occupied_cells):
        draw_cell(
            ax_grid,
            cell_x,
            cell_y,
            facecolor=(0.36, 0.40, 0.45, 0.10),
            edgecolor="#7b8792",
            linewidth=0.7,
            alpha=1.0,
            zorder=1,
        )
    for cell_x, cell_y in route_cells:
        draw_cell(
            ax_grid,
            cell_x,
            cell_y,
            facecolor=(0.69, 0.47, 0.16, 0.12),
            edgecolor="#a06a2a",
            linewidth=1.1,
            alpha=1.0,
            zorder=3,
        )

    if route_cell_centers:
        ax_grid.plot(
            [pt[0] for pt in route_cell_centers],
            [pt[1] for pt in route_cell_centers],
            color="#a06a2a",
            linewidth=1.8,
            zorder=4,
        )

    start_handle = ax_grid.scatter([0.0], [0.0], s=42, color="#24303d", label="Start cell", zorder=5)
    goal_handle = ax_grid.scatter(
        [route_cell_centers[-1][0]],
        [route_cell_centers[-1][1]],
        marker="*",
        s=150,
        color="#b9802b",
        label="Reached goal cell",
        zorder=6,
    )

    group_offsets = [(7.0, 5.5), (-18.0, 7.5), (6.0, -14.0)]
    for idx, ((seed_x, seed_y), group) in enumerate(sorted(seed_groups.items(), key=lambda item: min(g["distance_m"] for g in item[1]))):
        center_x = seed_x * cell_size
        center_y = seed_y * cell_size
        ax_grid.scatter([center_x], [center_y], s=34, color="#a94d3e", zorder=6)
        distances = [f"{obs['distance_m']:.1f}" for obs in group]
        if len(group) == 1:
            label_text = f"{distances[0]} m"
        else:
            label_text = f"{len(group)} tracks\n" + " / ".join(distances) + " m"
        dx, dy = group_offsets[min(idx, len(group_offsets) - 1)]
        ax_grid.text(
            center_x + dx,
            center_y + dy,
            label_text,
            fontsize=8.05,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.92),
            zorder=7,
        )

    occ_patch = patches.Patch(facecolor=(0.36, 0.40, 0.45, 0.10), edgecolor="#7b8792", label="Occupied cells")
    route_patch = patches.Patch(facecolor=(0.69, 0.47, 0.16, 0.12), edgecolor="#a06a2a", label="Proxy route cells")
    planner_handle = Line2D([0], [0], marker="o", color="none", markerfacecolor="#a94d3e", markeredgecolor="#a94d3e", markersize=6, label="Planner track seeds")
    ax_grid.legend(handles=[start_handle, goal_handle, planner_handle, route_patch, occ_patch], loc="upper left", framealpha=0.96, fontsize=7.7)
    ax_grid.set_title("Grid Space: Proxy Planner Input", fontsize=11, color=PAPER_INK)
    ax_grid.set_xlabel("Local east (m)")
    ax_grid.set_ylabel("Local north (m)")
    ax_grid.set_xlim(x_min, x_max)
    ax_grid.set_ylim(y_min, y_max)
    ax_grid.set_aspect("equal", adjustable="box")
    style_paper_axes(ax_grid)

    fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.09)
    fig.savefig(FIGURES_DIR / "porce_detection_montage.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.35, 5.85))

    traj_x = [waypoint_xy[0], *full_df["east_m"].tolist(), *[obs["east_m"] for obs in published_xy], *[pt[0] for pt in route_cell_centers]]
    traj_y = [waypoint_xy[1], *full_df["north_m"].tolist(), *[obs["north_m"] for obs in published_xy], *[pt[1] for pt in route_cell_centers]]
    x_min = math.floor((min(traj_x) - cell_size) / cell_size) * cell_size
    x_max = math.ceil((max(traj_x) + cell_size) / cell_size) * cell_size
    y_min = math.floor((min(traj_y) - cell_size) / cell_size) * cell_size
    y_max = math.ceil((max(traj_y) + cell_size) / cell_size) * cell_size

    for boundary_x in np.arange(x_min - cell_size / 2.0, x_max + cell_size, cell_size):
        ax.axvline(boundary_x, color=PAPER_GRID, linewidth=0.7, zorder=0)
    for boundary_y in np.arange(y_min - cell_size / 2.0, y_max + cell_size, cell_size):
        ax.axhline(boundary_y, color=PAPER_GRID, linewidth=0.7, zorder=0)

    for cell_x, cell_y in sorted(occupied_cells):
        draw_cell(
            ax,
            cell_x,
            cell_y,
            facecolor=(0.36, 0.40, 0.45, 0.08),
            edgecolor="#7b8792",
            linewidth=0.65,
            alpha=1.0,
            zorder=1,
        )
    for cell_x, cell_y in route_cells:
        draw_cell(
            ax,
            cell_x,
            cell_y,
            facecolor=(0.69, 0.47, 0.16, 0.10),
            edgecolor="#a06a2a",
            linewidth=1.0,
            alpha=1.0,
            zorder=3,
        )

    if len(mission_xy) > 1:
        ax.plot(mission_xy[:, 0], mission_xy[:, 1], "--", color="#8f99a2", linewidth=1.25, label="Mission segment")
    ax.plot(full_df["east_m"], full_df["north_m"], color="#66727c", linewidth=1.35, alpha=0.9, label="Executed flight", zorder=7)
    ax.plot(evasion_df["east_m"], evasion_df["north_m"], color="#a06a2a", linewidth=2.15, label="Executed evasion", zorder=8)
    ax.plot(
        [pt[0] for pt in route_cell_centers],
        [pt[1] for pt in route_cell_centers],
        color="#8f5b1d",
        linewidth=1.55,
        linestyle="-.",
        label="Proxy route cells",
        zorder=6,
    )
    ax.scatter([evasion_df["east_m"].iloc[0]], [evasion_df["north_m"].iloc[0]], s=52, color="#24303d", label="Trigger", zorder=7)
    ax.scatter([evasion_df["east_m"].iloc[-1]], [evasion_df["north_m"].iloc[-1]], s=52, color="#a06a2a", marker="s", label="Rejoin", zorder=7)
    ax.scatter([waypoint_xy[0]], [waypoint_xy[1]], marker="*", s=170, color="#b9802b", zorder=8)
    ax.text(waypoint_xy[0] + 2.5, waypoint_xy[1] + 2.0, f"WP{waypoint_idx}", fontsize=8.7, color=PAPER_INK)

    seed_offsets = [(7.2, 5.5), (-25.0, 8.0), (5.0, -16.0)]
    for idx, ((seed_x, seed_y), group) in enumerate(sorted(seed_groups.items(), key=lambda item: min(g["distance_m"] for g in item[1]))):
        center_x = seed_x * cell_size
        center_y = seed_y * cell_size
        ax.scatter([center_x], [center_y], marker="o", color="#a94d3e", s=38, zorder=8)
        dx, dy = seed_offsets[min(idx, len(seed_offsets) - 1)]
        if len(group) == 1:
            label_text = f"{group[0]['label']}\n{group[0]['distance_m']:.1f} m"
        else:
            distances = " / ".join(f"{obs['distance_m']:.1f}" for obs in group)
            label_text = f"{len(group)} bikers\n{distances} m"
        ax.text(
            center_x + dx,
            center_y + dy,
            label_text,
            fontsize=8.15,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.9),
            zorder=9,
        )

    for obs in published_xy:
        if obs["selected"]:
            continue
        ax.scatter(obs["east_m"], obs["north_m"], marker="x", color="#8c9aa5", s=34, zorder=7)
        ax.text(
            obs["east_m"] + 1.8,
            obs["north_m"] + 1.4,
            f"dropped\n{obs['distance_m']:.1f} m",
            fontsize=7.9,
            color=PAPER_INK,
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.88),
            zorder=8,
        )

    ax.set_xlabel("Local east (m)")
    ax.set_ylabel("Local north (m)")
    style_paper_axes(ax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(x_min - cell_size / 2.0, x_max + cell_size / 2.0)
    ax.set_ylim(y_min - cell_size / 2.0, y_max + cell_size / 2.0)
    handles, labels = ax.get_legend_handles_labels()
    handles.extend(
        [
            patches.Patch(facecolor=(0.36, 0.40, 0.45, 0.08), edgecolor="#7b8792", label="Occupied cells"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#a94d3e", markeredgecolor="#a94d3e", markersize=6, label="Planner track seeds"),
            Line2D([0], [0], marker="x", color="#8c9aa5", linestyle="none", markersize=6, label="Dropped published track"),
        ]
    )
    labels.extend(["Occupied cells", "Planner track seeds", "Dropped published track"])
    ax.legend(handles, labels, loc="upper right", framealpha=0.96, fontsize=8.4)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "porce_case_trajectory.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    decision_rows = []
    for evt in brain_events:
        if evt.get("kind") != "decision_snapshot":
            continue
        ts = float(evt["ts"])
        if ts < start_ts - 0.5 or ts > end_ts + 1.0:
            continue
        reaction = evt.get("reaction_distance_eval_m", evt.get("reaction_distance_m"))
        nearest_distance = evt.get("nearest_distance_m")
        if reaction is None or nearest_distance is None:
            continue
        decision_rows.append(
            {
                "t_rel_s": ts - start_ts,
                "reaction_distance_m": float(reaction),
                "nearest_distance_m": float(nearest_distance),
                "evasion_active": int(bool(evt.get("evasion_active"))),
            }
        )
    decisions = pd.DataFrame(decision_rows)

    planning_obstacles = [(float(obs["lat"]), float(obs["lon"])) for obs in planner_tracks]
    geometric_rows = []
    for row in evasion_df.itertuples():
        min_geo = min(haversine_m(float(row.lat), float(row.lon), lat, lon) for lat, lon in planning_obstacles)
        geometric_rows.append({"t_rel_s": float(row.ts) - start_ts, "min_geo_distance_m": min_geo})
    geometric_df = pd.DataFrame(geometric_rows)

    # Time-synchronized clearance: distance from the drone (interpolated from the
    # audited trajectory) to the nearest concurrently observed track of the
    # trigger class at each vision frame. With moving obstacles (the peloton
    # rides at ~20 m/s) the static trigger-seed proxy above is not meaningful
    # over the full maneuver; this series uses where the obstacles actually
    # were at each instant, as published by the perception audit stream.
    traj_sorted = traj.sort_values("ts").reset_index(drop=True)
    traj_ts_arr = traj_sorted["ts"].to_numpy(dtype=float)
    concurrent_rows = []
    for evt in vision_events:
        if evt.get("kind") != "vision_frame" or not isinstance(evt.get("outgoing"), list):
            continue
        ts = float(evt["ts"])
        if ts < start_ts - 0.5 or ts > end_ts + 1.0:
            continue
        tracked = [
            obs
            for obs in evt.get("outgoing", [])
            if matches_nearest(obs.get("type")) and obs.get("lat") is not None and obs.get("lon") is not None
        ]
        if not tracked:
            continue
        idx = int(np.searchsorted(traj_ts_arr, ts))
        idx = min(max(idx, 0), len(traj_sorted) - 1)
        if idx > 0 and abs(traj_ts_arr[idx - 1] - ts) < abs(traj_ts_arr[idx] - ts):
            idx -= 1
        if abs(traj_ts_arr[idx] - ts) > 0.8:
            continue
        drone_lat = float(traj_sorted.loc[idx, "lat"])
        drone_lon = float(traj_sorted.loc[idx, "lon"])
        dmin = min(
            haversine_m(drone_lat, drone_lon, float(obs["lat"]), float(obs["lon"])) for obs in tracked
        )
        concurrent_rows.append({"t_rel_s": ts - start_ts, "min_concurrent_m": float(dmin)})
    concurrent_df = pd.DataFrame(concurrent_rows)

    fig, ax = plt.subplots(figsize=(7.4, 4.9))
    ax.axvspan(0.0, end_ts - start_ts, color="#edf2f6", alpha=0.96, label="PORCE active")
    clearance_df = concurrent_df if not concurrent_df.empty else geometric_df.rename(
        columns={"min_geo_distance_m": "min_concurrent_m"}
    )
    ax.plot(
        clearance_df["t_rel_s"],
        clearance_df["min_concurrent_m"],
        color="#a94d3e",
        linewidth=2.1,
        label="Clearance to concurrently tracked obstacles",
    )
    ax.plot(
        decisions["t_rel_s"],
        decisions["reaction_distance_m"],
        color="#496d8d",
        linewidth=1.8,
        label="Dynamic reaction horizon",
    )
    ax.axhline(12.0, color="#5f8470", linestyle="--", linewidth=1.4, label="Safety radius (12 m)")
    ax.axhline(22.0, color="#7c7f84", linestyle=":", linewidth=1.4, label="Failsafe threshold (22 m)")
    ax.set_xlabel("Time from evasion trigger (s)")
    ax.set_ylabel("Distance (m)")
    style_paper_axes(ax)
    ax.set_ylim(
        0.0,
        max(float(decisions["reaction_distance_m"].max()), float(clearance_df["min_concurrent_m"].max())) + 8.0,
    )
    ax.legend(loc="upper left", framealpha=0.96)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "porce_case_timeseries.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    evasion_points = list(zip(evasion_df["lat"], evasion_df["lon"]))
    evasion_path_m = cumulative_path_length(evasion_points)
    evasion_straight_m = haversine_m(
        float(evasion_df["lat"].iloc[0]),
        float(evasion_df["lon"].iloc[0]),
        float(evasion_df["lat"].iloc[-1]),
        float(evasion_df["lon"].iloc[-1]),
    )

    case_metrics = {
        "trigger_distance_m": round(float(route_evt["nearest_distance_m"]), 2),
        "route_points": int(route_evt["route_points"]),
        "planner_obs_count": int(route_evt["planner_obs_count"]),
        "planner_obs_ids": list(route_evt.get("planner_obs_ids") or []),
        "pretrigger_frame": int(vision_evt["frame"]),
        "pretrigger_raw_boxes": int(vision_evt["counts"]["raw_boxes"]),
        "pretrigger_accepted_detections": int(vision_evt["counts"]["accepted_frame_dets"]),
        "pretrigger_published_tracks": int(len(published_tracks)),
        "pixel_audit_frame_used": int(vision_evt["frame"]),
        "pixel_audit_published_tracks": int(vision_evt["counts"]["published_outgoing"]),
        "clean_viewer_frame_archived": bool(
            (CASE_FRAMES_DIR / f"yolo_{int(vision_evt['frame']):06d}.jpg").exists()
            or any(
                (CASE_FRAMES_DIR / f"yolo_{int(vision_evt['frame']) + d:06d}.jpg").exists()
                for d in (1, -1, 2, -2, 3, -3)
            )
        ),
        "evasion_duration_s": round(end_ts - start_ts, 2),
        "min_concurrent_clearance_m": (
            round(float(concurrent_df["min_concurrent_m"].min()), 2) if not concurrent_df.empty else None
        ),
        "min_concurrent_clearance_over_safety_radius_m": (
            round(float(concurrent_df["min_concurrent_m"].min()) - 12.0, 2) if not concurrent_df.empty else None
        ),
        "static_seed_proxy_min_m": round(float(geometric_df["min_geo_distance_m"].min()), 2),
        "observed_max_reaction_m": round(float(decisions["reaction_distance_m"].max()), 2),
        "evasion_path_length_m": round(evasion_path_m, 2),
        "straight_line_equivalent_m": round(evasion_straight_m, 2),
        "local_detour_over_straight_m": round(evasion_path_m - evasion_straight_m, 2),
        "safety_radius_m": 12.0,
        "failsafe_threshold_m": 22.0,
    }
    return case_metrics


def main() -> None:
    ensure_dirs()
    mission = load_waypoints(PIPELINE_DIR / "ejea_default.waypoints")
    if should_generate_structural_png("pipeline_a_architecture"):
        build_architecture_figure(FIGURES_DIR / "pipeline_a_architecture.png")
    if should_generate_structural_png("porce_method_flow"):
        build_porce_method_figure(FIGURES_DIR / "porce_method_flow.png")
    e2e_metrics = build_e2e_ablation_figure(mission, FIGURES_DIR / "e2e_ablation_paths.png")
    case_metrics = build_case_study_assets(mission)

    summary = {
        "e2e_metrics": e2e_metrics,
        "case_metrics": case_metrics,
    }
    save_json(DATA_DIR / "paper_metrics.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
