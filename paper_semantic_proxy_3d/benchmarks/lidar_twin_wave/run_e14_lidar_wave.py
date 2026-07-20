"""E14 LiDAR Twin Wave — offline degradation, detection, fitting, scoring.

SIMULATED LiDAR-class returns (UE raycasts), positions locked to GT,
reconstruction-only scope. See E14_PROTOCOL.md (frozen before any outcome).

Reads:  points.jsonl (raw exact raycast hits from Unreal/Scripts/e14_lidar_scan_pie.py)
Writes: results.jsonl (resumable by (tower_id, arm, method)), e14_analysis.json.

Arms (deterministic, frozen seeds):
  clean    : dropout 5%,  sigma 2 cm, max range 150 m, full ray grid
  degraded : dropout 50%, sigma 5 cm, max range 100 m, angular downsample x4/x2

Run: python run_e14_lidar_wave.py
"""
from __future__ import annotations

import json
import math
import sys
import time
import zlib
from pathlib import Path

import numpy as np

E14_ROOT = Path(__file__).resolve().parent
REPO_ROOT = E14_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "benchmarks" / "real_stream_wave"))

from e7_common import EVAL_RES, EXPLORATORY_LABEL, scaled_graphs_for_family, mv  # noqa: E402
from run_e7_real_stream import (  # noqa: E402
    case_window, cell_centers, fit_top_only, rasterize_masks, voxelize_oriented_box,
)

GT_GEO = REPO_ROOT / "benchmarks" / "oblique_twin_wave" / "gt" / "tower_geometry.json"
GT_OBJ = REPO_ROOT / "benchmarks" / "oblique_twin_wave" / "gt" / "tower_mesh_Internal.obj"
POINTS = E14_ROOT / "points.jsonl"
RESULTS = E14_ROOT / "results.jsonl"
ANALYSIS = E14_ROOT / "e14_analysis.json"

TOWER_LABELS = ["t0", "t1", "t2", "t3", "t4", "t5", "t7", "t9", "t10", "tower12", "tower13"]
FAMILY = "lattice_tower"
METHODS = ("sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule")

ARMS = {
    "clean": {"dropout": 0.05, "sigma_cm": 2.0, "max_range_m": 150.0, "az_step": 1, "el_step": 1, "seed": 14001},
    "degraded": {"dropout": 0.50, "sigma_cm": 5.0, "max_range_m": 100.0, "az_step": 4, "el_step": 2, "seed": 14002},
}

CELL_M = 1.0
STRUCT_ZRANGE_M = 5.0
MIN_CLUSTER_POINTS = 30
BOOT_SEED = 77157
BOOT_N = 10000


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def quat_to_rot(q: dict) -> np.ndarray:
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    verts, faces = [], []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                parts = line.split()
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                if len(idx) == 3:
                    faces.append(idx)
                elif len(idx) == 4:
                    faces.append([idx[0], idx[1], idx[2]])
                    faces.append([idx[0], idx[2], idx[3]])
    return np.asarray(verts, dtype=np.float64), np.asarray(faces, dtype=np.int64)


def obj_to_actor_local_m(verts_obj_cm: np.ndarray) -> np.ndarray:
    """OBJ (x,y,z) = Unreal local (x,z,y), cm -> m (E11a documented mapping)."""
    return np.stack([verts_obj_cm[:, 0] / 100.0,
                     verts_obj_cm[:, 2] / 100.0,
                     verts_obj_cm[:, 1] / 100.0], axis=1)


# ---------------------------------------------------------------------------
# Arm synthesis (deterministic degradation of raw returns)
# ---------------------------------------------------------------------------

