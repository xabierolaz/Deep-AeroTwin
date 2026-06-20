from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

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
PIPELINE = REPO / "pipeline"

FIG3_NAME = "paper_figure_3_e2e_ablation.png"
FIG4_NAME = "paper_figure_4_audited_collision_evasion.png"

SAFETY_RADIUS_M = g.RS_M
FAILSAFE_RADIUS_M = 22.0
CELL_SIZE_M = g.CELL_SIZE_M

INK = g.INK
GRID = g.GRID
NOMINAL = g.NOMINAL
EVASION = g.EVASION
BLUE = "#2d638f"
GREEN = "#3f8b67"
RED = g.TOWER
PURPLE = "#765da8"

E2E_CAMPAIGN = PIPELINE / "logs" / "e2e" / "campaign_20260612_174114.json"
E2E_RUNS = {
    "Replanner on + detections": "porce_on_with_detections_20260612_174114_r02",
    "Replanner off + detections": "porce_off_with_detections_20260612_175232_r02",
    "Replanner on + no detections": "porce_on_no_detections_20260612_175937_r02",
    "Replanner off + no detections": "porce_off_no_detections_20260612_181014_r04",
}
E2E_STYLE = {
    "Replanner on + detections": dict(color=EVASION, linewidth=2.0, linestyle="-"),
    "Replanner off + detections": dict(color=BLUE, linewidth=1.45, linestyle="--"),
    "Replanner on + no detections": dict(color=GREEN, linewidth=1.25, linestyle="-."),
    "Replanner off + no detections": dict(color="#677482", linewidth=1.25, linestyle=":"),
}

AUDIT_RUN = PIPELINE / "logs" / "zero_trust" / "20260220_092802"
AUDIT_TRIGGER_TS = 1771576361.2000635
AUDIT_FRAME = 5053


parse_jsonl = g.parse_jsonl
latlon_to_enu = g.latlon_to_enu
valid_traj = g.valid_traj
nearest_row = g.nearest_row


def copy_to_latex_images(source: Path, filename: str) -> list[str]:
    copied = []
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
        target = image_dir / filename
        shutil.copyfile(source, target)
        copied.append(str(target))
    return copied


def add_enu(df: pd.DataFrame, lat_ref: float, lon_ref: float) -> pd.DataFrame:
    df = df.copy()
    xy = [latlon_to_enu(lat_ref, lon_ref, float(lat), float(lon)) for lat, lon in zip(df["lat"], df["lon"])]
    df["east"] = [p[0] for p in xy]
    df["north"] = [p[1] for p in xy]
    return df


def style_axis(ax, *, equal: bool = True) -> None:
    ax.grid(color=GRID, linestyle=":", linewidth=0.7)
    for spine in ax.spines.values():
        spine.set_color("#8b96a2")
        spine.set_linewidth(0.75)
    ax.tick_params(labelsize=7, colors=INK)
    ax.xaxis.label.set_size(8)
    ax.yaxis.label.set_size(8)
    if equal:
        ax.set_aspect("equal", adjustable="box")


def panel_label(ax, panel: str, title: str, *, dark: bool = False) -> None:
    face = INK if dark else "white"
    color = "white" if dark else INK
    ax.text(
        0.018,
        0.965,
        f"{panel}. {title}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        fontweight="bold",
        color=color,
        bbox=dict(boxstyle="round,pad=0.22", facecolor=face, edgecolor="none", alpha=0.94),
        zorder=100,
    )


