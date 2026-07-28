#!/usr/bin/env python3
"""
VIZ RECORDER
------------
Consume /api/ui/data and render debug/evasion traces for inspection.
"""

import math
import os
import shutil
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle
import requests

from constants import (
    BRAIN_HTTP_HOST,
    EARTH_RADIUS_M,
    MAVLINK_HUB_HTTP_PORT,
    VIZ_AXIS_FONT_SIZE,
    VIZ_CELL_BORDER_HALF_M,
    VIZ_CELL_BORDER_SIZE,
    VIZ_DPI,
    VIZ_DRONE_OUTLINE_MARKER_SIZE,
    VIZ_DRONE_MARKER_SIZE,
    VIZ_DRONE_ORIENTATION_SPAN_RAD,
    VIZ_EMPTY_SLEEP_S,
    VIZ_FIGSIZE_INCH,
    VIZ_EVASION_LINE_WIDTH,
    VIZ_FETCH_TIMEOUT_S,
    VIZ_FLIGHT_LINE_WIDTH,
    VIZ_FRAME_STEP_LOG_EVERY,
    VIZ_GRID_CELL_HALF_M,
    VIZ_GRID_LINE_WIDTH,
    VIZ_GRID_RADIUS_M,
    VIZ_GRID_SIZE_M,
    VIZ_HISTORY_LIMIT,
    VIZ_HOME_LABEL_FONT_SIZE,
    VIZ_LEGEND_FONT_SIZE,
    VIZ_OUTPUT_DIR,
    VIZ_MISSION_LINE_WIDTH,
    VIZ_PAD_M,
    VIZ_POLL_TIMEOUT_S,
    VIZ_TICK_FONT_SIZE,
    VIZ_WAYPOINT_LABEL_FONT_SIZE,
    VIZ_WAYPOINT_LABEL_OFFSET_M,
    VIZ_WAYPOINT_MARKER_SIZE,
    VIZ_STATUS_FONT_SIZE,
)

API_URL = f"http://{BRAIN_HTTP_HOST}:{MAVLINK_HUB_HTTP_PORT}/api/ui/data"
OUTPUT_DIR = VIZ_OUTPUT_DIR


def latlon_to_meters(lat: float, lon: float, home_lat: float, home_lon: float) -> tuple[float, float]:
    dlat = math.radians(lat - home_lat)
    dlon = math.radians(lon - home_lon)
    R = float(EARTH_RADIUS_M)
    return dlon * R * math.cos(math.radians(home_lat)), dlat * R


def _fetch_payload() -> dict | None:
    try:
        resp = requests.get(API_URL, timeout=float(VIZ_FETCH_TIMEOUT_S))
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict) or not data.get("home"):
            return None
        return data
    except Exception:
        return None