def scan_points_actor(scan: dict, arm: dict, anchor_cm: np.ndarray, rot_w2l: np.ndarray) -> np.ndarray:
    """Returns (n,3) actor-local metres after arm degradation."""
    o = np.asarray(scan["origin_world_cm"], dtype=np.float64)
    pts, dists, keys = [], [], []
    az_step, el_step = arm["az_step"], arm["el_step"]
    for key, h in scan["hits"].items():
        i = int(key)
        az_i, el_i = divmod(i, 16)
        if az_i % az_step or el_i % el_step:
            continue
        pts.append(h[:3])
        dists.append(h[3])
        keys.append(i)
    if not pts:
        return np.zeros((0, 3), dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64)
    dists = np.asarray(dists, dtype=np.float64)
    rng = np.random.default_rng(arm["seed"] + zlib.crc32(scan["frame_id"].encode()) % 100000)
    keep = rng.random(len(pts)) >= arm["dropout"]
    keep &= dists <= arm["max_range_m"] * 100.0
    pts, dists = pts[keep], dists[keep]
    if not len(pts):
        return np.zeros((0, 3), dtype=np.float64)
    u = (pts - o) / dists[:, None]
    noisy = o + u * (dists + rng.normal(0.0, arm["sigma_cm"], len(dists)))[:, None]
    return (rot_w2l @ (noisy - anchor_cm).T).T / 100.0


# ---------------------------------------------------------------------------
# Detection (GT-free; E14_PROTOCOL.md)
# ---------------------------------------------------------------------------

def detect(pts: np.ndarray) -> dict | None:
    if len(pts) < MIN_CLUSTER_POINTS:
        return None
    ij = np.floor(pts[:, :2] / CELL_M).astype(np.int64)
    cell_of = {}
    for n, (i, j) in enumerate(ij):
        cell_of.setdefault((i, j), []).append(n)
    zrange = {c: pts[idx, 2].max() - pts[idx, 2].min() for c, idx in cell_of.items()}
    struct = {c for c, zr in zrange.items() if zr >= STRUCT_ZRANGE_M}
    if not struct:
        return None
    # 8-connected components over structure cells
    comps, seen = [], set()
    for c in struct:
        if c in seen:
            continue
        stack, comp = [c], set()
        seen.add(c)
        while stack:
            i, j = stack.pop()
            comp.add((i, j))
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    nb = (i + di, j + dj)
                    if nb in struct and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        comps.append(comp)
    best = max(comps, key=lambda comp: sum(len(cell_of[c]) for c in comp))
    idx = [n for c in best for n in cell_of[c]]
    tp = pts[idx]
    if len(tp) < MIN_CLUSTER_POINTS:
        return None
    ground_z = float(np.percentile(tp[:, 2], 2.0))  # Amended A1: p2 (p10 overestimates base)
    height = float(tp[:, 2].max() - ground_z)
    if height < 3.0:
        return None
    low = tp[tp[:, 2] <= ground_z + 0.25 * height]
    if len(low) < 8:
        low = tp
    xy = low[:, :2]
    center = xy.mean(axis=0)
    cov = np.cov((xy - center).T)
    vals, vecs = np.linalg.eigh(cov)
    major = vecs[:, int(np.argmax(vals))]
    minor = np.array([-major[1], major[0]])
    proj_u = (tp[:, :2] - center) @ major
    proj_v = (tp[:, :2] - center) @ minor
    length = max(float(proj_u.max() - proj_u.min()), 0.3)
    width = max(float(proj_v.max() - proj_v.min()), 0.3)
    yaw = math.degrees(math.atan2(major[1], major[0])) % 180.0
    corners = []
    for su, sv in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        p = center + major * (su * length / 2) + minor * (sv * width / 2)
        corners.append({"north_m": float(p[0]), "east_m": float(p[1])})
    return {
        "n_points": int(len(tp)),
        "n_cells": int(len(best)),
        "ground_z_m": ground_z,
        "height_m": height,
        "footprint": {
            "center_north_m": float(center[0]), "center_east_m": float(center[1]),
            "length_m": length, "width_m": width,
            "orientation_deg_axial": yaw,
            "points_ned_m": corners,
        },
        "raw_points": tp,  # internal, not serialized
    }


# ---------------------------------------------------------------------------
# GT voxelization (surface-intersection occupancy; Protocol Amendment A1)
# A voxel is occupied iff the mesh surface passes through it. Implemented by
# barycentric sampling of every triangle at <= 0.4 x the finest window pitch
# and marking the containing voxels. (The lattice is a thin-beam structure,
# not a watertight solid; even-odd solid fill undersamples it to ~nothing.)
# ---------------------------------------------------------------------------

