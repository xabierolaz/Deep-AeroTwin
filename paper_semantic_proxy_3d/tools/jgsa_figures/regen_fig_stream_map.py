# -*- coding: utf-8 -*-
"""Regenerate figures/fig_stream_map.png ONLY (figure 2 of fig_worked_example.py).

Audit fix 2026-07-20: the caption states "only towers t0--t1 fall inside the
observed corridor". Data check: t1's nearest raw detection is 154.2 m (< the
250 m near-anchor criterion used by this figure), so t1 IS inside the corridor
and was already selected for plotting; in the previous render it was hidden
behind the lower-right legend. The only change versus the original block is
the legend location (lower right -> lower left) so t1 is plotted AND visible.

All inputs are measured artifacts (stream events + spawn GT). No synthetic
embellishment.
"""
import json, math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d")
STREAM = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260620_084932\vision")
ORIGIN = {"lat": 42.229695, "lon": -1.235085}
R_EARTH = 6371000.0
CLS_COLOR = {"tower": "#d62728", "cow": "#8c564b", "biker": "#1f77b4"}

def to_local(lat, lon):
    x = math.radians(lon - ORIGIN["lon"]) * math.cos(math.radians(ORIGIN["lat"])) * R_EARTH
    y = math.radians(lat - ORIGIN["lat"]) * R_EARTH
    return x, y

events = [json.loads(l) for l in (STREAM / "events.jsonl").open(encoding="utf-8")]
spawn = json.load(open(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\ejea_spawn_state_latest.json"))
anchors = []
for a in spawn["actors"]:
    llh = a.get("globe_anchor_llh") or {}
    lab = str(a.get("label") or "")
    if llh.get("lat"):
        cls = "tower" if lab.startswith("t") else "cow"
        x, y = to_local(llh["lat"], llh["lon"])
        anchors.append((lab, cls, x, y))

# ---------------------------------------------------------------- stream map
fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=300)
path = [(to_local(e["telemetry"]["lat"], e["telemetry"]["lon"])) for e in events
        if e["kind"] == "vision_frame" and e.get("telemetry", {}).get("lat")]
ax.plot([p[0] for p in path], [p[1] for p in path], color="0.45", lw=0.7, alpha=0.8, zorder=1,
        label="UAV trajectory (MAVLink)")
seen = {}
for e in events:
    if e["kind"] != "vision_frame":
        continue
    for d in e.get("detections", []):
        if d.get("lat"):
            seen.setdefault(d["type"], []).append(to_local(d["lat"], d["lon"]))
for cls, pts in seen.items():
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=3, alpha=0.35,
               color=CLS_COLOR.get(cls, "k"), label=f"detections: {cls} (n={len(pts)})", zorder=2)
# crop to the observed working area: keep anchors within 250 m of a detection
allx = [p[0] for p in path] + [p[0] for pts in seen.values() for p in pts]
ally = [p[1] for p in path] + [p[1] for pts in seen.values() for p in pts]
det_pts = [p for pts in seen.values() for p in pts]
near = [a for a in anchors
        if any(math.hypot(a[2] - px, a[3] - py) <= 250 for px, py in det_pts)]
print("near anchors:", [(a[0], round(min(math.hypot(a[2]-px, a[3]-py) for px, py in det_pts), 1))
                        for a in near])
for lab, cls, x, y in near:
    mk = "^" if cls == "tower" else "s"
    ax.plot(x, y, mk, ms=9 if cls == "tower" else 6, mec="black", mfc=CLS_COLOR[cls], mew=0.8, zorder=3)
    if lab.startswith("t"):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(6, 4), fontsize=7, weight="bold")
ax.plot([], [], "k^", ms=7, label="GT tower anchor")
ax.plot([], [], "ks", ms=6, label="GT cow anchor")
allx += [a[2] for a in near]; ally += [a[3] for a in near]
x0, x1 = min(allx), max(allx); y0, y1 = min(ally), max(ally)
mx_, my_ = 0.15 * (x1 - x0 + 1), 0.15 * (y1 - y0 + 1)
ax.set_xlim(x0 - mx_, x1 + mx_); ax.set_ylim(y0 - my_, y1 + my_)
ax.set_xlabel("E of twin origin (m)"); ax.set_ylabel("N of twin origin (m)")
ax.set_title("Recorded flight over the georeferenced Ejea twin (2026-06-20)")
ax.tick_params(labelsize=7); ax.legend(fontsize=6.5, loc="lower left", framealpha=0.95)
ax.set_aspect("equal"); ax.grid(alpha=0.3, lw=0.4)
ax.annotate("N", xy=(0.97, 0.94), xycoords="axes fraction", ha="center", fontsize=10, weight="bold")
ax.annotate("", xy=(0.97, 0.93), xytext=(0.97, 0.86), xycoords="axes fraction",
            arrowprops=dict(arrowstyle="->", lw=1.2))
fig.savefig(ROOT / "figures/fig_stream_map.png", bbox_inches="tight")
plt.close(fig)
print("SAVED fig_stream_map.png", "| path pts:", len(path), "| anchors:", len(anchors),
      "| dets:", {k: len(v) for k, v in seen.items()})
