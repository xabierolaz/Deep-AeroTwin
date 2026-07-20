"""E11 "Oblique Twin Wave" - step 2: fits + 3D voxel IoU vs exact GT.

Per detection (detections.jsonl x manifest):
  * one observation (E7 construction, E11 view geometry) - shape only;
  * per-case metric window LOCKED on the tower's exact GT pivot (positions
    are never estimated; locked invariant asserted);
  * SPPA-MVFit / Generic-MVFit (production top-only + height anchor) and the
    E7 box/voxel baselines fitted in that window;
  * exact-GT solid voxelization (welded OBJ at the tower's exact pose) in the
    same window -> per-method 3D voxel IoU.

Resumable: case_ids already present in results.jsonl are skipped.

Run:  python run_e11_analysis.py
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from e11_common import (
    CAM11, CLASS_TO_FAMILY, E11_ROOT, EVAL_RES, EXPLORATORY_LABEL,
    FAMILY_SCALE_M_PER_UNIT, METHODS, build_observation_e11, case_window,
    cell_centers, enlarge_window_to_contain, graph_extent_units, load_gt_geometry,
    load_manifest, mesh_in_window, mv, rasterize_masks, run_method,
    scaled_graphs_for_family, tel_from_manifest, voxel_iou, voxelize_mesh_solid,
)
from run_e7_real_stream import fit_top_only  # noqa: E402  (E7 production mode)

DETECTIONS = E11_ROOT / "detections.jsonl"
RESULTS = E11_ROOT / "results.jsonl"


def evaluate_case(det: dict, frame: dict, gt_actors: dict) -> list[dict]:
    """Fit all methods at the LOCKED GT position; 3D voxel IoU vs exact GT."""
    family = CLASS_TO_FAMILY[det["class"]]
    tel = tel_from_manifest(frame)
    obs = build_observation_e11(det["bbox"], tel)
    if obs is None:
        return []
    fp = obs["footprint"]
    height_m = obs["height_m"]
    bearing = math.radians(fp["orientation_deg_axial"])

    # Locked window: E7 sizing, centered on the GT pivot (asserted invariant).
    mv.GRAPHS = scaled_graphs_for_family(family)  # in-memory only
    window0 = case_window(fp["length_m"], fp["width_m"], height_m, family)
    assert abs(window0["x"][0] + window0["x"][1]) < 1e-12
    assert abs(window0["y"][0] + window0["y"][1]) < 1e-12
    verts_w, faces = mesh_in_window(frame["tower_id"], bearing, gt_actors)
    window = enlarge_window_to_contain(window0, verts_w)
    mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}  # in-memory only
    top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], height_m)

    gt_surface, gt_solid = voxelize_mesh_solid(verts_w, faces, window, EVAL_RES)
    n_surface, n_solid = int(gt_surface.sum()), int(gt_solid.sum())
    assert n_solid > 0, f"empty GT voxelization for {det['case_id']}"

    case = {"footprint": fp, "bbox": obs["bbox"]}  # what run_method needs
    base = {
        "case_id": det["case_id"], "frame_id": det["frame_id"],
        "tower_id": frame["tower_id"], "ring": frame["ring"],
        "azimuth_deg": float(frame["azimuth_deg"]),
        "det_index": det["det_index"], "det_class": det["class"],
        "family_token": family, "token_correct": det["class"] == "tower",
        "confidence": det["confidence"],
        "obs_length_m": fp["length_m"], "obs_width_m": fp["width_m"],
        "obs_height_m": height_m, "base_distance_m": obs["base_distance_m"],
        "bearing_deg": fp["orientation_deg_axial"],
        "window": {a: list(window[a]) for a in "xyz"},
        "gt_voxels_surface": n_surface, "gt_voxels_solid": n_solid,
        "gt_fill_ratio": n_solid / max(1, int(np.prod(gt_solid.shape))),
    }

    rows = []
    for method in METHODS:
        t0 = time.perf_counter()
        extra: dict = {}
        if method == "sppa_mvfit":
            # Identical two lines as E7 run_method("sppa_mvfit"), keeping theta.
            fit = fit_top_only(family, top, height_m, window["nom"][2])
            occ = mv.voxelize_actor(fit["actor"], EVAL_RES)
            extra["theta"] = [float(v) for v in fit["theta"]]
        elif method == "generic_mvfit":
            generic_height_m = graph_extent_units("generic")[2] * FAMILY_SCALE_M_PER_UNIT[family]
            fit = fit_top_only("generic", top, height_m, generic_height_m)
            occ = mv.voxelize_actor(fit["actor"], EVAL_RES)
            extra["theta"] = [float(v) for v in fit["theta"]]
        else:
            occ = run_method(method, family, top, side, window, height_m, case, bearing)
            if method == "obb":
                extra["boxes"] = [{"center": [0.0, 0.0, height_m / 2],
                                   "size": [fp["length_m"], fp["width_m"], height_m], "yaw": 0.0}]
            elif method == "aabb":
                pts = fp["points_ned_m"]
                ns = np.array([p["north_m"] for p in pts])
                es = np.array([p["east_m"] for p in pts])
                cn_rel = 0.5 * (ns.min() + ns.max()) - fp["center_north_m"]
                ce_rel = 0.5 * (es.min() + es.max()) - fp["center_east_m"]
                cx = cn_rel * math.cos(bearing) + ce_rel * math.sin(bearing)
                cy = -cn_rel * math.sin(bearing) + ce_rel * math.cos(bearing)
                extra["boxes"] = [{"center": [float(cx), float(cy), height_m / 2],
                                   "size": [float(ns.max() - ns.min()), float(es.max() - es.min()), height_m],
                                   "yaw": -bearing}]
        latency_ms = (time.perf_counter() - t0) * 1000.0
        rows.append({**base, "method": method, "iou_3d": voxel_iou(occ, gt_solid),
                     "latency_ms": latency_ms, **extra})
    return rows


def main() -> int:
    manifest = load_manifest()
    gt_actors = load_gt_geometry()
    dets = [json.loads(line) for line in DETECTIONS.open("r", encoding="utf-8")]

    done: set[str] = set()
    if RESULTS.exists():
        with RESULTS.open("r", encoding="utf-8") as handle:
            for line in handle:
                done.add(json.loads(line)["case_id"])
        print(f"resume: {len(done)} case_ids already in results.jsonl")

    exclusions = {"frame_not_in_manifest": 0, "class_not_mapped": 0, "observation_failed": 0}
    det_counts: dict[str, int] = {}
    n_rows = 0
    t_start = time.perf_counter()
    n_total = len(dets)
    with RESULTS.open("a", encoding="utf-8") as handle:
        for i, det in enumerate(dets):
            det_counts[det["class"]] = det_counts.get(det["class"], 0) + 1
            frame = manifest.get(det["frame_id"])
            assert frame is not None, f"detection without manifest frame: {det['frame_id']}"
            det["case_id"] = f"{det['frame_id']}::d{det['det_index']}"
            if det["case_id"] in done:
                continue
            if det["class"] not in CLASS_TO_FAMILY:
                exclusions["class_not_mapped"] += 1
                continue
            rows = evaluate_case(det, frame, gt_actors)
            if not rows:
                exclusions["observation_failed"] += 1
                continue
            for row in rows:
                handle.write(json.dumps(row) + "\n")
                n_rows += 1
            handle.flush()
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{n_total} dets, {n_rows} rows ({time.perf_counter() - t_start:.0f}s)")

    seconds = time.perf_counter() - t_start
    print(f"wrote {n_rows} rows -> {RESULTS} ({seconds:.0f}s)")
    print(f"detections per class: {det_counts}")
    print(f"exclusions: {exclusions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
