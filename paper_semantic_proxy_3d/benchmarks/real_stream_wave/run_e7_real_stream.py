"""E7 "Real Stream Wave" - main benchmark runner (exploratory post-hoc).

Equal conditions on a REAL stream:
  * one observation per accepted detection (oriented footprint + height),
    identical input for every method (see e7_common.build_observation);
  * SPPA-MVFit and Generic-MVFit share the SAME fitter (frozen coordinate
    descent, 31 candidates, 5 parameters, frozen BOUNDS) in the SAME per-case
    metric window, in the operational top-only mode: x/y fitted on the
    footprint mask, z-scale anchored to the monocular height estimate;
  * OBB / AABB / visual hull / capsule consume the same observation;
  * family token comes from the REAL detector label; detector errors are kept
    and reported (token_correct flag + correct-token refit arm).

Outputs: results.jsonl (one row per case x method), e7_summary.json.

Run:  python run_e7_real_stream.py
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

from e7_common import (  # noqa: E402
    CAMERA, CLASS_TO_FAMILY, E7_ROOT, EVAL_RES, EXPLORATORY_LABEL,
    FAMILY_NOMINAL_HEIGHT_M, FAMILY_SCALE_M_PER_UNIT, GT_FOOTPRINT_DIMS_M,
    OBS_RES, GeoProjector, graph_extent_units, iter_cases, load_gt_static,
    match_gt, mv, scaled_graphs_for_family,
)

OUT = E7_ROOT

# ---------------------------------------------------------------------------
# Top-only MVFit (operational mode): verbatim replica of the frozen coordinate
# descent used in e2_top_only (same STEP_FRACTIONS, parameter order, tie-break,
# 31 candidates), restricted to the top view. z-scale is NOT fitted from the
# footprint; it is anchored post-fit to the monocular height estimate within
# the frozen bounds (documented operational rule, identical for both MVFits).
# ---------------------------------------------------------------------------


def regularizer(theta: np.ndarray) -> float:
    return 0.01 * float(np.sum(theta[:3] ** 2)) + 0.005 * float((theta[3] - 1.0) ** 2) + 0.005 * float(theta[4] ** 2)


def init_top_only(graph_name: str, top_mask: np.ndarray) -> tuple[np.ndarray, bool]:
    extent = mv._mask_extent(top_mask, "x", "y")
    if extent is None:
        return mv.default_theta(), True
    default_top, _ = mv.render_actor_masks(mv.build_actor(graph_name, mv.default_theta()), top_mask.shape[0])
    default_extent = mv._mask_extent(default_top, "x", "y")
    if default_extent is None:
        raise RuntimeError("graph has empty default top projection")
    ratio_u = extent[2] / max(default_extent[2], 1e-9)
    ratio_v = extent[3] / max(default_extent[3], 1e-9)
    theta = mv.default_theta()
    theta[0] = math.log(float(np.clip(ratio_u, math.exp(mv.BOUNDS[0, 0]), math.exp(mv.BOUNDS[0, 1]))))
    theta[1] = math.log(float(np.clip(ratio_v, math.exp(mv.BOUNDS[1, 0]), math.exp(mv.BOUNDS[1, 1]))))
    return theta, False


def objective_top(graph_name: str, theta: np.ndarray, top_mask: np.ndarray) -> tuple[float, dict[str, float]]:
    actor = mv.build_actor(graph_name, theta)
    top_pred, _ = mv.render_actor_masks(actor, top_mask.shape[0])
    top_iou = mv._iou2d(top_pred, top_mask)
    reg = regularizer(theta)
    return (1.0 - top_iou) + reg, {"top_iou": top_iou, "regularizer": reg}


def fit_top_only(graph_name: str, top_mask: np.ndarray, height_m: float, graph_height_m: float) -> dict:
    """Frozen coordinate descent (31 evaluations) on the footprint mask."""
    theta, empty = init_top_only(graph_name, top_mask)
    value, details = objective_top(graph_name, theta, top_mask)
    evaluations = 1
    spans = mv.BOUNDS[:, 1] - mv.BOUNDS[:, 0]
    for fraction in mv.STEP_FRACTIONS:
        for parameter_index in range(len(mv.PARAMETER_NAMES)):
            candidates = [(value, details, theta.copy())]
            for direction in (-1.0, 1.0):
                proposal = theta.copy()
                proposal[parameter_index] = np.clip(
                    proposal[parameter_index] + direction * fraction * spans[parameter_index],
                    mv.BOUNDS[parameter_index, 0], mv.BOUNDS[parameter_index, 1])
                proposal_value, proposal_details = objective_top(graph_name, proposal, top_mask)
                evaluations += 1
                candidates.append((proposal_value, proposal_details, proposal))
            value, details, theta = min(candidates, key=lambda item: mv._candidate_key(item[0], item[1], item[2]))
    if evaluations != 31:
        raise AssertionError(f"candidate budget drift: {evaluations}")
    # Height anchor: z-scale from the monocular height estimate (frozen bounds).
    anchor = math.log(float(np.clip(height_m / max(graph_height_m, 1e-9),
                                    math.exp(mv.BOUNDS[2, 0]), math.exp(mv.BOUNDS[2, 1]))))
    theta[2] = anchor
    return {"theta": theta, "objective": value, "top_iou": details["top_iou"],
            "empty_observation": empty, "evaluations": evaluations,
            "actor": mv.build_actor(graph_name, theta)}


# ---------------------------------------------------------------------------
# Per-case metric window, masks, voxel helpers
# ---------------------------------------------------------------------------


def case_window(fp_len: float, fp_wid: float, height_m: float, family: str) -> dict:
    """Metric fit window centered on the footprint; x = footprint major axis.

    Sized from the observation with headroom for the frozen scale bounds
    (reachable extent = nominal * [0.55, 1.80]); identical for all methods.
    """
    k = FAMILY_SCALE_M_PER_UNIT[family]
    ext = graph_extent_units(family)
    nom_x, nom_y, nom_z = (ext[0] * k, ext[1] * k, ext[2] * k)
    wx = max(1.5 * fp_len, 2.2 * nom_x)
    wy = max(1.5 * fp_wid, 2.2 * nom_y)
    wz = max(1.3 * height_m, 2.0 * nom_z)
    return {"x": (-wx / 2, wx / 2), "y": (-wy / 2, wy / 2), "z": (0.0, wz),
            "nom": (nom_x, nom_y, nom_z)}


def cell_centers(axis: tuple[float, float], res: int) -> np.ndarray:
    low, high = axis
    return np.linspace(low, high, res, endpoint=False) + (high - low) / (2 * res)


def rasterize_masks(window: dict, fp_len: float, fp_wid: float, height_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Observation masks in the window: top = footprint rect; side = height profile."""
    xs = cell_centers(window["x"], OBS_RES)
    ys = cell_centers(window["y"], OBS_RES)
    zs = cell_centers(window["z"], OBS_RES)
    tx, ty = np.meshgrid(xs, ys, indexing="ij")
    sx, sz = np.meshgrid(xs, zs, indexing="ij")
    top = (np.abs(tx) <= fp_len / 2) & (np.abs(ty) <= fp_wid / 2)
    side = (np.abs(sx) <= fp_len / 2) & (sz >= 0.0) & (sz <= height_m)
    return top, side


