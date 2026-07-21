# -*- coding: utf-8 -*-
"""JGSA figures: real flight-photo probes end-to-end (2026-07-21).

Inputs (all measured/generated artifacts, no synthetic embellishment):
- rea_flight_data/real_photos/{tower,tractor}.png  (user-supplied real flight photos)
- experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu/
  (YOLOE-26s detector evidence: annotated image, native mask, confidence)
- experiments/sppa_geometric_projection/20260721_real_flight_photos_replay/
  real_image_assumed_flight_replay.json (declared assumed-flight replay:
  mask footprint, constraint-fused metric dims, gate decisions)

Builds the runtime proxy meshes with the frozen parametric builder
(XYT-xabi-yolo-telemetry/xyt_generate_3d.py) at the replay's gated dims,
renders them with their own MTL role colors (painter's algorithm, no GL),
and composes figures/fig_real_flight_probes.png (2 rows x 3 cols).

Run: python render_real_flight_proxies.py
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PAPER = REPO / "paper_semantic_proxy_3d"
REPLAY_JSON = REPO / "experiments/sppa_geometric_projection/20260721_real_flight_photos_replay/real_image_assumed_flight_replay.json"
DET_DIR = REPO / "experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu"
XYT = REPO / "XYT-xabi-yolo-telemetry/xyt_generate_3d.py"
ASSETS = PAPER / "figures/assets/real_flight"
OUT_FIG = PAPER / "figures/fig_real_flight_probes.png"

CASES = ["tower", "tractor"]
DET_IMG = {"tower": DET_DIR / "tower_yoloe26s_open_vocab.png",
           "tractor": DET_DIR / "tractor_yoloe26s_open_vocab.png"}
ROW_TITLE = {"tower": "YOLOE 'electric pylon' 0.49 -> power_tower",
             "tractor": "YOLOE 'two-wheeled vehicle' 0.48 -> generic_vehicle"}
TRIPOSR_IMG = {"tower": ASSETS / "triposr_tower.png",
               "tractor": ASSETS / "triposr_tractor.png"}
TRIPOSR_NOTE = {"tower": "TripoSR: 26,836 tris, 0.49 s, 1,868 MB -> amorphous blob",
                "tractor": "TripoSR: 39,700 tris, 0.09 s, 1,870 MB -> amorphous blob"}


# ---------------------------------------------------------------- mesh build
def load_xyt():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d_for_fig", XYT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_meshes(rows: dict) -> None:
    mod = load_xyt()
    ASSETS.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        dims = rows[case]["sppa_metric_dims_m"]
        mesh = mod.Mesh()
        mod.build_label_observed(mesh, case, dims_m={
            "length": dims["length"], "width": dims["width"], "height": dims["height"]})
        mod.write_obj(mesh, ASSETS / f"{case}.obj", f"{case}.mtl")
        mod.write_mtl(ASSETS / f"{case}.mtl")
        tris = sum(max(0, len(idx) - 2) for idx, _ in mesh.faces)
        print(f"built {case}: {len(mesh.faces)} faces, {tris} tris, dims={dims}")


# ---------------------------------------------------------------- OBJ/MTL parse + software render
def parse_obj(path: Path):
    verts, faces, fmats = [], [], []
    current = "default"
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("v "):
            verts.append([float(v) for v in line.split()[1:4]])
        elif line.startswith("usemtl "):
            current = line.split(None, 1)[1].strip()
        elif line.startswith("f "):
            idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
            for k in range(1, len(idx) - 1):
                faces.append([idx[0], idx[k], idx[k + 1]])
                fmats.append(current)
    return np.asarray(verts), faces, fmats


def parse_mtl(path: Path):
    kd = {}
    name = None
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("newmtl "):
            name = line.split(None, 1)[1].strip()
        elif line.startswith("Kd ") and name:
            kd[name] = tuple(float(v) for v in line.split()[1:4])
    return kd


def render_proxy(case: str) -> Path:
    verts, faces, fmats = parse_obj(ASSETS / f"{case}.obj")
    kd = parse_mtl(ASSETS / f"{case}.mtl")
    base = np.asarray([kd.get(m, (0.62, 0.66, 0.70)) for m in fmats])
    # thin dark structures (e.g. tower lattice metal) read as black at print
    # size; lift the palette so the members stay visible
    lum = base @ np.array([0.299, 0.587, 0.114])
    if float(lum.mean()) < 0.52:
        base = np.clip(base * (0.55 / max(float(lum.mean()), 1e-3)), 0, 1)
    tri = verts[np.asarray(faces)]
    center = tri.reshape(-1, 3).mean(axis=0)
    tri = tri - center
    # camera: azimuth about the world z axis, then a look-down of el_deg from
    # the horizontal plane. Rx must be (el_deg - 90) so the world z axis lands
    # mostly on the image y axis (upright objects), not on the depth axis.
    az_deg, el_deg = -25.0, 14.0
    az = math.radians(az_deg)
    el = math.radians(el_deg - 90.0)
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(el), -math.sin(el)], [0, math.sin(el), math.cos(el)]])
    R = Rx @ Rz
    rot = tri @ R.T
    depth = rot[:, :, 2].mean(axis=1)
    order = np.argsort(depth)
    normals = np.cross(rot[:, 1] - rot[:, 0], rot[:, 2] - rot[:, 0])
    nlen = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(nlen, 1e-12)
    light = np.array([0.35, -0.45, 0.82])
    light = light / np.linalg.norm(light)
    shade = 0.68 + 0.32 * np.abs(normals @ light)
    polys = rot[order, :, :2]
    cols = np.clip(base[order] * shade[order][:, None], 0, 1)
    fig, ax = plt.subplots(figsize=(3.2, 3.2), dpi=300)
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="#22303a",
                                     linewidths=0.25))
    xy = polys.reshape(-1, 2)
    span = max(np.ptp(xy[:, 0]), np.ptp(xy[:, 1])) * 0.62
    cxy = xy.mean(axis=0)
    ax.set_xlim(cxy[0] - span, cxy[0] + span)
    ax.set_ylim(cxy[1] - span, cxy[1] + span)
    ax.set_aspect("equal")
    ax.axis("off")
    out = ASSETS / f"proxy_{case}.png"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    return out


# ---------------------------------------------------------------- footprint vs gate plan
def plan_panel(ax, row: dict) -> None:
    fp = row["sppa_footprint_m"]
    dims = row["sppa_metric_dims_m"]
    ang = math.radians(fp["orientation_deg_axial"])
    ca, sa = math.cos(ang), math.sin(ang)

    def rect(L, W):
        pts = [(L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2), (-L / 2, -W / 2)]
        return [(ca * s - sa * w, sa * s + ca * w) for s, w in pts]

    raw = rect(fp["length_m"], fp["width_m"])
    gated = rect(dims["length"], dims["width"])
    ax.add_patch(MplPolygon(raw, closed=True, fill=False, ec="#d62728", ls="--", lw=1.8))
    ax.add_patch(MplPolygon(gated, closed=True, fill=False, ec="#0072B2", lw=2.2))
    ax.plot(0, 0, "k+", ms=8, mew=1.6)
    lim = max(fp["length_m"], fp["width_m"]) * 0.68
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3, lw=0.4)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("E (m)", fontsize=8)
    ax.set_ylabel("N (m)", fontsize=8)
    ax.plot([], [], color="#d62728", ls="--", lw=1.8,
            label=f'mask footprint {fp["length_m"]:.1f} x {fp["width_m"]:.1f} m')
    ax.plot([], [], color="#0072B2", lw=2.2,
            label=f'gated dims {dims["length"]:.2f} x {dims["width"]:.2f} x {dims["height"]:.2f} m')
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.14), framealpha=0.95)


# ---------------------------------------------------------------- compose
def main() -> None:
    rows = {r["case_id"]: r for r in json.loads(REPLAY_JSON.read_text(encoding="utf-8"))["rows"]}
    build_meshes(rows)
    proxy_imgs = {c: render_proxy(c) for c in CASES}

    fig = plt.figure(figsize=(13.6, 8.6), dpi=300)
    gs = fig.add_gridspec(2, 4, width_ratios=[1.05, 0.95, 0.75, 0.85], hspace=0.46, wspace=0.10)
    for i, case in enumerate(CASES):
        row = rows[case]
        ax = fig.add_subplot(gs[i, 0])
        ax.imshow(Image.open(DET_IMG[case]))
        ax.set_title("(a) real flight photo + YOLOE-26s evidence", fontsize=9.5)
        ax.axis("off")
        ax.text(0.0, -0.07, ROW_TITLE[case], transform=ax.transAxes, fontsize=8.5,
                color="#333333", style="italic")
        ax = fig.add_subplot(gs[i, 1])
        plan_panel(ax, row)
        ax.set_title("(b) geo-projected mask footprint vs gated dims", fontsize=9.5)
        ax = fig.add_subplot(gs[i, 2])
        ax.imshow(Image.open(proxy_imgs[case]))
        ax.set_title("(c) SPPA proxy (runtime, roles)", fontsize=9.5)
        ax.axis("off")
        ax = fig.add_subplot(gs[i, 3])
        ax.imshow(Image.open(TRIPOSR_IMG[case]))
        ax.set_title("(d) TripoSR, same crop + RTX 5090", fontsize=9.5)
        ax.axis("off")
        ax.text(0.0, -0.07, TRIPOSR_NOTE[case], transform=ax.transAxes, fontsize=8,
                color="#333333", style="italic")
    fig.text(0.995, 0.005,
             "Hunyuan3D-2mini-turbo (6 GB): hard failure 'No surface found' on both aerial crops (5 and 20 steps)",
             fontsize=8, color="#666666", ha="right", style="italic")
    fig.savefig(OUT_FIG, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print("SAVED", OUT_FIG)


if __name__ == "__main__":
    main()