def voxelize_mesh_surface(verts: np.ndarray, faces: np.ndarray, window: dict, res: int = EVAL_RES) -> np.ndarray:
    xs = cell_centers(window["x"], res)
    ys = cell_centers(window["y"], res)
    zs = cell_centers(window["z"], res)
    pitch = min((window["x"][1] - window["x"][0]) / res,
                (window["y"][1] - window["y"][0]) / res,
                (window["z"][1] - window["z"][0]) / res)
    step = 0.4 * pitch
    occ = np.zeros((res, res, res), dtype=bool)
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    edge = np.maximum.reduce([
        np.linalg.norm(v1 - v0, axis=1),
        np.linalg.norm(v2 - v1, axis=1),
        np.linalg.norm(v0 - v2, axis=1)])
    n_sub = np.maximum(1, np.ceil(edge / step).astype(np.int64))
    x0, y0, z0 = window["x"][0], window["y"][0], window["z"][0]
    px = (window["x"][1] - x0) / res
    py = (window["y"][1] - y0) / res
    pz = (window["z"][1] - z0) / res
    for f in range(len(faces)):
        n = int(n_sub[f])
        iu, jv = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        m = (iu + jv) <= n
        uu = iu[m] / n
        vv = jv[m] / n
        p = (uu[:, None] * v0[f] + vv[:, None] * v1[f] + (1.0 - uu - vv)[:, None] * v2[f])
        ii = np.clip(((p[:, 0] - x0) / px).astype(np.int64), 0, res - 1)
        jj = np.clip(((p[:, 1] - y0) / py).astype(np.int64), 0, res - 1)
        kk = np.clip(((p[:, 2] - z0) / pz).astype(np.int64), 0, res - 1)
        occ[ii, jj, kk] = True
    return occ


# ---------------------------------------------------------------------------
# Methods (E7 machinery)
# ---------------------------------------------------------------------------