def voxelize_oriented_box(window: dict, center_xy: tuple[float, float], size_xy: tuple[float, float],
                          yaw_in_window: float, z0: float, z1: float) -> np.ndarray:
    xs = cell_centers(window["x"], EVAL_RES)
    ys = cell_centers(window["y"], EVAL_RES)
    zs = cell_centers(window["z"], EVAL_RES)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    dx = gx - center_xy[0]
    dy = gy - center_xy[1]
    c, s = math.cos(-yaw_in_window), math.sin(-yaw_in_window)
    lx = dx * c - dy * s
    ly = dx * s + dy * c
    inside_xy = (np.abs(lx) <= size_xy[0] / 2) & (np.abs(ly) <= size_xy[1] / 2)
    inside_z = (zs >= z0) & (zs <= z1)
    return inside_xy[:, :, None] & inside_z[None, None, :]


def gt_footprint_mask(window: dict, gt: dict, case: dict, bearing_rad: float) -> np.ndarray:
    """Declared GT base rect (see e7_common.GT_FOOTPRINT_DIMS_M) on the eval grid."""
    xs = cell_centers(window["x"], EVAL_RES)
    ys = cell_centers(window["y"], EVAL_RES)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    fp = case["footprint"]
    dn = (gt["north_m"] - case["drone_north_m"]) - fp["center_north_m"]
    de = (gt["east_m"] - case["drone_east_m"]) - fp["center_east_m"]
    cx = dn * math.cos(bearing_rad) + de * math.sin(bearing_rad)
    cy = -dn * math.sin(bearing_rad) + de * math.cos(bearing_rad)
    # Declared convention: anchor yaw used as compass bearing of the long axis.
    gt_bearing_window = math.radians(gt["yaw_deg"] % 180.0) - bearing_rad
    length, width = GT_FOOTPRINT_DIMS_M[gt["cls"]]
    dx, dy = gx - cx, gy - cy
    c, s = math.cos(-gt_bearing_window), math.sin(-gt_bearing_window)
    lx = dx * c - dy * s
    ly = dx * s + dy * c
    return (np.abs(lx) <= length / 2) & (np.abs(ly) <= width / 2)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def occupancy_centroid_window(occ: np.ndarray, window: dict) -> tuple[float, float, float] | None:
    idx = np.argwhere(occ)
    if not len(idx):
        return None
    xs = cell_centers(window["x"], EVAL_RES)
    ys = cell_centers(window["y"], EVAL_RES)
    zs = cell_centers(window["z"], EVAL_RES)
    return float(xs[idx[:, 0]].mean()), float(ys[idx[:, 1]].mean()), float(zs[idx[:, 2]].mean())


