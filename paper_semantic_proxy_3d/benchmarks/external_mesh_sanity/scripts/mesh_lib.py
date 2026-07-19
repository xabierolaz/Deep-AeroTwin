# external sanity check (exploratory, post-hoc)
"""Mesh loading, normalization, silhouette rasterization and voxelization.

Benchmark conventions replicated from the sealed package (imported, not modified):
- world box x[-4.8,4.8] y[-3.2,3.2] z[0,6.4] m
- cell centers: linspace(low, high, res, endpoint=False) + (high-low)/(2*res)
- top mask indexed [x, y]; side mask indexed [x, z]; voxels indexed [x, y, z]
- masks rendered at 256 then downsampled to 96 with the sealed _downsample_any.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (sets sys.path for the sealed package)

from source.source_generators import _downsample_any  # sealed, imported only

WORLD = common.WORLD
RES_MASK_SRC = 256
RES_MASK = 96
RES_VOX = 64
MAX_FACES = 12000


def cell_centers(axis: str, resolution: int) -> np.ndarray:
    low, high = WORLD[axis]
    return np.linspace(low, high, resolution, endpoint=False) + (high - low) / (2 * resolution)


# ------------------------- loading & cleaning -------------------------

def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="scene")
    if isinstance(loaded, trimesh.Scene):
        if len(loaded.geometry) == 0:
            raise ValueError("empty scene")
        mesh = loaded.to_mesh()
    else:
        mesh = loaded
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"cannot convert to Trimesh: {type(mesh)}")
    mesh = mesh.copy()
    mesh.merge_vertices()
    mesh.remove_degenerate_faces()
    mesh.remove_unreferenced_vertices()
    if len(mesh.faces) > MAX_FACES:
        mesh = mesh.simplify_quadric_decimation(face_count=MAX_FACES)
        mesh.remove_unreferenced_vertices()
    if len(mesh.faces) == 0:
        raise ValueError("no faces after cleaning")
    return mesh


# ------------------------- orientation -------------------------

def rot_about_x(deg: float) -> np.ndarray:
    a = np.deg2rad(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def rot_about_z(deg: float) -> np.ndarray:
    a = np.deg2rad(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def pca_yaw_rotation(mesh: trimesh.Trimesh) -> tuple[np.ndarray, float]:
    """Rotate about +z so the first horizontal PCA axis aligns with +x."""
    pts = mesh.vertices[:, :2]
    pts = pts - pts.mean(axis=0, keepdims=True)
    cov = np.cov(pts.T)
    vals, vecs = np.linalg.eigh(cov)
    v = vecs[:, int(np.argmax(vals))]
    theta = np.arctan2(v[1], v[0])
    return rot_about_z(-np.rad2deg(theta)), float(np.rad2deg(theta))


def apply_orientation(mesh: trimesh.Trimesh, base_rot: np.ndarray, use_pca_yaw: bool, overrides: list[float] | None) -> tuple[trimesh.Trimesh, dict]:
    """base_rot first; then optional extra yaw rotations (degrees about z) from overrides;
    then PCA yaw unless disabled. Returns (mesh, info)."""
    info: dict = {"base_rot": base_rot.tolist(), "override_yaw_deg": overrides or [], "pca_yaw_deg": None}
    m = mesh.copy()
    m.apply_transform(np.vstack([np.hstack([base_rot, np.zeros((3, 1))]), [0, 0, 0, 1]]))
    for deg in overrides or []:
        m.apply_transform(np.vstack([np.hstack([rot_about_z(deg), np.zeros((3, 1))]), [0, 0, 0, 1]]))
    if use_pca_yaw:
        r, deg = pca_yaw_rotation(m)
        m.apply_transform(np.vstack([np.hstack([r, np.zeros((3, 1))]), [0, 0, 0, 1]]))
        info["pca_yaw_deg"] = deg
    return m, info


# ------------------------- scale & placement -------------------------

def normalize_scale_place(mesh: trimesh.Trimesh, ref_axis: str, target_size: float, margin: float = 0.2) -> tuple[trimesh.Trimesh, dict]:
    extents = mesh.extents.astype(float)
    axis_idx = {"x": 0, "y": 1, "z": 2}[ref_axis]
    scale = target_size / max(extents[axis_idx], 1e-9)
    world_span = np.array([WORLD["x"][1] - WORLD["x"][0] - margin, WORLD["y"][1] - WORLD["y"][0] - margin, WORLD["z"][1] - WORLD["z"][0] - margin])
    clamp = float(np.min(world_span / np.maximum(extents * scale, 1e-9)))
    clamped = clamp < 1.0
    if clamped:
        scale *= clamp
    m = mesh.copy()
    m.apply_scale(scale)
    # center x,y at 0; bottom at z=0
    bounds = m.bounds
    center_xy = (bounds[0, :2] + bounds[1, :2]) / 2
    m.apply_translation([-center_xy[0], -center_xy[1], -bounds[0, 2]])
    final_extents = m.extents.astype(float)
    info = {
        "ref_axis": ref_axis,
        "target_size_m": target_size,
        "scale": float(scale),
        "clamped_to_world": bool(clamped),
        "final_extents_m": [float(v) for v in final_extents],
        "raw_extents": [float(v) for v in extents],
    }
    return m, info


# ------------------------- silhouette rasterization (no rays) -------------------------

def _rasterize_view(points3d: np.ndarray, faces: np.ndarray, axis_u: str, axis_v: str, resolution: int) -> np.ndarray:
    """Union of projected triangles sampled at cell centers -> silhouette mask [u, v]."""
    idx = {"x": 0, "y": 1, "z": 2}
    iu, iv = idx[axis_u], idx[axis_v]
    us = cell_centers(axis_u, resolution)
    vs = cell_centers(axis_v, resolution)
    low_u, high_u = WORLD[axis_u]
    low_v, high_v = WORLD[axis_v]
    step_u = (high_u - low_u) / resolution
    step_v = (high_v - low_v) / resolution
    mask = np.zeros((resolution, resolution), dtype=bool)
    tri_u = points3d[:, iu][faces]  # (F,3)
    tri_v = points3d[:, iv][faces]
    u_min = np.floor((tri_u.min(axis=1) - low_u) / step_u).astype(int)
    u_max = np.ceil((tri_u.max(axis=1) - low_u) / step_u).astype(int)
    v_min = np.floor((tri_v.min(axis=1) - low_v) / step_v).astype(int)
    v_max = np.ceil((tri_v.max(axis=1) - low_v) / step_v).astype(int)
    for f in range(len(faces)):
        u0, u1 = max(u_min[f], 0), min(u_max[f], resolution)
        v0, v1 = max(v_min[f], 0), min(v_max[f], resolution)
        if u0 >= u1 or v0 >= v1:
            continue
        a_u, a_v = tri_u[f, 0], tri_v[f, 0]
        b_u, b_v = tri_u[f, 1], tri_v[f, 1]
        c_u, c_v = tri_u[f, 2], tri_v[f, 2]
        denom = (b_v - c_v) * (a_u - c_u) + (c_u - b_u) * (a_v - c_v)
        if abs(denom) < 1e-15:
            continue
        gu, gv = np.meshgrid(us[u0:u1], vs[v0:v1], indexing="ij")
        w0 = ((b_v - c_v) * (gu - c_u) + (c_u - b_u) * (gv - c_v)) / denom
        w1 = ((c_v - a_v) * (gu - c_u) + (a_u - c_u) * (gv - c_v)) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if inside.any():
            block = mask[u0:u1, v0:v1]
            block |= inside
    return mask


def render_masks(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    """Top (x,y) and side (x,z) 96x96 masks following the sealed convention."""
    top_hi = _rasterize_view(mesh.vertices, mesh.faces, "x", "y", RES_MASK_SRC)
    side_hi = _rasterize_view(mesh.vertices, mesh.faces, "x", "z", RES_MASK_SRC)
    return _downsample_any(top_hi, RES_MASK), _downsample_any(side_hi, RES_MASK)


# ------------------------- GT voxelization (ray parity fill along y) -------------------------

def voxelize_gt(mesh: trimesh.Trimesh, resolution: int = RES_VOX) -> tuple[np.ndarray, dict]:
    """Occupancy at benchmark 64^3 cell centers via parity fill of ray hits along +y."""
    xs = cell_centers("x", resolution)
    ys = cell_centers("y", resolution)
    zs = cell_centers("z", resolution)
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    origins = np.stack([gx.ravel(), np.full(gx.size, WORLD["y"][0] - 0.5), gz.ravel()], axis=1)
    directions = np.tile(np.array([[0.0, 1.0, 0.0]]), (len(origins), 1))
    locations, index_ray, _ = mesh.ray.intersects_location(origins, directions, multiple_hits=True)
    ts = locations[:, 1] - origins[0, 1]  # distance along +y from origin (same for all)
    occ = np.zeros((resolution, resolution, resolution), dtype=bool)
    odd_columns = 0
    hits_per_ray: dict[int, list[float]] = {}
    for r, t in zip(index_ray, ts):
        hits_per_ray.setdefault(int(r), []).append(float(t))
    y_low = WORLD["y"][0]
    step_y = (WORLD["y"][1] - y_low) / resolution
    eps = 1e-6
    for r, tlist in hits_per_ray.items():
        tlist.sort()
        # dedupe near-duplicate hits (shared triangle edges)
        dedup: list[float] = []
        for t in tlist:
            if not dedup or t - dedup[-1] > eps:
                dedup.append(t)
        if len(dedup) < 2:
            continue
        if len(dedup) % 2 == 1:
            odd_columns += 1
            dedup = dedup[:-1]
        xi, zi = divmod(r, resolution)
        for a, b in zip(dedup[0::2], dedup[1::2]):
            y0 = a + origins[0, 1]
            y1 = b + origins[0, 1]
            j0 = int(np.clip(np.searchsorted(ys, y0, side="left"), 0, resolution))
            j1 = int(np.clip(np.searchsorted(ys, y1, side="left"), 0, resolution))
            # fill cell centers strictly inside (y0, y1]
            if j1 > j0:
                occ[xi, j0:j1, zi] = True
    info = {"odd_parity_columns": odd_columns, "columns_with_hits": len(hits_per_ray), "filled_voxels": int(occ.sum())}
    return occ, info


def mask_from_occ(occ: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Project 64^3 occupancy to 96^2 masks by nearest upsampling of any-projections (QC only)."""
    top = occ.any(axis=2)
    side = occ.any(axis=1)
    return top, side