def main() -> None:
    if os.path.exists(OUTPUT_DIR):
        try:
            shutil.rmtree(OUTPUT_DIR)
        except Exception:
            pass
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(VIZ_FIGSIZE_INCH, VIZ_FIGSIZE_INCH))

    frame = 0
    hx, hy = [], []
    print("[VIZ] Iniciando motor grafico...")

    while True:
        st = time.time()
        data = _fetch_payload()
        if data is None:
            time.sleep(VIZ_EMPTY_SLEEP_S)
            continue

        h = data["home"]
        t = data["telemetry"]
        obs = data["obstacles"]
        ev = data["evasion"]
        wps = data["waypoints"]

        dx, dy = latlon_to_meters(t["lat"], t["lon"], h["lat"], h["lon"])
        hx.append(dx)
        hy.append(dy)
        if len(hx) > VIZ_HISTORY_LIMIT:
            hx.pop(0)
            hy.pop(0)

        ax.clear()

        # 1) Mission route
        mx, my = [0], [0]
        ax.text(
            0,
            0,
            "HOME",
            fontsize=int(VIZ_HOME_LABEL_FONT_SIZE),
            fontweight="bold",
            color="#4C72B0",
        )
        for i, wp in enumerate(wps):
            wx, wy = latlon_to_meters(wp["lat"], wp["lon"], h["lat"], h["lon"])
            mx.append(wx)
            my.append(wy)
            if i > 0:
                ax.text(
                    wx + VIZ_WAYPOINT_LABEL_OFFSET_M,
                    wy + VIZ_WAYPOINT_LABEL_OFFSET_M,
                    f"WP{i}",
                    fontsize=int(VIZ_WAYPOINT_LABEL_FONT_SIZE),
                    color="#4C72B0",
                )
        ax.plot(mx, my, "--", color="#4C72B0", linewidth=float(VIZ_MISSION_LINE_WIDTH), label="Global Mission", zorder=1)
        ax.scatter(mx, my, marker="", color="#4C72B0", s=float(VIZ_WAYPOINT_MARKER_SIZE), zorder=2)

        # 2) Obstacles
        for o in obs:
            ox, oy = latlon_to_meters(o["lat"], o["lon"], h["lat"], h["lon"])
            ax.add_patch(Circle((ox, oy), data["params"]["safety_dist"], color="#C44E52", alpha=0.3))
            ax.plot(ox, oy, "x", color="#C44E52")

        if ev["active"] and ev["path"] and ev.get("grid_origin"):
            # Grid overlay for A* debug view.
            gox, goy = latlon_to_meters(ev["grid_origin"]["lat"], ev["grid_origin"]["lon"], h["lat"], h["lon"])
            half = float(VIZ_GRID_SIZE_M)
            radius = float(VIZ_GRID_RADIUS_M)
            grid_begin_x = int(gox) - int(radius)
            grid_end_x = int(gox) + int(radius)
            grid_begin_y = int(goy) - int(radius)
            grid_end_y = int(goy) + int(radius)

            for gx in range(grid_begin_x, grid_end_x, int(half)):
                offset = (gx - gox) % half
                line_x = gx - offset
                ax.plot(
                    [line_x, line_x],
                    [goy - radius, goy + radius],
                    "-",
                    color="#DDDDDD",
                    linewidth=float(VIZ_GRID_LINE_WIDTH),
                    zorder=0,
                )

            for gy in range(grid_begin_y, grid_end_y, int(half)):
                offset = (gy - goy) % half
                line_y = gy - offset
                ax.plot(
                    [gox - radius, gox + radius],
                    [line_y, line_y],
                    "-",
                    color="#DDDDDD",
                    linewidth=float(VIZ_GRID_LINE_WIDTH),
                    zorder=0,
                )

            ex = [dx] + [latlon_to_meters(p["lat"], p["lon"], h["lat"], h["lon"])[0] for p in ev["path"]]
            ey = [dy] + [latlon_to_meters(p["lat"], p["lon"], h["lat"], h["lon"])[1] for p in ev["path"]]
            ax.plot(
                ex,
                ey,
                "-",
                color="#E67E22",
                linewidth=float(VIZ_EVASION_LINE_WIDTH),
                label="Evasion Path",
                zorder=5,
            )

            for i in range(len(ex)):
                rect = Rectangle(
                    (ex[i] - VIZ_GRID_CELL_HALF_M, ey[i] - VIZ_GRID_CELL_HALF_M),
                    width=VIZ_CELL_BORDER_SIZE,
                    height=VIZ_CELL_BORDER_SIZE,
                    color="#E67E22",
                    alpha=0.3,
                    zorder=4,
                )
                ax.add_patch(rect)

        # 3) Real flight history
        ax.plot(
            hx,
            hy,
            "-",
            color="#555555",
            linewidth=float(VIZ_FLIGHT_LINE_WIDTH),
            alpha=0.7,
            label="Flown Path",
            zorder=3,
        )

        # 4) Drone icon
        angle_rad = math.radians(90 - t["heading"])
        p1 = (dx + VIZ_DRONE_MARKER_SIZE * math.cos(angle_rad), dy + VIZ_DRONE_MARKER_SIZE * math.sin(angle_rad))
        p2 = (
            dx + VIZ_DRONE_MARKER_SIZE * 0.7 * math.cos(angle_rad + VIZ_DRONE_ORIENTATION_SPAN_RAD),
            dy + VIZ_DRONE_MARKER_SIZE * 0.7 * math.sin(angle_rad + VIZ_DRONE_ORIENTATION_SPAN_RAD),
        )
        p3 = (
            dx + VIZ_DRONE_MARKER_SIZE * 0.7 * math.cos(angle_rad - VIZ_DRONE_ORIENTATION_SPAN_RAD),
            dy + VIZ_DRONE_MARKER_SIZE * 0.7 * math.sin(angle_rad - VIZ_DRONE_ORIENTATION_SPAN_RAD),
        )
        ax.fill([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color="black", zorder=10, label="Drone")

        # 5) Status + legend
        status = "NAVIGATING"
        if ev["active"] and ev["path"]:
            status = "EVADING (A*)"
        elif len(obs) > 0:
            status = "OBSTACLE DETECTED"
        info = (
            f"STATUS: {status}\n"
            f"GPS: {t['lat']:.5f}, {t['lon']:.5f}\n"
            f"ALT: {t['alt']:.1f}m ^| HDG: {t['heading']}deg\n"
            f"OBS: {len(obs)}"
        )
        props = dict(boxstyle="round", facecolor="white", alpha=0.9, edgecolor="#333333")
        ax.text(
            0.5,
            0.03,
            info,
            transform=ax.transAxes,
            fontsize=VIZ_STATUS_FONT_SIZE,
            horizontalalignment="center",
            verticalalignment="bottom",
            bbox=props,
            fontfamily="monospace",
        )

        legend_elements = [
            Line2D([0], [0], color="#4C72B0", lw=float(VIZ_MISSION_LINE_WIDTH), ls="--", label="Global Mission"),
            Line2D([0], [0], color="#555555", lw=float(VIZ_FLIGHT_LINE_WIDTH), label="Flown Path"),
            Line2D([0], [0], color="#E67E22", lw=float(VIZ_EVASION_LINE_WIDTH), label="Evasion Path"),
            Line2D(
                [0],
                [0],
                marker="",
                color="w",
                markerfacecolor="black",
                markersize=float(VIZ_DRONE_OUTLINE_MARKER_SIZE) / 8.0,
                label="Drone",
            ),
            Line2D([0], [0], marker="x", color="#C44E52", label="Obstacles", linestyle="None"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=VIZ_LEGEND_FONT_SIZE, framealpha=0.9)

        ax.tick_params(axis="both", which="major", labelsize=float(VIZ_TICK_FONT_SIZE))
        ax.set_xlabel("East (m)", fontsize=VIZ_AXIS_FONT_SIZE, fontweight="bold")
        ax.set_ylabel("North (m)", fontsize=VIZ_AXIS_FONT_SIZE, fontweight="bold")

        if len(mx) > 1:
            min_x, max_x = min(mx), max(mx)
            min_y, max_y = min(my), max(my)
            cx = (min_x + max_x) * 0.5
            cy = (min_y + max_y) * 0.5
            half_span = max(max_x - min_x, max_y - min_y) * 0.5 + VIZ_PAD_M
            if not math.isfinite(half_span) or half_span <= 0:
                half_span = max(1.0, float(VIZ_PAD_M))
            ax.set_xlim(cx - half_span, cx + half_span)
            ax.set_ylim(cy - half_span, cy + half_span)
            ax.set_aspect("auto")
            try:
                ax.set_box_aspect(1)
            except Exception:
                pass

        ax.grid(True, linestyle=":", alpha=0.6)
        fig.savefig(os.path.join(OUTPUT_DIR, f"frame_{frame:04d}.png"), dpi=VIZ_DPI)
        if frame % int(VIZ_FRAME_STEP_LOG_EVERY) == 0:
            print(f"[REC] Guardado Frame {frame}")

        frame += 1
        time.sleep(max(0.0, VIZ_POLL_TIMEOUT_S - (time.time() - st)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