def reprojection_iou(occ: np.ndarray, window: dict, case: dict, bearing_rad: float) -> float:
    """Project occupied voxel centers through the REAL camera model and compare
    with the detector bbox (proxy mask; no segmentation weights exist for this
    detector - declared). Splat -> 5x5 closing -> fill holes, same for all."""
    idx = np.argwhere(occ)
    if not len(idx):
        return 0.0
    xs = cell_centers(window["x"], EVAL_RES)[idx[:, 0]]
    ys = cell_centers(window["y"], EVAL_RES)[idx[:, 1]]
    zs = cell_centers(window["z"], EVAL_RES)[idx[:, 2]]
    fp = case["footprint"]
    cb, sb = math.cos(bearing_rad), math.sin(bearing_rad)
    dn = fp["center_north_m"] + xs * cb - ys * sb
    de = fp["center_east_m"] + xs * sb + ys * cb
    ddown = case["telemetry"]["alt_agl"] - zs  # NED down, drone frame
    ned = np.stack([dn, de, ddown], axis=1)

    tel = case["telemetry"]
    R_ned_body = GeoProjector._ned_from_body(tel["yaw"], tel["pitch"], tel["roll"])
    R_mount = (GeoProjector._rot_z(CAMERA["mount_yaw_deg"]) @ GeoProjector._rot_y(CAMERA["mount_pitch_deg"])
               @ GeoProjector._rot_x(CAMERA["mount_roll_deg"]))
    A = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])  # cam->body
    cam = (A.T @ (R_mount.T @ (R_ned_body.T @ ned.T))).T  # (n,3): x right, y down, z fwd
    zc = cam[:, 2]
    valid = zc > 1e-6
    if not np.any(valid):
        return 0.0
    H, W = CAMERA["image_height"], CAMERA["image_width"]
    fy = (H / 2.0) / math.tan(math.radians(CAMERA["vfov_deg"]) / 2.0)
    fx = fy  # square pixels (VFOV + aspect, same derivation as the projector)
    u = np.rint(fx * cam[valid, 0] / zc[valid] + W / 2.0).astype(int)
    v = np.rint(fy * cam[valid, 1] / zc[valid] + H / 2.0).astype(int)
    inside = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    pred = np.zeros((H, W), dtype=bool)
    pred[v[inside], u[inside]] = True
    pred = ndimage.binary_closing(pred, structure=np.ones((5, 5), bool))
    pred = ndimage.binary_fill_holes(pred)
    b = case["bbox"]
    gt_mask = np.zeros((H, W), dtype=bool)
    gt_mask[int(b["y1"]):int(math.ceil(b["y2"])) + 1, int(b["x1"]):int(math.ceil(b["x2"])) + 1] = True
    union = np.count_nonzero(pred | gt_mask)
    return float(np.count_nonzero(pred & gt_mask) / union) if union else 0.0