# ------------------------- GT voxelization v2 (splat + parity + closing) -------------------------

def _triangle_splat(mesh: trimesh.Trimesh, resolution: int) -> np.ndarray:
    """Surface occupancy: trimesh fine surface voxelization (pitch 0.03 m) remapped
    onto the benchmark world grid. Every fine voxel lands in its coarse cell, so thin
    structures (spokes, lattice bars, foliage) are preserved without slab overfill.
    Falls back to an empty grid if the fine voxelization fails.
    """
    lows = np.array([WORLD["x"][0], WORLD["y"][0], WORLD["z"][0]], dtype=float)
    highs = np.array([WORLD["x"][1], WORLD["y"][1], WORLD["z"][1]], dtype=float)
    steps = (highs - lows) / resolution
    occ = np.zeros((resolution, resolution, resolution), dtype=bool)
    try:
        vg = mesh.voxelized(0.03)
        idx = np.argwhere(vg.encoding.dense)
        if len(idx):
            pts = vg.indices_to_points(idx)
            ci = np.clip(np.floor((pts - lows) / steps).astype(int), 0, resolution - 1)
            occ[ci[:, 0], ci[:, 1], ci[:, 2]] = True
    except Exception:
        pass
    return occ


def voxelize_gt_v2(mesh: trimesh.Trimesh, resolution: int = RES_VOX) -> tuple[np.ndarray, dict]:
    """GT = closing_1iter( triangle_splat U ray_parity_fill ).

    Rationale: parity fill gives solid interiors for well-closed meshes but fails on
    open/thin geometry (billboard foliage, bicycle spokes, lattice bars); the triangle
    splat preserves exactly those thin structures. One iteration of 3x3x3 closing
    bridges sub-cell gaps. Documented as the external-check GT convention.
    """
    from scipy import ndimage

    parity, pinfo = voxelize_gt(mesh, resolution)
    splat = _triangle_splat(mesh, resolution)
    union = splat | parity
    structure = ndimage.generate_binary_structure(3, 1)
    closed = ndimage.binary_closing(union, structure=structure, iterations=1, border_value=0)
    info = {
        **{f"parity_{k}": v for k, v in pinfo.items()},
        "splat_voxels": int(splat.sum()),
        "parity_only_voxels": int(parity.sum()),
        "union_voxels": int(union.sum()),
        "closed_voxels": int(closed.sum()),
    }
    return closed, info
