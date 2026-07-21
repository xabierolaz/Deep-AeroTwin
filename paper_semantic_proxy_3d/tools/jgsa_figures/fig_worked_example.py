# -*- coding: utf-8 -*-
"""JGSA figures: worked end-to-end example + georeferenced stream map.
Outputs: figures/fig_worked_example.png, figures/fig_stream_map.png
All inputs are measured artifacts (stream events, results.jsonl, spawn GT,
graphs.json proxy render, E11 twin frame). No synthetic embellishment.

2026-07-21 rework (figure readability pass):
- Worked-example frame changed 916 -> 1584 (same recorded stream): the old
  frame had the tower at the extreme left border (bbox x1=4, 93 px tall);
  frame 1584 keeps the tower fully inside the frame (bbox 29x84 px at
  x 83..112), on loaded Cesium terrain (mean-abs-gradient 9.44 vs 6.83),
  GT-matched to anchor t0 (token_correct=true, loc err 17.8 m, obs
  18.03x4.17 m; source benchmarks/real_stream_wave/results.jsonl
  case f01584_d0, method sppa_mvfit).
- Layout changed from one cramped 5-panel row to a 2-row grid with larger
  fonts; the real tower crop (b) sits directly above the compiled proxy
  render (d) so the silhouette-to-parts mapping reads at a glance.
- Panel (d) now uses the role-colored Blender render of the sealed
  lattice_tower graph (tools/jgsa_figures/assets/render_fam_lattice_tower.png)
  instead of the pale 640x640 preview.
"""
import json, math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, Polygon
from PIL import Image

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d")
STREAM = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260620_084932\vision")
ORIGIN = {"lat": 42.229695, "lon": -1.235085}
R_EARTH = 6371000.0
CLS_COLOR = {"tower": "#d62728", "cow": "#8c564b", "biker": "#1f77b4"}
ROLE_COLOR = {"spine / mast (primary)": "#0072B2",
              "legs (4)": "#009E73",
              "platforms (3)": "#CC79A7"}

def to_local(lat, lon):
    x = math.radians(lon - ORIGIN["lon"]) * math.cos(math.radians(ORIGIN["lat"])) * R_EARTH
    y = math.radians(lat - ORIGIN["lat"]) * R_EARTH
    return x, y

events = [json.loads(l) for l in (STREAM / "events.jsonl").open(encoding="utf-8")]
frames = {e["frame"]: e for e in events if e["kind"] == "vision_frame"}
spawn = json.load(open(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\ejea_spawn_state_latest.json"))
anchors = []
for a in spawn["actors"]:
    llh = a.get("globe_anchor_llh") or {}
    lab = str(a.get("label") or "")
    if llh.get("lat"):
        cls = "tower" if lab.startswith("t") else "cow"
        x, y = to_local(llh["lat"], llh["lon"])
        anchors.append((lab, cls, x, y))

# ---------------------------------------------------------------- figure 1: worked example
FRAME_ID = 1584
ev = frames[FRAME_ID]
det_tower = [d for d in ev["detections"] if d["type"] == "tower"][0]
row = [json.loads(l) for l in (ROOT / "benchmarks/real_stream_wave/results.jsonl").open(encoding="utf-8")
       if json.loads(l)["case_id"] == f"f{FRAME_ID:05d}_d0" and json.loads(l)["method"] == "sppa_mvfit"][0]
t0 = [a for a in anchors if a[0] == "t0"][0]

img = Image.open(STREAM / "frames" / f"yolo_{FRAME_ID:06d}.jpg")
W, H = img.size

fig = plt.figure(figsize=(13.2, 7.2), dpi=300)
gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 1.0],
                      width_ratios=[1.25, 0.85, 1.1], hspace=0.16, wspace=0.10)

# (a) frame crop around the tower + boxes (spans two columns; the full frame
# leaves the tower at 29 px of 640, unreadable at print size -- the crop keeps
# the tower, its field context and the nearby cow evidence)
CROP_A = (0, 180, 400, 460)  # x0, y0, x1, y1 in source frame pixels
img_a = img.crop(CROP_A)
ax = fig.add_subplot(gs[0, 0:2]); ax.imshow(img_a)
for d in ev["detections"]:
    b = d["bbox"]
    ax.add_patch(Rectangle((b["x1"]-CROP_A[0], b["y1"]-CROP_A[1]), b["x2"]-b["x1"], b["y2"]-b["y1"],
                           fill=False, ec=CLS_COLOR[d["type"]], lw=2.0))
    ax.text(b["x1"]-CROP_A[0], b["y1"]-CROP_A[1]-6, f'{d["type"]} {d["confidence"]:.2f}', color=CLS_COLOR[d["type"]],
            fontsize=9, weight="bold",
            bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1.2))
ax.set_title(f"(a) stream frame {FRAME_ID}, left-center crop + detector", fontsize=10); ax.axis("off")