# ---------------------------------------------------------------------------
# Methods (all consume the SAME observation; occupancy at 64^3 in the window)
# ---------------------------------------------------------------------------

METHODS = ("sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule")


def run_method(method: str, family: str, top: np.ndarray, side: np.ndarray,
               window: dict, height_m: float, case: dict, bearing_rad: float) -> np.ndarray:
    fp_len = case["footprint"]["length_m"]
    fp_wid = case["footprint"]["width_m"]
    if method == "sppa_mvfit":
        fit = fit_top_only(family, top, height_m, window["nom"][2])
        return mv.voxelize_actor(fit["actor"], EVAL_RES)
    if method == "generic_mvfit":
        generic_height_m = graph_extent_units("generic")[2] * FAMILY_SCALE_M_PER_UNIT[family]
        fit = fit_top_only("generic", top, height_m, generic_height_m)
        return mv.voxelize_actor(fit["actor"], EVAL_RES)
    if method == "obb":
        return voxelize_oriented_box(window, (0.0, 0.0), (fp_len, fp_wid), 0.0, 0.0, height_m)
    if method == "aabb":
        pts = case["footprint"]["points_ned_m"]
        ns = np.array([p["north_m"] for p in pts])
        es = np.array([p["east_m"] for p in pts])
        cn_rel = 0.5 * (ns.min() + ns.max()) - case["footprint"]["center_north_m"]
        ce_rel = 0.5 * (es.min() + es.max()) - case["footprint"]["center_east_m"]
        cx = cn_rel * math.cos(bearing_rad) + ce_rel * math.sin(bearing_rad)
        cy = -cn_rel * math.sin(bearing_rad) + ce_rel * math.cos(bearing_rad)
        return voxelize_oriented_box(window, (cx, cy), (float(ns.max() - ns.min()), float(es.max() - es.min())),
                                     -bearing_rad, 0.0, height_m)
    if method == "visual_hull":
        occ, _ = mv.baseline_occupancy("nonsemantic_visual_hull", top, side, EVAL_RES)
        return occ
    if method == "capsule":
        occ, _ = mv.baseline_occupancy("capsule", top, side, EVAL_RES)
        return occ
    raise ValueError(method)


