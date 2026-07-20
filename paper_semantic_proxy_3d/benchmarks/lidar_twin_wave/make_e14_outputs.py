"""E14 outputs: e14_table.tex, fig_e14_lidar.png, supplementary tolerance metric.

Reads results.jsonl + e14_analysis.json + e14_detect_dump.json (all produced by
run_e14_lidar_wave.py). The 1-voxel-tolerant IoU is POST-HOC SUPPLEMENTARY
(labeled as such): it re-runs the same frozen pipeline and compares occupancies
with both sides dilated by one voxel, because voxel-exact IoU between two
different lattice realisations is dominated by sub-voxel member placement.

Run: python make_e14_outputs.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

E14_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(E14_ROOT))
sys.path.insert(0, str(E14_ROOT.parents[1] / "benchmarks" / "real_stream_wave"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import ndimage

from run_e14_lidar_wave import (  # noqa: E402
    ARMS, EVAL_RES, FAMILY, GT_GEO, GT_OBJ, METHODS, RESULTS, TOWER_LABELS,
    detect, load_obj, obj_to_actor_local_m, quat_to_rot, run_method,
    scan_points_actor, voxelize_mesh_surface, iou,
)
from e7_common import scaled_graphs_for_family, mv  # noqa: E402
from run_e7_real_stream import case_window, rasterize_masks  # noqa: E402

POINTS = E14_ROOT / "points.jsonl"
DETECT_DUMP = E14_ROOT / "e14_detect_dump.json"
ANALYSIS = E14_ROOT / "e14_analysis.json"
TABLE_TEX = E14_ROOT / "e14_table.tex"
FIG_PNG = E14_ROOT / "fig_e14_lidar.png"

FIG_TOWER = "t3"
FIG_ARM = "clean"


def case_setup(label: str, arm: str):
    """Replay the frozen pipeline for one case; returns dict with window,
    det, gt_occ, mesh_w and per-method occupancy."""
    geo = json.loads(GT_GEO.read_text(encoding="utf-8"))
    rec = {t["label"]: t for t in geo["actors"]}[label]
    verts_obj, faces = load_obj(GT_OBJ)
    mesh_local = obj_to_actor_local_m(verts_obj)
    anchor = rec["world_location"]
    anchor_cm = np.array([anchor["x"], anchor["y"], anchor["z"]])
    rot_w2l = quat_to_rot(rec["world_rotation_quat"]).T
    off = rec["pivot_to_bounds_origin_offset"]
    gt_center_xy = np.array([off["x"] / 100.0, off["y"] / 100.0])
    scans = []
    with POINTS.open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["tower_id"] == label:
                scans.append(row)
    pts = np.concatenate([scan_points_actor(s, ARMS[arm], anchor_cm, rot_w2l) for s in scans], axis=0)
    det = detect(pts)
    raw = det.pop("raw_points")
    fp = det["footprint"]
    theta = math.radians(fp["orientation_deg_axial"])
    c, s = math.cos(-theta), math.sin(-theta)
    wc = np.array([c * gt_center_xy[0] - s * gt_center_xy[1],
                   s * gt_center_xy[0] + c * gt_center_xy[1]])
    mesh_w = mesh_local.copy()
    mesh_w[:, 0] = c * mesh_local[:, 0] - s * mesh_local[:, 1] - wc[0]
    mesh_w[:, 1] = s * mesh_local[:, 0] + c * mesh_local[:, 1] - wc[1]
    mv.GRAPHS = scaled_graphs_for_family(FAMILY)
    window = case_window(fp["length_m"], fp["width_m"], det["height_m"], FAMILY)
    mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}
    top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], det["height_m"])
    gt_occ = voxelize_mesh_surface(mesh_w, faces, window)
    occs = {m: run_method(m, top, side, window, det["height_m"], det) for m in METHODS}
    return {"window": window, "det": det, "raw_points": raw, "gt_occ": gt_occ,
            "occs": occs, "faces": faces, "mesh_w": mesh_w}


def supplementary_tolerance(rows) -> dict:
    """Post-hoc supplementary: 1-voxel-dilated IoU (both sides), per arm x method."""
    out = {}
    for arm in ARMS:
        for method in METHODS:
            vals = []
            for r in rows:
                if r["arm"] != arm or r["method"] != method or r["detection_failed"]:
                    continue
                cs = case_setup(r["tower_id"], arm)
                occ = cs["occs"][method]
                gt = cs["gt_occ"]
                d_occ = ndimage.binary_dilation(occ, iterations=1)
                d_gt = ndimage.binary_dilation(gt, iterations=1)
                vals.append(iou(d_occ, d_gt))
            arr = np.asarray(vals)
            out.setdefault(arm, {})[method] = {
                "n": int(len(arr)),
                "mean": float(arr.mean()) if len(arr) else None,
                "median": float(np.median(arr)) if len(arr) else None,
            }
    return out


def make_table(analysis: dict) -> str:
    lines = [
        "% E14 LiDAR Twin Wave — SIMULATED LiDAR-class returns (UE raycasts), positions locked to GT.",
        "% Exploratory post-hoc. 3D voxel IoU vs welded tower mesh at 64^3 (E14_PROTOCOL.md, Amendment A1).",
        "\\begin{tabular}{llrrr}",
        "\\toprule",
        "Arm & Method & Mean IoU$_{3D}$ & Median & 95\\% CI (boot.) \\\\",
        "\\midrule",
    ]
    labels = {"sppa_mvfit": "SPPA-MVFit", "generic_mvfit": "Generic-MVFit", "obb": "OBB",
              "aabb": "AABB", "visual_hull": "Visual hull", "capsule": "Capsule"}
    for arm_i, arm in enumerate(("clean", "degraded")):
        arm_name = "Clean" if arm == "clean" else "Degraded (heavy fog)"
        for i, method in enumerate(METHODS):
            st = analysis["per_arm_method"][arm][method]["iou_3d"]
            fails = analysis["per_arm_method"][arm][method]["n_detection_failed"]
            if st is None:
                continue
            ci = st["ci95"]
            arm_cell = f"\\multirow{{{len(METHODS)}}}{{*}}{{{arm_name}}}" if i == 0 else ""
            note = f" \\footnotesize({fails} det. fail)" if (i == 0 and fails) else ""
            lines.append(f"{arm_cell}{note} & {labels[method]} & {st['mean']:.3f} & {st['median']:.3f} "
                         f"& [{ci[0]:.3f}, {ci[1]:.3f}] \\\\")
        if arm_i == 0:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


def make_figure(analysis: dict) -> None:
    cs = case_setup(FIG_TOWER, FIG_ARM)
    raw = cs["raw_points"]
    gt_top = cs["gt_occ"].any(axis=2)
    sppa_top = cs["occs"]["sppa_mvfit"].any(axis=2)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2))

    ax = axes[0]
    sc = ax.scatter(raw[:, 0], raw[:, 1], c=raw[:, 2], s=1.5, cmap="viridis")
    ax.set_title(f"(a) Simulated LiDAR returns — {FIG_TOWER}, {FIG_ARM} arm\n"
                 f"(actor frame, merged 5 scans, n={len(raw)} cluster pts)")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    cb = fig.colorbar(sc, ax=ax, shrink=0.8); cb.set_label("z (m)")

    ax = axes[1]
    ax.contour(gt_top.T, levels=[0.5], colors="black", linewidths=1.6)
    ax.contour(sppa_top.T, levels=[0.5], colors="tab:blue", linewidths=1.4, linestyles="--")
    fp = cs["det"]["footprint"]
    L, W = fp["length_m"] / 2, fp["width_m"] / 2
    rect = np.array([[-L, -W], [L, -W], [L, W], [-L, W], [-L, -W]])
    wx, wy = cs["window"]["x"], cs["window"]["y"]
    res = gt_top.shape[0]
    def to_idx(px, py):
        return ((px - wx[0]) / (wx[1] - wx[0]) * res, (py - wy[0]) / (wy[1] - wy[0]) * res)
    rx, ry = to_idx(rect[:, 0], rect[:, 1])
    ax.plot(rx, ry, color="tab:red", lw=1.4, label="observed footprint")
    ax.plot([], [], color="black", lw=1.6, label="GT mesh (top proj.)")
    ax.plot([], [], color="tab:blue", lw=1.4, ls="--", label="SPPA proxy (top proj.)")
    ax.set_title(f"(b) Top view: observed footprint vs GT vs SPPA proxy\n"
                 f"(fp {fp['length_m']:.2f}$\\times${fp['width_m']:.2f} m, "
                 f"h={cs['det']['height_m']:.2f} m, yaw={fp['orientation_deg_axial']:.1f}°)")
    ax.set_xlabel("x cell"); ax.set_ylabel("y cell"); ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")

    ax = axes[2]
    xpos = np.arange(len(METHODS))
    width = 0.38
    for k, arm in enumerate(("clean", "degraded")):
        means, los, his, ns = [], [], [], []
        for method in METHODS:
            st = analysis["per_arm_method"][arm][method]["iou_3d"]
            means.append(st["mean"] if st else 0.0)
            los.append(st["mean"] - st["ci95"][0] if st else 0.0)
            his.append(st["ci95"][1] - st["mean"] if st else 0.0)
            ns.append(st["n"] if st else 0)
        bars = ax.bar(xpos + (k - 0.5) * width, means, width,
                      label=f"{arm} (n={ns[0]})", color=("tab:blue" if arm == "clean" else "tab:orange"),
                      alpha=0.85)
        ax.errorbar(xpos + (k - 0.5) * width, means, yerr=[los, his], fmt="none",
                    ecolor="black", elinewidth=1, capsize=3)
    ax.set_xticks(xpos)
    ax.set_xticklabels([m.replace("_", "-") for m in METHODS], rotation=20, ha="right")
    ax.set_ylabel("3D voxel IoU vs exact mesh (64³)")
    ax.set_title("(c) Method x arm — mean IoU$_{3D}$ [95% CI]\n(degraded: 4/11 towers lost to detection failure)")
    ax.legend(); ax.grid(axis="y", alpha=0.3)

    fig.suptitle("E14 — camera-less reconstruction from SIMULATED LiDAR-class returns "
                 "(UE raycasts; positions locked to GT; exploratory post-hoc)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(FIG_PNG, dpi=160)
    plt.close(fig)


def main() -> int:
    rows = [json.loads(l) for l in RESULTS.open("r", encoding="utf-8")]
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    print("supplementary 1-voxel-tolerant IoU (post-hoc, refit pass)...")
    analysis["supplementary_tolerance_1vox_iou"] = {
        "note": ("POST-HOC SUPPLEMENTARY (not the frozen primary metric): both occupancies "
                 "dilated by 1 voxel before IoU; compensates sub-voxel member placement when "
                 "comparing two different lattice realisations."),
        "per_arm_method": supplementary_tolerance(rows),
    }
    ANALYSIS.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")

    TABLE_TEX.write_text(make_table(analysis), encoding="utf-8")
    print("wrote", TABLE_TEX)
    make_figure(analysis)
    print("wrote", FIG_PNG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