# (b) tower crop
b = det_tower["bbox"]
mx, my = 34, 40
crop = img.crop((max(b["x1"]-mx, 0), max(b["y1"]-my, 0), min(b["x2"]+mx, W), min(b["y2"]+my, H)))
ax = fig.add_subplot(gs[0, 2]); ax.imshow(crop.resize((crop.width*4, crop.height*4), Image.LANCZOS))
ax.add_patch(Rectangle(( (b["x1"]-max(b["x1"]-mx,0))*4, (b["y1"]-max(b["y1"]-my,0))*4),
                       (b["x2"]-b["x1"])*4, (b["y2"]-b["y1"])*4, fill=False, ec="#d62728", lw=1.6))
ax.set_title(f'(b) detection evidence: {b["x2"]-b["x1"]}x{b["y2"]-b["y1"]}-px bbox', fontsize=10)
ax.axis("off")

# (c) plan view
ax = fig.add_subplot(gs[1, 0])
dx, dy = ev["telemetry"]["drone_x_m"], ev["telemetry"]["drone_y_m"]
px, py = det_tower["x_m"], det_tower["y_m"]
ax.plot(dx, dy, "k^", ms=9, label="UAV (telemetry)")
yaw = math.radians(ev["telemetry"]["yaw"])
ax.annotate("", xy=(dx+9*math.sin(yaw), dy+9*math.cos(yaw)), xytext=(dx, dy),
            arrowprops=dict(arrowstyle="->", color="k", lw=1.4))
ax.plot(px, py, "x", color="#d62728", ms=10, mew=2.4, label="observed footprint")
ang = math.atan2(py-dy, px-dx)
L, Wd = row["obs_length_m"], row["obs_width_m"]
ca, sa = math.cos(ang), math.sin(ang)
corn = [(px + ca*s - sa*w, py + sa*s + ca*w) for s, w in
        (( L/2, -Wd/2), ( L/2, Wd/2), (-L/2, Wd/2), (-L/2, -Wd/2))]
ax.add_patch(Polygon(corn, closed=True, fill=False, ec="#d62728", ls="--", lw=1.6))
ax.add_patch(Rectangle((t0[2]-2.5, t0[3]-2.5), 5, 5, fill=False, ec="green", lw=2.0, label="GT anchor (t0, 5x5 m)"))
ax.plot([px, t0[2]], [py, t0[3]], ":", color="gray", lw=1.4)
ax.text((px+t0[2])/2+2, (py+t0[3])/2, f'{row["loc_err_horiz_m"]:.1f} m', fontsize=9, color="gray")
ax.set_title("(c) geo-projected footprint vs GT", fontsize=10)
ax.set_xlabel("E (m)", fontsize=9); ax.set_ylabel("N (m)", fontsize=9)
ax.tick_params(labelsize=8)
ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), framealpha=0.95)
ax.set_aspect("equal"); ax.grid(alpha=0.25, lw=0.5)
# keep every element inside the view with a margin (legend must not cover t0)
xs_all = [dx, px, t0[2]]; ys_all = [dy, py, t0[3]]
x0c, x1c = min(xs_all), max(xs_all); y0c, y1c = min(ys_all), max(ys_all)
ax.set_xlim(x0c - 6, x1c + 6); ax.set_ylim(y0c - 6, y1c + 6)

# (d) compiled proxy (role-colored render of the sealed lattice_tower graph),
# placed directly below the real tower crop (b) for the silhouette comparison
ax = fig.add_subplot(gs[1, 2])
ax.imshow(Image.open(ROOT / "tools/jgsa_figures/assets/render_fam_lattice_tower.png"))
ax.set_title("(d) compiled SPPA proxy (8 parts, roles)", fontsize=10); ax.axis("off")
handles = [mpatches.Patch(color=c, label=l) for l, c in ROLE_COLOR.items()]
ax.legend(handles=handles, fontsize=8, loc="lower right", framealpha=0.95)

# (e) twin layer
ax = fig.add_subplot(gs[1, 1])
ax.imshow(Image.open(ROOT / "benchmarks/oblique_twin_wave/frames/t0_oblique30_az060.png"))
ax.set_title("(e) twin display layer (Unreal/Cesium)", fontsize=10); ax.axis("off")

fig.savefig(ROOT / "figures/fig_worked_example.png", bbox_inches="tight")
plt.close(fig)
print("SAVED fig_worked_example.png")

# ---------------------------------------------------------------- figure 2: stream map
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
ax.tick_params(labelsize=7); ax.legend(fontsize=6.5, loc="lower right", framealpha=0.95)
ax.set_aspect("equal"); ax.grid(alpha=0.3, lw=0.4)
ax.annotate("N", xy=(0.97, 0.94), xycoords="axes fraction", ha="center", fontsize=10, weight="bold")
ax.annotate("", xy=(0.97, 0.93), xytext=(0.97, 0.86), xycoords="axes fraction",
            arrowprops=dict(arrowstyle="->", lw=1.2))
fig.savefig(ROOT / "figures/fig_stream_map.png", bbox_inches="tight")
plt.close(fig)
print("SAVED fig_stream_map.png", "| path pts:", len(path), "| anchors:", len(anchors),
      "| dets:", {k: len(v) for k, v in seen.items()})