def evaluate_case(case: dict, gt_match: dict | None) -> list[dict]:
    family = case["family"]
    fp = case["footprint"]
    height_m = case["height_m"]
    bearing = math.radians(fp["orientation_deg_axial"])  # compass bearing of major axis

    mv.GRAPHS = scaled_graphs_for_family(family)  # in-memory only
    window = case_window(fp["length_m"], fp["width_m"], height_m, family)
    mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}  # in-memory only
    top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], height_m)

    gt_mask = gt_footprint_mask(window, gt_match, case, bearing) if gt_match else None
    gt_centroid_z = (gt_match["height_msl"] + FAMILY_NOMINAL_HEIGHT_M[CLASS_TO_FAMILY[gt_match["cls"]]] / 2.0
                     if gt_match else None)

    rows = []
    for method in METHODS:
        t0 = time.perf_counter()
        occ = run_method(method, family, top, side, window, height_m, case, bearing)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        row = {
            "case_id": case["case_id"], "frame": case["frame"], "method": method,
            "det_class": case["det_class"], "family_token": family,
            "confidence": case["confidence"], "base_distance_m": case["base_distance_m"],
            "obs_length_m": fp["length_m"], "obs_width_m": fp["width_m"], "obs_height_m": height_m,
            "latency_ms": latency_ms,
            "gt_actor": gt_match["label"] if gt_match else None,
            "gt_class": gt_match["cls"] if gt_match else None,
            "token_correct": (gt_match is not None and gt_match["cls"] == case["det_class"]),
            "matched": gt_match is not None,
            "loc_err_3d_m": None, "loc_err_horiz_m": None, "footprint_iou": None,
        }
        centroid = occupancy_centroid_window(occ, window)
        if gt_match and centroid is not None:
            cb, sb = math.cos(bearing), math.sin(bearing)
            cn = (case["drone_north_m"] + fp["center_north_m"]) + centroid[0] * cb - centroid[1] * sb
            ce = (case["drone_east_m"] + fp["center_east_m"]) + centroid[0] * sb + centroid[1] * cb
            horiz = math.hypot(cn - gt_match["north_m"], ce - gt_match["east_m"])
            cz_abs = case["ground_msl_m"] + centroid[2]
            vert = cz_abs - gt_centroid_z
            row["loc_err_horiz_m"] = horiz
            row["loc_err_3d_m"] = math.hypot(horiz, vert)
            proxy_fp = occ.any(axis=2)
            union = np.count_nonzero(proxy_fp | gt_mask)
            row["footprint_iou"] = float(np.count_nonzero(proxy_fp & gt_mask) / union) if union else None
        row["reproj_iou"] = reprojection_iou(occ, window, case, bearing)
        rows.append(row)

    # Correct-token refit arm: only where the detector token disagrees with GT.
    if gt_match is not None and gt_match["cls"] != case["det_class"]:
        correct_family = CLASS_TO_FAMILY[gt_match["cls"]]
        mv.GRAPHS = scaled_graphs_for_family(correct_family)
        window_c = case_window(fp["length_m"], fp["width_m"], height_m, correct_family)
        mv.WORLD = {"x": window_c["x"], "y": window_c["y"], "z": window_c["z"]}
        top_c, side_c = rasterize_masks(window_c, fp["length_m"], fp["width_m"], height_m)
        gt_mask_c = gt_footprint_mask(window_c, gt_match, case, bearing)
        t0 = time.perf_counter()
        occ = run_method("sppa_mvfit", correct_family, top_c, side_c, window_c, height_m, case, bearing)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        proxy_fp = occ.any(axis=2)
        union = np.count_nonzero(proxy_fp | gt_mask_c)
        rows.append({
            "case_id": case["case_id"], "frame": case["frame"], "method": "sppa_mvfit_correct_token",
            "det_class": case["det_class"], "family_token": correct_family,
            "confidence": case["confidence"], "base_distance_m": case["base_distance_m"],
            "obs_length_m": fp["length_m"], "obs_width_m": fp["width_m"], "obs_height_m": height_m,
            "latency_ms": latency_ms,
            "gt_actor": gt_match["label"], "gt_class": gt_match["cls"], "token_correct": True,
            "matched": True,
            "loc_err_3d_m": None, "loc_err_horiz_m": None,
            "footprint_iou": float(np.count_nonzero(proxy_fp & gt_mask_c) / union) if union else None,
            "reproj_iou": reprojection_iou(occ, window_c, case, bearing),
        })
    return rows


