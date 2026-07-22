#!/usr/bin/env python3
"""Generate the two English paper figures for the Pipeline B VRIH paper.

Outputs (paper_pipeline_B_telemetry/figures/):
  - fig_trajectory_check.png : reference (.bin) vs Brain-commanded vs Unreal readback
  - fig_real_vs_map.png      : (a) real frame 182 with detection box (crop from the
                               sealed SPPA figure fig_real_video_pass.png)
                               (b) published positions vs PNOA ground truth
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot  # noqa: E402

setup_plot()
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).parent.absolute()          # paper_pipeline_B_telemetry/ (no resolve: it is a junction)
REPO = ROOT.parent
OUT = REPO / "tools/real_flight_replay/out"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
R_EARTH = 6378137.0


def nearest_error(point, path):
    px, py = point
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 < 1e-9 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
        ex, ey = x1 + t * dx, y1 + t * dy
        best = min(best, math.hypot(px - ex, py - ey))
    return best


def fig_trajectory():
    traj = list(csv.DictReader((OUT / "trajectory_m20_1rr.csv").open(encoding="utf-8")))
    lat0, lon0 = float(traj[0]["lat"]), float(traj[0]["lon"])
    ref = [(math.radians(float(r["lat"]) - lat0) * R_EARTH,
            math.radians(float(r["lon"]) - lon0) * R_EARTH * math.cos(math.radians(lat0)))
           for r in traj]
    cmds, reads = [], []
    for line in (OUT / "flight_path_log.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["type"] == "cmd":
            cmds.append((rec["north"], rec["east"]))
        else:
            reads.append((rec["x"] / 100.0, rec["y"] / 100.0))
    err_cmd = sorted(nearest_error(p, ref) for p in cmds)
    err_read = sorted(nearest_error(p, ref) for p in reads)
    print(f"cmd vs ref: mean={sum(err_cmd)/len(err_cmd):.2f} max={err_cmd[-1]:.2f}")
    print(f"read vs ref: mean={sum(err_read)/len(err_read):.2f} max={err_read[-1]:.2f}")

    fig, ax = plt.subplots(figsize=(7.0, 6.4), dpi=160)
    ax.plot([p[1] for p in ref], [p[0] for p in ref], "-", color="#888888", lw=1.6,
            label="reference (ArduPilot .bin)")
    ax.plot([p[1] for p in cmds], [p[0] for p in cmds], "-", color="#1f4e79", lw=1.0,
            alpha=0.7, label="commanded (Brain world_m)")
    ax.plot([p[1] for p in reads], [p[0] for p in reads], ".", color="#b02a20", ms=3.5,
            label="Unreal marker readback")
    ax.plot(ref[0][1], ref[0][0], "^", color="#1a7a1a", ms=9, label="start (home)")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.legend(loc="best", fontsize=8)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_trajectory_check.png")
    plt.close(fig)
    print("written:", FIGS / "fig_trajectory_check.png")


def fig_real_vs_map():
    # --- panel (a): crop from sealed SPPA figure (frame 182 with detection box)
    src = Image.open(REPO / "paper_semantic_proxy_3d/figures/fig_real_video_pass.png")
    w, h = src.size  # 3120x1830
    # panel (a) occupies upper-left quadrant; tune crop on the original pixels
    crop = src.crop((int(0.078 * w), int(0.055 * h), int(0.42 * w), int(0.46 * h)))

    # --- panel (b): published positions vs PNOA GT
    poles = []
    for line in (OUT / "tower_ground_truth.csv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("id,"):
            continue
        p = line.split(",")
        poles.append({"id": p[0].strip(), "lat": float(p[1]), "lon": float(p[2])})
    rows = list(csv.DictReader((OUT / "validation_errors.csv").open(encoding="utf-8")))

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(10.5, 4.6), dpi=160,
                                   gridspec_kw={"width_ratios": [1.25, 1.0]})
    axa.imshow(crop)
    axa.axis("off")
    axa.set_title("(a) recorded frame 182 with detector output", fontsize=10)

    for p in poles:
        axb.plot(p["lon"], p["lat"], "k^", ms=10, zorder=3)
        axb.annotate(p["id"], (p["lon"], p["lat"]), textcoords="offset points",
                     xytext=(6, 6), fontsize=9)
    axb.scatter([float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows],
                s=6, c="#b02a20", alpha=0.5, label="published position", zorder=2)
    axb.set_xlabel("longitude")
    axb.set_ylabel("latitude")
    axb.set_title("(b) published positions vs PNOA ground truth", fontsize=10)
    axb.legend(loc="best", fontsize=8)
    axb.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_real_vs_map.png")
    plt.close(fig)
    print("written:", FIGS / "fig_real_vs_map.png")


if __name__ == "__main__":
    fig_trajectory()
    fig_real_vs_map()