def e2e_campaign_stats() -> dict[str, dict[str, float]]:
    campaign = json.loads(E2E_CAMPAIGN.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for item in campaign["results"]:
        grouped.setdefault(item["scenario"], []).append(item)
    out: dict[str, dict[str, float]] = {}
    scenario_label = {
        "porce_on_with_detections": "Replanner on + detections",
        "porce_off_with_detections": "Replanner off + detections",
        "porce_on_no_detections": "Replanner on + no detections",
        "porce_off_no_detections": "Replanner off + no detections",
    }
    for scenario, rows in grouped.items():
        label = scenario_label[scenario]
        durations = [float(row["metrics"]["duration_s"]) for row in rows]
        paths = [float(row["metrics"]["path_length_m"]) for row in rows]
        out[label] = {
            "n": float(len(rows)),
            "duration_mean_s": float(np.mean(durations)),
            "path_mean_m": float(np.mean(paths)),
            "duration_std_s": float(np.std(durations, ddof=0)),
            "path_std_m": float(np.std(paths, ddof=0)),
        }
    return out


def load_e2e_traces() -> tuple[dict[str, pd.DataFrame], tuple[float, float], dict]:
    traces: dict[str, pd.DataFrame] = {}
    ref: tuple[float, float] | None = None
    campaign = json.loads(E2E_CAMPAIGN.read_text(encoding="utf-8"))
    inject_meta = {}
    for label, run_name in E2E_RUNS.items():
        df = valid_traj(pd.read_csv(PIPELINE / "logs" / "e2e" / run_name / "brain" / "trajectory.csv"))
        if ref is None:
            ref = (float(df.iloc[0]["lat"]), float(df.iloc[0]["lon"]))
        traces[label] = df
        for item in campaign["results"]:
            if item["run"] == run_name and item.get("inject_meta"):
                inject_meta = item["inject_meta"]
    assert ref is not None
    traces = {label: add_enu(df, ref[0], ref[1]) for label, df in traces.items()}
    return traces, ref, inject_meta


def build_e2e_ablation_figure() -> dict:
    traces, ref, inject_meta = load_e2e_traces()
    stats = e2e_campaign_stats()
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.25))
    ax_full, ax_zoom = axes

    for label, df in traces.items():
        style = E2E_STYLE[label]
        ax_full.plot(df["east"], df["north"], label=label, **style)
        ax_zoom.plot(df["east"], df["north"], label=label, **style)

    on_det = traces["Replanner on + detections"]
    active = on_det[on_det["evasion_active"] == 1]
    if len(active):
        ax_zoom.plot(active["east"], active["north"], color=RED, linewidth=3.0, alpha=0.55, label="Active evasion interval")

    if inject_meta:
        obs_e, obs_n = latlon_to_enu(ref[0], ref[1], float(inject_meta["obs_lat"]), float(inject_meta["obs_lon"]))
        for ax in axes:
            ax.scatter([obs_e], [obs_n], marker="x", s=48, color=RED, linewidth=1.35, zorder=9)
            ax.add_patch(
                patches.Circle(
                    (obs_e, obs_n),
                    SAFETY_RADIUS_M,
                    facecolor=(0.70, 0.18, 0.15, 0.10),
                    edgecolor=RED,
                    linewidth=0.8,
                    zorder=2,
                )
            )
        ax_zoom.text(
            obs_e + 4,
            obs_n + 4,
            "injected biker",
            fontsize=7,
            color=INK,
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.8),
            zorder=10,
        )

    start = (float(on_det.iloc[0]["east"]), float(on_det.iloc[0]["north"]))
    finish = (float(on_det.iloc[-1]["east"]), float(on_det.iloc[-1]["north"]))
    ax_full.scatter([start[0]], [start[1]], marker="^", s=50, color=INK, edgecolor="white", linewidth=0.35, zorder=10)
    ax_full.scatter([finish[0]], [finish[1]], marker="s", s=35, color=INK, edgecolor="white", linewidth=0.35, zorder=10)

    ax_full.set_xlim(-45, 850)
    ax_full.set_ylim(-1280, 65)
    ax_zoom.set_xlim(-35, 125)
    ax_zoom.set_ylim(-170, 35)
    for ax in axes:
        ax.set_xlabel("East (m)")
        ax.set_ylabel("North (m)")
        style_axis(ax)
    panel_label(ax_full, "3A", "Full mission overlay")
    panel_label(ax_zoom, "3B", "Early conflict window")

    handles = [
        Line2D([0], [0], **E2E_STYLE["Replanner on + detections"], label="Replanner on + detections"),
        Line2D([0], [0], **E2E_STYLE["Replanner off + detections"], label="Replanner off + detections"),
        Line2D([0], [0], **E2E_STYLE["Replanner on + no detections"], label="Replanner on + no detections"),
        Line2D([0], [0], **E2E_STYLE["Replanner off + no detections"], label="Replanner off + no detections"),
        Line2D([0], [0], color=RED, linewidth=3.0, alpha=0.55, label="Active evasion interval"),
        Line2D([0], [0], marker="x", color=RED, linestyle="none", markersize=7, markeredgewidth=1.35, label="Injected biker"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=7.4, bbox_to_anchor=(0.5, 0.01))
    fig.subplots_adjust(left=0.06, right=0.985, top=0.96, bottom=0.19, wspace=0.18)
    out = OUT / FIG3_NAME
    fig.savefig(out, dpi=320, facecolor="white")
    plt.close(fig)
    latex_files = copy_to_latex_images(out, FIG3_NAME)
    return {
        "file": str(out),
        "latex_file": latex_files[0],
        "latex_files": latex_files,
        "campaign": str(E2E_CAMPAIGN.relative_to(REPO)),
        "runs": {label: str((PIPELINE / "logs" / "e2e" / name).relative_to(REPO)) for label, name in E2E_RUNS.items()},
        "stats": stats,
    }


def find_event(events: list[dict], kind: str, *, frame: int | None = None, ts: float | None = None) -> dict:
    candidates = [event for event in events if event.get("kind") == kind]
    if frame is not None:
        candidates = [event for event in candidates if int(event.get("frame", -1)) == int(frame)]
    if not candidates:
        raise RuntimeError(f"No event found for {kind}")
    if ts is None:
        return candidates[0]
    return min(candidates, key=lambda event: abs(float(event.get("ts", 0.0)) - ts))


def flow_box(ax, x: float, y: float, title: str, value: str, color: str) -> None:
    ax.add_patch(
        patches.FancyBboxPatch(
            (x, y),
            0.18,
            0.18,
            boxstyle="round,pad=0.018,rounding_size=0.018",
            facecolor="white",
            edgecolor=color,
            linewidth=1.35,
            transform=ax.transAxes,
            zorder=3,
        )
    )
    ax.text(x + 0.09, y + 0.112, value, ha="center", va="center", fontsize=13, fontweight="bold", color=color, transform=ax.transAxes, zorder=4)
    ax.text(x + 0.09, y + 0.046, title, ha="center", va="center", fontsize=6.9, color=INK, transform=ax.transAxes, zorder=4)


def draw_detection_plane(parent_ax, frame_evt: dict, proxy_tracks: list[dict]) -> None:
    inset = parent_ax.inset_axes([0.055, 0.075, 0.89, 0.43])
    inset.set_facecolor("#f6f8fa")
    inset.set_xlim(0, 640)
    inset.set_ylim(640, 0)
    inset.set_xticks([0, 320, 640])
    inset.set_yticks([0, 320, 640])
    inset.tick_params(labelsize=5.8, colors="#617080")
    for spine in inset.spines.values():
        spine.set_color("#9ba7b3")
        spine.set_linewidth(0.55)

    for det in frame_evt.get("detections", [])[:45]:
        bbox = det.get("bbox") or {}
        if not bbox:
            continue
        inset.add_patch(
            patches.Rectangle(
                (float(bbox["x1"]), float(bbox["y1"])),
                float(bbox["x2"]) - float(bbox["x1"]),
                float(bbox["y2"]) - float(bbox["y1"]),
                fill=False,
                edgecolor="#98a6b3",
                linewidth=0.45,
                alpha=0.55,
            )
        )

    published_ids = {int(item.get("source_id", item.get("id", -1))) for item in frame_evt.get("outgoing", []) or []}
    proxy_ids = {int(item.get("source_id", item.get("id", -1))) for item in proxy_tracks}
    for item in frame_evt.get("outgoing", []) or []:
        bbox = item.get("bbox") or {}
        if not bbox:
            continue
        item_id = int(item.get("source_id", item.get("id", -1)))
        is_proxy = item_id in proxy_ids
        color = RED if is_proxy else GREEN
        lw = 1.6 if is_proxy else 1.0
        inset.add_patch(
            patches.Rectangle(
                (float(bbox["x1"]), float(bbox["y1"])),
                float(bbox["x2"]) - float(bbox["x1"]),
                float(bbox["y2"]) - float(bbox["y1"]),
                fill=False,
                edgecolor=color,
                linewidth=lw,
                alpha=0.92,
            )
        )
    _ = published_ids
    inset.set_title("Logged pixel boxes: accepted sample, published tracks, proxy subset", fontsize=6.9, color=INK, pad=2)


def draw_perception_flow(ax, frame_evt: dict, route_evt: dict, proxy_tracks: list[dict]) -> None:
    ax.axis("off")
    counts = frame_evt.get("counts") or {}
    labels = [
        ("raw boxes", str(counts.get("raw_boxes", "n/a")), "#56606b"),
        ("projected detections", str(counts.get("accepted_frame_dets", "n/a")), BLUE),
        ("published tracks", str(counts.get("published_outgoing", len(frame_evt.get("outgoing") or []))), GREEN),
        ("planner proxy", str(int(route_evt.get("planner_obs_count", len(proxy_tracks)))), RED),
    ]
    xs = [0.045, 0.29, 0.535, 0.78]
    for idx, (title, value, color) in enumerate(labels):
        flow_box(ax, xs[idx], 0.695, title, value, color)
        if idx < len(labels) - 1:
            ax.annotate(
                "",
                xy=(xs[idx + 1] - 0.025, 0.785),
                xytext=(xs[idx] + 0.205, 0.785),
                xycoords=ax.transAxes,
                textcoords=ax.transAxes,
                arrowprops=dict(arrowstyle="->", lw=1.0, color="#7d8790"),
            )
    rel = float(frame_evt["ts"]) - float(route_evt["ts"])
    ax.text(
        0.055,
        0.605,
        f"Frame {int(frame_evt['frame'])}, t={rel:+.3f} s before route generation",
        transform=ax.transAxes,
        fontsize=7.3,
        color=INK,
    )
    draw_detection_plane(ax, frame_evt, proxy_tracks)
    panel_label(ax, "4A", "Perception reduction")


def occupied_cells(proxy_xy: list[tuple[float, float]]) -> set[tuple[int, int]]:
    safety_cells = int(math.ceil(SAFETY_RADIUS_M / CELL_SIZE_M))
    cells: set[tuple[int, int]] = set()
    for east, north in proxy_xy:
        seed = (int(east / CELL_SIZE_M), int(north / CELL_SIZE_M))
        for dx in range(-safety_cells, safety_cells + 1):
            for dy in range(-safety_cells, safety_cells + 1):
                cells.add((seed[0] + dx, seed[1] + dy))
    return cells


def draw_local_grid(ax, cells: set[tuple[int, int]], xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    for x in np.arange(math.floor(xlim[0] / CELL_SIZE_M) * CELL_SIZE_M, xlim[1] + CELL_SIZE_M, CELL_SIZE_M):
        ax.axvline(x, color="#c4ccd5", linewidth=0.35, alpha=0.45, zorder=0)
    for y in np.arange(math.floor(ylim[0] / CELL_SIZE_M) * CELL_SIZE_M, ylim[1] + CELL_SIZE_M, CELL_SIZE_M):
        ax.axhline(y, color="#c4ccd5", linewidth=0.35, alpha=0.45, zorder=0)
    for cx, cy in cells:
        ax.add_patch(
            patches.Rectangle(
                (cx * CELL_SIZE_M - CELL_SIZE_M / 2.0, cy * CELL_SIZE_M - CELL_SIZE_M / 2.0),
                CELL_SIZE_M,
                CELL_SIZE_M,
                facecolor=(0.70, 0.18, 0.15, 0.15),
                edgecolor=(0.70, 0.18, 0.15, 0.35),
                linewidth=0.35,
                zorder=1,
            )
        )


def min_proxy_distance(df: pd.DataFrame, proxy_xy: list[tuple[float, float]]) -> tuple[np.ndarray, int, int]:
    distances = []
    nearest_idx = []
    for _, row in df.iterrows():
        ds = [math.hypot(float(row["east"]) - px, float(row["north"]) - py) for px, py in proxy_xy]
        distances.append(min(ds))
        nearest_idx.append(int(np.argmin(ds)))
    min_i = int(np.argmin(distances)) if distances else 0
    return np.array(distances, dtype=float), min_i, nearest_idx[min_i] if nearest_idx else 0


def draw_audited_map(ax, traj: pd.DataFrame, active: pd.DataFrame, proxy_xy: list[tuple[float, float]], completion_ts: float) -> dict:
    win = traj[(traj["ts"] >= AUDIT_TRIGGER_TS - 12.0) & (traj["ts"] <= completion_ts + 7.0)].copy()
    xs = list(win["east"]) + [p[0] for p in proxy_xy]
    ys = list(win["north"]) + [p[1] for p in proxy_xy]
    xlim = (min(xs) - 18.0, max(xs) + 18.0)
    ylim = (min(ys) - 18.0, max(ys) + 18.0)
    draw_local_grid(ax, occupied_cells(proxy_xy), xlim, ylim)

    ax.plot(win["east"], win["north"], color=NOMINAL, linewidth=1.2, alpha=0.8, label="Executed trajectory", zorder=3)
    ax.plot(active["east"], active["north"], color=EVASION, linewidth=2.0, label="Active evasion segment", zorder=5)
    ax.scatter([0], [0], marker="^", s=64, color=INK, edgecolor="white", linewidth=0.4, label="Trigger UAS state", zorder=8)

    for idx, (east, north) in enumerate(proxy_xy, start=1):
        ax.add_patch(
            patches.Circle(
                (east, north),
                SAFETY_RADIUS_M,
                facecolor=(0.70, 0.18, 0.15, 0.10),
                edgecolor=RED,
                linewidth=0.85,
                zorder=2,
            )
        )
        ax.scatter([east], [north], marker="x", s=54, color=RED, linewidth=1.35, zorder=7)
        ax.text(east + 2.2, north + 2.2, f"P{idx}", fontsize=7, color=RED, zorder=8)

    distances, min_i, proxy_i = min_proxy_distance(active, proxy_xy)
    min_row = active.iloc[min_i]
    min_proxy = proxy_xy[proxy_i]
    ax.plot(
        [float(min_row["east"]), min_proxy[0]],
        [float(min_row["north"]), min_proxy[1]],
        color=PURPLE,
        linestyle=":",
        linewidth=1.15,
        zorder=6,
    )
    ax.text(
        float(min_row["east"]) + 2.5,
        float(min_row["north"]) + 1.5,
        f"min {float(distances[min_i]):.2f} m",
        fontsize=7,
        color=PURPLE,
        bbox=dict(boxstyle="round,pad=0.13", facecolor="white", edgecolor="none", alpha=0.82),
        zorder=9,
    )
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel("East from trigger (m)")
    ax.set_ylabel("North from trigger (m)")
    style_axis(ax)
    panel_label(ax, "4B", "Local ENU planner evidence")
    ax.legend(loc="lower left", fontsize=6.7, frameon=True, framealpha=0.82)
    return {"min_distance_m": float(distances[min_i]), "min_time_s": float(min_row["ts"] - AUDIT_TRIGGER_TS)}


def draw_time_series(ax, traj: pd.DataFrame, proxy_xy: list[tuple[float, float]], brain_events: list[dict], completion_ts: float) -> dict:
    win = traj[(traj["ts"] >= AUDIT_TRIGGER_TS - 5.0) & (traj["ts"] <= completion_ts + 4.0)].copy()
    distances, min_i, _ = min_proxy_distance(win, proxy_xy)
    rel_t = win["ts"].to_numpy(dtype=float) - AUDIT_TRIGGER_TS
    ax.plot(rel_t, distances, color=EVASION, linewidth=1.8, label="Distance to pre-trigger proxy")

    decision = [
        event
        for event in brain_events
        if event.get("kind") == "decision_snapshot"
        and AUDIT_TRIGGER_TS - 5.0 <= float(event.get("ts", 0.0)) <= completion_ts + 4.0
        and event.get("reaction_distance_eval_m") is not None
    ]
    if decision:
        t_dec = [float(event["ts"]) - AUDIT_TRIGGER_TS for event in decision]
        r_dec = [float(event["reaction_distance_eval_m"]) for event in decision]
        ax.plot(t_dec, r_dec, color=BLUE, linewidth=1.4, label="Dynamic reaction horizon")

    ax.axhline(SAFETY_RADIUS_M, color=RED, linestyle="--", linewidth=1.1, label="Hard safety radius")
    ax.axhline(FAILSAFE_RADIUS_M, color="#6b7280", linestyle=":", linewidth=1.15, label="Failsafe threshold")
    ax.axvline(0.0, color=INK, linestyle="-", linewidth=0.85, alpha=0.65)
    ax.axvspan(0.0, completion_ts - AUDIT_TRIGGER_TS, color=(0.70, 0.41, 0.17, 0.10), label="Active evasion window")
    ax.scatter([float(rel_t[min_i])], [float(distances[min_i])], color=PURPLE, s=24, zorder=8)
    ax.set_xlim(-5.0, completion_ts - AUDIT_TRIGGER_TS + 4.0)
    ax.set_ylim(0, max(70.0, float(np.nanmax(distances)) + 6.0))
    ax.set_xlabel("Time from route generation (s)")
    ax.set_ylabel("Distance (m)")
    style_axis(ax, equal=False)
    panel_label(ax, "4C", "Clearance and reaction horizon")
    ax.legend(loc="upper right", fontsize=6.7, frameon=True, framealpha=0.82)
    return {"min_distance_m": float(distances[min_i]), "min_time_s": float(rel_t[min_i])}


def build_audited_collision_figure() -> dict:
    brain_events = parse_jsonl(AUDIT_RUN / "brain" / "events.jsonl")
    vision_events = parse_jsonl(AUDIT_RUN / "vision" / "events.jsonl")
    route_evt = find_event(brain_events, "evasion_route_generated", ts=AUDIT_TRIGGER_TS)
    frame_evt = find_event(vision_events, "vision_frame", frame=AUDIT_FRAME)
    completion_evt = find_event(brain_events, "evasion_completed", ts=AUDIT_TRIGGER_TS + 34.0)

    traj = valid_traj(pd.read_csv(AUDIT_RUN / "brain" / "trajectory.csv"))
    trigger_row = nearest_row(traj, float(route_evt["ts"]))
    traj = add_enu(traj, float(trigger_row["lat"]), float(trigger_row["lon"]))
    active = traj[(traj["ts"] >= float(route_evt["ts"])) & (traj["ts"] <= float(completion_evt["ts"]))].copy()
    proxy_tracks = sorted(frame_evt.get("outgoing") or [], key=lambda item: float(item.get("distance", 1e9)))[:3]
    proxy_xy = [latlon_to_enu(float(trigger_row["lat"]), float(trigger_row["lon"]), float(item["lat"]), float(item["lon"])) for item in proxy_tracks]

    fig = plt.figure(figsize=(11.0, 7.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[0.92, 1.02], wspace=0.18, hspace=0.22)
    ax_flow = fig.add_subplot(gs[0, 0])
    ax_map = fig.add_subplot(gs[0, 1])
    ax_ts = fig.add_subplot(gs[1, :])

    draw_perception_flow(ax_flow, frame_evt, route_evt, proxy_tracks)
    map_meta = draw_audited_map(ax_map, traj, active, proxy_xy, float(completion_evt["ts"]))
    ts_meta = draw_time_series(ax_ts, traj, proxy_xy, brain_events, float(completion_evt["ts"]))

    handles = [
        Line2D([0], [0], color=EVASION, linewidth=2.0, label="Active evasion"),
        Line2D([0], [0], marker="x", color=RED, linestyle="none", markersize=7, markeredgewidth=1.35, label="Planner-proxy biker"),
        patches.Patch(facecolor=(0.70, 0.18, 0.15, 0.15), edgecolor=(0.70, 0.18, 0.15, 0.35), label="Inflated occupied cells"),
        Line2D([0], [0], color=BLUE, linewidth=1.4, label="Dynamic reaction horizon"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=7.2, bbox_to_anchor=(0.5, 0.012))
    fig.subplots_adjust(left=0.055, right=0.985, top=0.975, bottom=0.095)
    out = OUT / FIG4_NAME
    fig.savefig(out, dpi=320, facecolor="white")
    plt.close(fig)
    latex_files = copy_to_latex_images(out, FIG4_NAME)

    counts = frame_evt.get("counts") or {}
    return {
        "file": str(out),
        "latex_file": latex_files[0],
        "latex_files": latex_files,
        "source_run": str(AUDIT_RUN.relative_to(REPO)),
        "route_event_ts": float(route_evt["ts"]),
        "frame": int(frame_evt["frame"]),
        "counts": counts,
        "planner_obs_count": int(route_evt.get("planner_obs_count", len(proxy_tracks))),
        "proxy_track_ids": [int(item.get("source_id", item.get("id"))) for item in proxy_tracks],
        "map_min_distance_m": map_meta["min_distance_m"],
        "time_series_min_distance_m": ts_meta["min_distance_m"],
    }


def main() -> None:
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "figure_3_e2e_ablation": build_e2e_ablation_figure(),
        "figure_4_audited_collision_evasion": build_audited_collision_figure(),
    }
    (OUT / "validation_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