def main() -> int:
    cases, exclusions = iter_cases()
    gt_actors = load_gt_static()
    print(f"cases={len(cases)} exclusions={exclusions} gt_static={len(gt_actors)}")

    results_path = OUT / "results.jsonl"
    t_start = time.perf_counter()
    n_rows = 0
    with results_path.open("w", encoding="utf-8") as handle:
        for i, case in enumerate(cases):
            gt_match = match_gt(case, gt_actors)
            for row in evaluate_case(case, gt_match):
                handle.write(json.dumps(row) + "\n")
                n_rows += 1
            if (i + 1) % 200 == 0:
                print(f"  {i + 1}/{len(cases)} cases ({time.perf_counter() - t_start:.0f}s)")
    seconds = time.perf_counter() - t_start
    print(f"wrote {n_rows} rows -> {results_path} ({seconds:.0f}s)")

    summary = summarize(results_path, exclusions, gt_actors, seconds)
    (OUT / "e7_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["headline"], indent=2))
    return 0


def summarize(results_path: Path, exclusions: dict, gt_actors: list[dict], seconds: float) -> dict:
    rows = [json.loads(line) for line in results_path.open("r", encoding="utf-8")]

    def stats(values: list[float]) -> dict:
        arr = np.asarray(values, dtype=float)
        return {"n": int(arr.size), "median": float(np.median(arr)),
                "p25": float(np.percentile(arr, 25)), "p75": float(np.percentile(arr, 75)),
                "mean": float(arr.mean())}

    per_method: dict[str, dict] = {}
    for method in METHODS:
        sel = [r for r in rows if r["method"] == method]
        matched = [r for r in sel if r["matched"]]
        per_method[method] = {
            "n_cases": len(sel),
            "n_matched": len(matched),
            "loc_err_3d_m": stats([r["loc_err_3d_m"] for r in matched if r["loc_err_3d_m"] is not None]),
            "loc_err_horiz_m": stats([r["loc_err_horiz_m"] for r in matched if r["loc_err_horiz_m"] is not None]),
            "footprint_iou": stats([r["footprint_iou"] for r in matched if r["footprint_iou"] is not None]),
            "reproj_iou": stats([r["reproj_iou"] for r in sel]),
            "latency_ms": stats([r["latency_ms"] for r in sel]),
        }
        for cls in ("tower", "cow", "biker"):
            cls_sel = [r for r in sel if r["det_class"] == cls]
            cls_matched = [r for r in cls_sel if r["matched"]]
            per_method[method][f"class_{cls}"] = {
                "n_cases": len(cls_sel), "n_matched": len(cls_matched),
                "loc_err_3d_m": stats([r["loc_err_3d_m"] for r in cls_matched if r["loc_err_3d_m"] is not None]) if cls_matched else None,
                "footprint_iou": stats([r["footprint_iou"] for r in cls_matched if r["footprint_iou"] is not None]) if cls_matched else None,
                "reproj_iou": stats([r["reproj_iou"] for r in cls_sel]) if cls_sel else None,
            }

    wrong = [r for r in rows if r["method"] == "sppa_mvfit" and r["matched"] and not r["token_correct"]]
    refit = {r["case_id"]: r for r in rows if r["method"] == "sppa_mvfit_correct_token"}
    token_arm = {
        "n_wrong_token_matched": len(wrong),
        "real_token": {
            "reproj_iou": stats([r["reproj_iou"] for r in wrong]) if wrong else None,
            "footprint_iou": stats([r["footprint_iou"] for r in wrong if r["footprint_iou"] is not None]) if wrong else None,
        },
        "correct_token": {
            "reproj_iou": stats([refit[r["case_id"]]["reproj_iou"] for r in wrong if r["case_id"] in refit]) if wrong else None,
            "footprint_iou": stats([refit[r["case_id"]]["footprint_iou"] for r in wrong
                                    if r["case_id"] in refit and refit[r["case_id"]]["footprint_iou"] is not None]) if wrong else None,
        },
    }

    case_rows = [r for r in rows if r["method"] == "sppa_mvfit"]
    headline = {
        "label": EXPLORATORY_LABEL,
        "n_cases_total": len(case_rows),
        "n_cases_matched_gt": sum(1 for r in case_rows if r["matched"]),
        "per_class_cases": {cls: sum(1 for r in case_rows if r["det_class"] == cls) for cls in ("tower", "cow", "biker")},
        "wrong_token_matched_cases": token_arm["n_wrong_token_matched"],
        "sppa_reproj_iou_median": per_method["sppa_mvfit"]["reproj_iou"]["median"],
        "generic_reproj_iou_median": per_method["generic_mvfit"]["reproj_iou"]["median"],
    }
    return {
        "label": EXPLORATORY_LABEL,
        "benchmark": "E7 Real Stream Wave",
        "stream": "pipeline/logs/zero_trust/20260620_084932 (1394 saved frames, 2788 vision_frame events)",
        "exclusions": exclusions,
        "gt_static_actors": [{"label": a["label"], "cls": a["cls"]} for a in gt_actors],
        "fit_budget": {"candidates": 31, "parameters": 5, "bounds": "frozen (sealed)", "mode": "top-only + height anchor"},
        "wallclock_seconds": seconds,
        "headline": headline,
        "per_method": per_method,
        "token_correction_arm": token_arm,
    }


if __name__ == "__main__":
    raise SystemExit(main())