def run_method(method: str, top: np.ndarray, side: np.ndarray, window: dict,
               height_m: float, det: dict) -> np.ndarray:
    fp = det["footprint"]
    fp_len, fp_wid = fp["length_m"], fp["width_m"]
    if method == "sppa_mvfit":
        fit = fit_top_only(FAMILY, top, height_m, window["nom"][2])
        return mv.voxelize_actor(fit["actor"], EVAL_RES)
    if method == "generic_mvfit":
        from e7_common import FAMILY_SCALE_M_PER_UNIT, graph_extent_units
        gh = graph_extent_units("generic")[2] * FAMILY_SCALE_M_PER_UNIT[FAMILY]
        fit = fit_top_only("generic", top, height_m, gh)
        return mv.voxelize_actor(fit["actor"], EVAL_RES)
    if method == "obb":
        return voxelize_oriented_box(window, (0.0, 0.0), (fp_len, fp_wid), 0.0, 0.0, height_m)
    if method == "aabb":
        ns = np.array([p["north_m"] for p in fp["points_ned_m"]])
        es = np.array([p["east_m"] for p in fp["points_ned_m"]])
        # actor-frame axis-aligned bbox of the yawed footprint, re-centred on the
        # GT-locked window centre (position lock), yaw = -theta in window frame.
        theta = math.radians(fp["orientation_deg_axial"])
        du = 0.5 * float(ns.max() - ns.min())
        dv = 0.5 * float(es.max() - es.min())
        return voxelize_oriented_box(window, (0.0, 0.0), (2 * du, 2 * dv), -theta, 0.0, height_m)
    if method == "visual_hull":
        occ, _ = mv.baseline_occupancy("nonsemantic_visual_hull", top, side, EVAL_RES)
        return occ
    if method == "capsule":
        occ, _ = mv.baseline_occupancy("capsule", top, side, EVAL_RES)
        return occ
    raise ValueError(method)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    return float(np.count_nonzero(a & b) / union) if union else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    geo = json.loads(GT_GEO.read_text(encoding="utf-8"))
    towers = {t["label"]: t for t in geo["actors"]}
    verts_obj, faces = load_obj(GT_OBJ)
    mesh_local = obj_to_actor_local_m(verts_obj)  # (v,3) actor-local metres
    print(f"GT mesh: {len(verts_obj)} v, {len(faces)} f; "
          f"local bbox x[{mesh_local[:,0].min():.2f},{mesh_local[:,0].max():.2f}] "
          f"y[{mesh_local[:,1].min():.2f},{mesh_local[:,1].max():.2f}] "
          f"z[{mesh_local[:,2].min():.2f},{mesh_local[:,2].max():.2f}] m")

    scans: dict[str, list[dict]] = {t: [] for t in TOWER_LABELS}
    with POINTS.open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            scans[row["tower_id"]].append(row)
    print("scans per tower:", {t: len(s) for t, s in scans.items()})

    done = set()
    if RESULTS.exists():
        with RESULTS.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    done.add((r["tower_id"], r["arm"], r["method"]))
                except Exception:
                    pass
    print(f"{len(done)} result rows already present; skipping those keys")

    out_fh = RESULTS.open("a", encoding="utf-8")
    detect_dump = {}
    for label in TOWER_LABELS:
        rec = towers[label]
        anchor = rec["world_location"]
        anchor_cm = np.array([anchor["x"], anchor["y"], anchor["z"]], dtype=np.float64)
        rot_l2w = quat_to_rot(rec["world_rotation_quat"])
        rot_w2l = rot_l2w.T
        off = rec["pivot_to_bounds_origin_offset"]
        gt_center_xy = np.array([off["x"] / 100.0, off["y"] / 100.0])  # actor-local m
        tower_scans = scans.get(label, [])
        if not tower_scans:
            print(f"!! no scans for {label}")
            continue
        for arm_name, arm in ARMS.items():
            t0 = time.perf_counter()
            pts = np.concatenate([scan_points_actor(s, arm, anchor_cm, rot_w2l) for s in tower_scans], axis=0)
            det = detect(pts)
            if det is None:
                for method in METHODS:
                    if (label, arm_name, method) in done:
                        continue
                    out_fh.write(json.dumps({
                        "tower_id": label, "arm": arm_name, "method": method,
                        "detection_failed": True, "n_returns": int(len(pts)),
                        "iou_3d": None, "footprint_iou": None}) + "\n")
                out_fh.flush()
                print(f"{label}/{arm_name}: DETECTION FAILED ({len(pts)} returns)")
                continue
            raw_tp = det.pop("raw_points")
            detect_dump[f"{label}/{arm_name}"] = {
                "n_returns": int(len(pts)), **{k: v for k, v in det.items() if k != "footprint"},
                "footprint": det["footprint"], "points": raw_tp.tolist(),
            }
            fp = det["footprint"]
            height_m = det["height_m"]
            theta = math.radians(fp["orientation_deg_axial"])
            # window frame: rotate actor XY by -theta; window centre = GT mesh centre
            c, s = math.cos(-theta), math.sin(-theta)
            wc = np.array([c * gt_center_xy[0] - s * gt_center_xy[1],
                           s * gt_center_xy[0] + c * gt_center_xy[1]])
            mesh_w = mesh_local.copy()
            mx = c * mesh_local[:, 0] - s * mesh_local[:, 1] - wc[0]
            my = s * mesh_local[:, 0] + c * mesh_local[:, 1] - wc[1]
            mesh_w[:, 0], mesh_w[:, 1] = mx, my

            mv.GRAPHS = scaled_graphs_for_family(FAMILY)  # in-memory only
            window = case_window(fp["length_m"], fp["width_m"], height_m, FAMILY)
            mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}  # in-memory only
            top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], height_m)
            gt_occ = voxelize_mesh_surface(mesh_w, faces, window)
            gt_top = gt_occ.any(axis=2)
            fit_ms = (time.perf_counter() - t0) * 1000.0

            for method in METHODS:
                if (label, arm_name, method) in done:
                    continue
                t1 = time.perf_counter()
                occ = run_method(method, top, side, window, height_m, det)
                latency = (time.perf_counter() - t1) * 1000.0
                row = {
                    "tower_id": label, "arm": arm_name, "method": method,
                    "detection_failed": False,
                    "n_returns": int(len(pts)), "n_cluster": det["n_points"],
                    "obs_length_m": fp["length_m"], "obs_width_m": fp["width_m"],
                    "obs_yaw_deg": fp["orientation_deg_axial"], "obs_height_m": height_m,
                    "gt_ground_z_offset_m": det["ground_z_m"],
                    "iou_3d": iou(occ, gt_occ),
                    "footprint_iou": iou(occ.any(axis=2), gt_top),
                    "occ_voxels": int(np.count_nonzero(occ)),
                    "gt_voxels": int(np.count_nonzero(gt_occ)),
                    "latency_ms": latency,
                }
                out_fh.write(json.dumps(row) + "\n")
            out_fh.flush()
            print(f"{label}/{arm_name}: returns={len(pts)} cluster={det['n_points']} "
                  f"fp={fp['length_m']:.2f}x{fp['width_m']:.2f} yaw={fp['orientation_deg_axial']:.1f} "
                  f"h={height_m:.2f} (setup {fit_ms:.0f} ms)")
    out_fh.close()
    (E14_ROOT / "e14_detect_dump.json").write_text(json.dumps(detect_dump), encoding="utf-8")
    summarize()
    return 0


