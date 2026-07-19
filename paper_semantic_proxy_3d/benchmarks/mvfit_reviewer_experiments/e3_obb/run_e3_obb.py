"""E3 - Oriented bounding box (OBB) baseline (exploratory post-hoc).

Construction (documented before measurement):
  1. Top mask -> largest connected component (same ndimage.label scheme as the
     sealed method) -> occupied pixel centers in WORLD (x, y) meters.
  2. cv2.minAreaRect on those world points; cv2.boxPoints gives the four
     corners, so the box axes are the two adjacent edge vectors -- no
     angle-convention assumptions. Fallback to the axis-aligned extent when
     fewer than 3 points exist.
  3. Gap-midpoint refinement per axis: the true boundary sits between the
     extreme occupied center projection and the nearest unoccupied center
     projection measured inside the slab of the opposite axis; we take the
     midpoint (minimax estimator). This removes the center/size bias of
     minAreaRect on quantized masks (measured: ~0.03 m center bias costs
     ~0.05 IoU). Fallback: +half projected cell when no candidate exists.
  4. z center/extent from the SIDE mask largest component z-range (world z),
     i.e. the box is a right prism: rotated rectangle in x-y extruded over z.
  5. Analytic voxelization on the same 64^3 grid and world box as the sealed
     evaluation: voxel inside iff |d.e1| <= |e1|/2, |d.e2| <= |e2|/2,
     |dz| <= size_z/2.

Self-check (run first, aborts on failure): a synthetic box with known yaw is
voxelized, projected to a top mask, reconstructed by this same code, and the
3D IoU between input and reconstruction must be >= 0.90.

Comparators come from the sealed results/test/raw_metrics.csv (NOT
recomputed): Axis-aligned box 0.248, Visual hull 0.522, SPPA-MVFit 0.557.
n = 240 actors, clean condition.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, GtCache, bootstrap_paired, clean_view_masks, f3, load_masks,
    load_public_cases, load_sealed_clean_ious, mv, pooled_mean, voxel_iou,
    write_json, write_text, EXPLORATORY_LABEL,
)

OUT = EXPERIMENTS_ROOT / "e3_obb"
WORLD_X = (-4.8, 4.8)
WORLD_Y = (-3.2, 3.2)
WORLD_Z = (0.0, 6.4)


def top_points_world(top_mask: np.ndarray) -> np.ndarray:
    """World (x, y) coordinates of the occupied pixel centers of the largest
    connected component of the top mask. Mask axis 0 = world x, axis 1 = y."""
    component = mv._largest_component(top_mask)
    indices = np.argwhere(component)
    if not len(indices):
        return np.zeros((0, 2), dtype=np.float64)
    res = top_mask.shape[0]
    xs = WORLD_X[0] + (indices[:, 0] + 0.5) * (WORLD_X[1] - WORLD_X[0]) / res
    ys = WORLD_Y[0] + (indices[:, 1] + 0.5) * (WORLD_Y[1] - WORLD_Y[0]) / res
    return np.stack([xs, ys], axis=1)


def side_z_extent(side_mask: np.ndarray) -> tuple[float, float] | None:
    component = mv._largest_component(side_mask)  # axis 0 = x, axis 1 = z
    indices = np.argwhere(component)
    if not len(indices):
        return None
    res = side_mask.shape[0]
    step_z = (WORLD_Z[1] - WORLD_Z[0]) / res
    z0, z1 = int(indices[:, 1].min()), int(indices[:, 1].max()) + 1
    return WORLD_Z[0] + z0 * step_z, WORLD_Z[0] + z1 * step_z


def _refine_supports(points: np.ndarray, center: np.ndarray, e: np.ndarray, other: np.ndarray,
                     resolution: int) -> tuple[np.ndarray, np.ndarray]:
    """Gap-midpoint refinement of one rect axis.

    minAreaRect bounds the occupied pixel CENTERS, so both the axis length and
    the center are biased by the (asymmetric) staircase gaps between the
    extreme occupied centers and the true silhouette boundary. For a clean
    rect silhouette the boundary along axis u lies in (max occupied proj,
    min unoccupied proj] when unoccupied candidates are restricted to the slab
    spanning the other axis (otherwise corner regions would falsely constrain
    the face). We take the gap midpoint -- the minimax estimator. Falls back
    to +half projected cell when no candidate exists.
    """
    n = float(np.hypot(e[0], e[1]))
    u = e / n
    no = float(np.hypot(other[0], other[1]))
    uo = other / no
    cell_x = (WORLD_X[1] - WORLD_X[0]) / resolution
    cell_y = (WORLD_Y[1] - WORLD_Y[0]) / resolution
    proj = cell_x * abs(u[0]) + cell_y * abs(u[1])
    proj_o = cell_x * abs(uo[0]) + cell_y * abs(uo[1])
    occ_u = points @ u
    occ_o = points @ uo
    c_o = 0.5 * (occ_o.min() + occ_o.max())
    half_o = 0.5 * (occ_o.max() - occ_o.min()) + 0.5 * proj_o
    xs = WORLD_X[0] + (np.arange(resolution) + 0.5) * cell_x
    ys = WORLD_Y[0] + (np.arange(resolution) + 0.5) * cell_y
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    all_u = (gx * u[0] + gy * u[1]).ravel()
    all_o = (gx * uo[0] + gy * uo[1]).ravel()
    in_slab = np.abs(all_o - c_o) <= half_o
    slab_u = all_u[in_slab]
    occ_set_max, occ_set_min = occ_u.max(), occ_u.min()
    above = slab_u[slab_u > occ_set_max + 1e-12]
    below = slab_u[slab_u < occ_set_min - 1e-12]
    b_plus = 0.5 * (occ_set_max + above.min()) if len(above) else occ_set_max + 0.5 * proj
    b_minus = 0.5 * (occ_set_min + below.max()) if len(below) else occ_set_min - 0.5 * proj
    new_center_along = 0.5 * (b_plus + b_minus)
    new_length = max(b_plus - b_minus, 1e-4)
    delta = new_center_along - 0.5 * (occ_set_max + occ_set_min)
    return center + u * delta, u * new_length


def obb_from_masks(top_mask: np.ndarray, side_mask: np.ndarray) -> dict | None:
    points = top_points_world(top_mask)
    z_extent = side_z_extent(side_mask)
    if z_extent is None or not len(points):
        return None
    z_low, z_high = z_extent
    resolution = top_mask.shape[0]
    cell_x = (WORLD_X[1] - WORLD_X[0]) / resolution
    cell_y = (WORLD_Y[1] - WORLD_Y[0]) / resolution
    if len(points) < 3:  # degenerate: axis-aligned fallback over full cells
        cx, cy = points[:, 0].mean(), points[:, 1].mean()
        e1 = np.array([points[:, 0].ptp() + cell_x, 0.0])
        e2 = np.array([0.0, points[:, 1].ptp() + cell_y])
    else:
        rect = cv2.minAreaRect(points.astype(np.float32))
        corners = cv2.boxPoints(rect).astype(np.float64)  # 4 consecutive corners
        center = corners.mean(axis=0)
        e1 = corners[1] - corners[0]
        e2 = corners[3] - corners[0]
        if min(float(np.hypot(*e1)), float(np.hypot(*e2))) < 1e-9:
            return None
        center, e1 = _refine_supports(points, center, e1, e2, resolution)
        center, e2 = _refine_supports(points, center, e2, e1, resolution)
        cx, cy = center
    return {
        "center": [float(cx), float(cy), 0.5 * (z_low + z_high)],
        "e1": e1, "e2": e2,
        "size_z": max(z_high - z_low, 1e-4),
        "yaw_deg": float(np.degrees(np.arctan2(e1[1], e1[0]))),
    }


def voxelize_obb(obb: dict, resolution: int = 64) -> np.ndarray:
    xs = mv._cell_centers("x", resolution)
    ys = mv._cell_centers("y", resolution)
    zs = mv._cell_centers("z", resolution)
    x, y, z = np.meshgrid(xs, ys, zs, indexing="ij", sparse=True)
    cx, cy, cz = obb["center"]
    dx, dy, dz = x - cx, y - cy, z - cz
    e1, e2 = obb["e1"], obb["e2"]
    n1 = float(np.hypot(e1[0], e1[1]))
    n2 = float(np.hypot(e2[0], e2[1]))
    if n1 < 1e-9 or n2 < 1e-9:
        return np.zeros((resolution, resolution, resolution), dtype=bool)
    a = (dx * e1[0] + dy * e1[1]) / n1  # signed distance along axis 1
    b = (dx * e2[0] + dy * e2[1]) / n2  # signed distance along axis 2
    return (np.abs(a) <= n1 / 2) & (np.abs(b) <= n2 / 2) & (np.abs(dz) <= obb["size_z"] / 2)


def self_check() -> float:
    """Known-yaw box round trip; returns reconstruction 3D IoU."""
    yaw = np.radians(33.0)
    center = np.array([0.4, -0.3, 1.8])
    half = np.array([1.5, 0.6, 0.9])
    c, s = np.cos(yaw), np.sin(yaw)
    res = 64
    xs, ys, zs = (mv._cell_centers(ax, res) for ax in ("x", "y", "z"))
    x, y, z = np.meshgrid(xs, ys, zs, indexing="ij", sparse=True)
    dx, dy, dz = x - center[0], y - center[1], z - center[2]
    u = c * dx + s * dy
    v = -s * dx + c * dy
    gt_box = (np.abs(u) <= half[0]) & (np.abs(v) <= half[1]) & (np.abs(dz) <= half[2])
    top_mask = np.any(gt_box, axis=2)
    # side mask consistent with this box: project onto x-z
    side_mask = np.any(gt_box, axis=1)
    obb = obb_from_masks(top_mask, side_mask)
    recon = voxelize_obb(obb, res)
    return voxel_iou(gt_box, recon)


def main() -> int:
    check_iou = self_check()
    if check_iou < 0.90:
        raise RuntimeError(f"OBB self-check failed: 3D IoU {check_iou:.3f}")

    cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()

    obb_iou: dict[str, float] = {}
    ms: list[float] = []
    for case_index, case in enumerate(cases):
        top, side = clean_view_masks(masks, case_index)
        start = time.perf_counter()
        obb = obb_from_masks(top, side)
        occupancy = np.zeros((64, 64, 64), dtype=bool) if obb is None else voxelize_obb(obb, 64)
        ms.append((time.perf_counter() - start) * 1000.0)
        obb_iou[case["case_id"]] = voxel_iou(gt.voxels(case["case_id"]), occupancy)

    aabb_iou = {c["case_id"]: sealed[(c["case_id"], "bbox")] for c in cases}
    hull_iou = {c["case_id"]: sealed[(c["case_id"], "nonsemantic_visual_hull")] for c in cases}
    sppa_iou = {c["case_id"]: sealed[(c["case_id"], "sppa_mvfit")] for c in cases}

    pooled = {
        "obb": pooled_mean(list(obb_iou.values())),
        "aabb_sealed": pooled_mean(list(aabb_iou.values())),
        "visual_hull_sealed": pooled_mean(list(hull_iou.values())),
        "sppa_mvfit_sealed": pooled_mean(list(sppa_iou.values())),
    }
    paired = {
        "obb_minus_aabb": bootstrap_paired(cases, {cid: obb_iou[cid] - aabb_iou[cid] for cid in obb_iou}),
        "obb_minus_visual_hull": bootstrap_paired(cases, {cid: obb_iou[cid] - hull_iou[cid] for cid in obb_iou}),
        "sppa_minus_obb": bootstrap_paired(cases, {cid: sppa_iou[cid] - obb_iou[cid] for cid in obb_iou}),
    }
    per_stratum: dict[str, dict] = {}
    for stratum in ("csg_id", "implicit_ood"):
        ids = [c["case_id"] for c in cases if c["stratum"] == stratum]
        per_stratum[stratum] = {
            "n": len(ids),
            "obb": pooled_mean([obb_iou[i] for i in ids]),
            "aabb": pooled_mean([aabb_iou[i] for i in ids]),
            "visual_hull": pooled_mean([hull_iou[i] for i in ids]),
            "sppa_mvfit": pooled_mean([sppa_iou[i] for i in ids]),
        }

    lines = [
        "\\begin{tabular}{@{}lrrr@{}}",
        "\\toprule",
        "Method & Mean IoU & $\\Delta$ vs OBB & CI95 \\\\",
        "\\midrule",
        f"Axis-aligned box (sealed) & {f3(pooled['aabb_sealed'])} & "
        f"{f3(-paired['obb_minus_aabb']['mean_difference'])} & "
        f"[{f3(-paired['obb_minus_aabb']['ci95_high'])}, {f3(-paired['obb_minus_aabb']['ci95_low'])}] \\\\",
        f"OBB (this work) & {f3(pooled['obb'])} & --- & --- \\\\",
        f"Visual hull (sealed) & {f3(pooled['visual_hull_sealed'])} & "
        f"{f3(-paired['obb_minus_visual_hull']['mean_difference'])} & "
        f"[{f3(-paired['obb_minus_visual_hull']['ci95_high'])}, {f3(-paired['obb_minus_visual_hull']['ci95_low'])}] \\\\",
        f"SPPA-MVFit (sealed) & {f3(pooled['sppa_mvfit_sealed'])} & "
        f"{f3(paired['sppa_minus_obb']['mean_difference'])} & "
        f"[{f3(paired['sppa_minus_obb']['ci95_low'])}, {f3(paired['sppa_minus_obb']['ci95_high'])}] \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "obb_baseline_table.tex", "\n".join(lines))

    payload = {
        "experiment": "E3 oriented bounding box baseline",
        "label": EXPLORATORY_LABEL,
        "n_actors": len(cases),
        "condition": "clean",
        "metric": "voxel_iou_64cubed",
        "self_check": {"known_yaw_box_reconstruction_iou": check_iou, "threshold": 0.90},
        "construction": {
            "xy": "cv2.minAreaRect on largest top-mask component in world meters; axes from cv2.boxPoints edges; gap-midpoint support refinement per axis",
            "z": "largest side-mask component z range (right prism extrusion)",
            "voxelization": "analytic, sealed 64^3 grid and world box",
            "degenerate_fallback": "axis-aligned extent when < 3 component pixels",
        },
        "pooled_means": pooled,
        "median_inference_ms": float(np.median(np.asarray(ms))),
        "p95_inference_ms": float(np.quantile(np.asarray(ms), 0.95)),
        "paired_bootstrap": paired,
        "per_stratum": per_stratum,
        "protocol": {"bootstrap_resamples": 10000, "bootstrap_seed": 77157},
    }
    write_json(OUT / "obb_baseline.json", payload)

    print(f"self-check IoU: {check_iou:.3f}")
    print(f"OBB={pooled['obb']:.4f} AABB={pooled['aabb_sealed']:.4f} hull={pooled['visual_hull_sealed']:.4f} sppa={pooled['sppa_mvfit_sealed']:.4f}")
    for name, diff in paired.items():
        print(f"{name}: {diff['mean_difference']:.4f} [{diff['ci95_low']:.4f}, {diff['ci95_high']:.4f}] p={diff['null_centered_two_sided_p']:.4f}")
    print(f"median {np.median(np.asarray(ms)):.2f} ms/case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