def summarize() -> None:
    rows = [json.loads(l) for l in RESULTS.open("r", encoding="utf-8")]
    rng = np.random.default_rng(BOOT_SEED)

    def stats(vals):
        arr = np.asarray(vals, dtype=float)
        if not len(arr):
            return None
        idx = rng.integers(0, len(arr), (BOOT_N, len(arr)))
        boots = arr[idx].mean(axis=1)
        return {"n": int(len(arr)), "mean": float(arr.mean()), "median": float(np.median(arr)),
                "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}

    per = {}
    for arm in ARMS:
        per[arm] = {}
        for method in METHODS:
            sel = [r for r in rows if r["arm"] == arm and r["method"] == method and not r["detection_failed"]]
            fails = sum(1 for r in rows if r["arm"] == arm and r["method"] == method and r["detection_failed"])
            prec, rec = [], []
            for r in sel:
                inter = r["iou_3d"] * (r["occ_voxels"] + r["gt_voxels"]) / (1.0 + r["iou_3d"])
                prec.append(inter / r["occ_voxels"] if r["occ_voxels"] else 0.0)
                rec.append(inter / r["gt_voxels"] if r["gt_voxels"] else 0.0)
            per[arm][method] = {
                "iou_3d": stats([r["iou_3d"] for r in sel]),
                "footprint_iou": stats([r["footprint_iou"] for r in sel]),
                "precision_vox": stats(prec),
                "recall_vox": stats(rec),
                "n_detection_failed": fails,
            }
    # paired clean-vs-degraded deltas on towers where BOTH arms detected
    paired = {}
    for method in METHODS:
        c = {r["tower_id"]: r for r in rows if r["arm"] == "clean" and r["method"] == method and not r["detection_failed"]}
        d = {r["tower_id"]: r for r in rows if r["arm"] == "degraded" and r["method"] == method and not r["detection_failed"]}
        both = sorted(set(c) & set(d))
        deltas = [d[t]["iou_3d"] - c[t]["iou_3d"] for t in both]
        paired[method] = {"n_paired": len(both), "towers": both, "iou3d_delta_degraded_minus_clean": stats(deltas)}
    analysis = {
        "label": EXPLORATORY_LABEL,
        "experiment": "E14 LiDAR Twin Wave (SIMULATED LiDAR-class returns; positions locked to GT; reconstruction-only)",
        "protocol": "E14_PROTOCOL.md (frozen before any outcome; Amendment A1 documented inside)",
        "arms": ARMS,
        "per_arm_method": per,
        "paired_clean_vs_degraded": paired,
        "headline": {
            "clean_sppa_iou3d": per["clean"]["sppa_mvfit"]["iou_3d"],
            "degraded_sppa_iou3d": per["degraded"]["sppa_mvfit"]["iou_3d"],
            "degraded_detection_failures": per["degraded"]["sppa_mvfit"]["n_detection_failed"],
        },
    }
    ANALYSIS.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(analysis["headline"], indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
