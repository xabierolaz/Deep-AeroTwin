"""E11 "Oblique Twin Wave" - shared machinery (exploratory post-hoc, NOT sealed).

Everything here implements PROTOCOL_E11.md (frozen 2026-07-20):
  * view geometry from the manifest (Unreal euler/quat -> pipeline NED
    telemetry; mapping verified against the manifest quaternions, <1e-3 deg);
  * observation construction identical to E7 (same GeoProjector calls, same
    estimator `e7_common.estimate_height_m`, same gates), only the camera
    constants differ (mount 0/0/0 - the manifest rotation IS the camera
    rotation - and the per-frame AGL comes from the manifest);
  * POSITIONS LOCKED TO GT: the per-case window is centered on the tower's
    exact simulator pivot; the observation contributes shape only;
  * exact-GT solid voxelization of the welded OBJ at each tower pose;
  * canonical per-tower frame for cross-view consistency.

Read-only imports: sealed fitter (method.sppa_mvfit) and the E7 modules.
Nothing outside benchmarks/oblique_twin_wave/ is written.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

E11_ROOT = Path(__file__).resolve().parent
BENCH_ROOT = E11_ROOT.parent
sys.path.insert(0, str(BENCH_ROOT / "real_stream_wave"))

from e7_common import (  # noqa: E402
    CLASS_TO_FAMILY, EVAL_RES, EXPLORATORY_LABEL, FAMILY_NOMINAL_HEIGHT_M,
    FAMILY_SCALE_M_PER_UNIT, HEIGHT_MIN_VALID_M, OBS_RES, GeoProjector,
    estimate_height_m, graph_extent_units, mv, scaled_graphs_for_family,
)
from run_e7_real_stream import case_window, cell_centers, rasterize_masks, run_method  # noqa: E402

MANIFEST_PATH = E11_ROOT / "manifest.jsonl"
GT_GEOMETRY_PATH = E11_ROOT / "gt" / "tower_geometry.json"
GT_MESH_OBJ = E11_ROOT / "gt" / "tower_mesh_Internal.obj"  # welded (preferred per obj_notes)
FRAMES_DIR = E11_ROOT / "frames"

# E11 camera constants (protocol section 3): manifest rotation IS the camera
# rotation -> mount 0/0/0; VFOV and range gates identical to E7.
CAM11 = {
    "image_width": 640,
    "image_height": 640,
    "vfov_deg": 70.0,
    "mount_roll_deg": 0.0,
    "mount_pitch_deg": 0.0,
    "mount_yaw_deg": 0.0,
    "max_range_m": 80.0,     # same as E7 (DETECTION_RANGE_M, SIMULATION mode)
    "clamp_to_max_range": False,
    "min_agl_m": 0.5,
}
GT_CONTAIN_MARGIN_M = 0.5   # declared window enlargement to contain the GT AABB
METHODS = ("sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule")


# ---------------------------------------------------------------------------
# Manifest / GT loading
# ---------------------------------------------------------------------------
def load_manifest() -> dict[str, dict]:
    rows = [json.loads(line) for line in MANIFEST_PATH.open("r", encoding="utf-8")]
    return {r["frame_id"]: r for r in rows if r.get("ok")}


def load_gt_geometry() -> dict[str, dict]:
    payload = json.loads(GT_GEOMETRY_PATH.read_text(encoding="utf-8"))
    return {a["label"]: a for a in payload["actors"]}


def tel_from_manifest(entry: dict) -> dict:
    """Manifest Unreal camera euler -> pipeline NED telemetry (verified mapping)."""
    eul = entry["camera_rotation_euler"]
    return {
        "yaw": (float(eul["yaw"]) + 90.0) % 360.0,
        "pitch": float(eul["pitch"]),
        "roll": -float(eul["roll"]),
        "alt_agl": float(entry["agl_m"]),
    }


def quat_to_R(q: dict) -> np.ndarray:
    x, y, z, w = (float(q[k]) for k in ("x", "y", "z", "w"))
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


# ---------------------------------------------------------------------------
# Observation (E7 construction, E11 camera constants)
# ---------------------------------------------------------------------------
def build_observation_e11(bbox: dict, tel: dict) -> dict | None:
    """One observation per detection: oriented footprint + height estimate.

    Line-by-line port of e7_common.build_observation with CAM11 constants
    (mount 0/0/0) and the manifest view geometry. Same gates as E7.
    """
    x1, y1, x2, y2 = (float(bbox[k]) for k in ("x1", "y1", "x2", "y2"))
    if x2 <= x1 or y2 <= y1:
        return None
    common = dict(
        image_height=CAM11["image_height"],
        image_width=CAM11["image_width"],
        drone_yaw_deg=float(tel["yaw"]),
        drone_pitch_deg=float(tel["pitch"]),
        drone_roll_deg=float(tel["roll"]),
        camera_vfov_deg=CAM11["vfov_deg"],
        mount_roll_deg=CAM11["mount_roll_deg"],
        mount_pitch_deg=CAM11["mount_pitch_deg"],
        mount_yaw_deg=CAM11["mount_yaw_deg"],
    )
    alt_agl = float(tel["alt_agl"])
    if not math.isfinite(alt_agl) or alt_agl < CAM11["min_agl_m"]:
        return None

    footprint = GeoProjector.bbox_to_ground_footprint_m(
        (x1, y1, x2, y2),
        alt_agl_m=alt_agl,
        max_range_m=CAM11["max_range_m"],
        clamp_to_max_range=CAM11["clamp_to_max_range"],
        **common,
    )
    if footprint is None or footprint["length_m"] < 0.05 or footprint["width_m"] < 0.05:
        return None

    base = GeoProjector.pixel_to_ground_offset_m(
        y2, (x1 + x2) / 2.0, alt_agl_m=alt_agl, max_range_m=CAM11["max_range_m"],
        clamp_to_max_range=CAM11["clamp_to_max_range"], **common,
    )
    ray_top = GeoProjector.pixel_to_ray_ned(y1, (x1 + x2) / 2.0, **common)
    if base is None or ray_top is None:
        return None
    height = estimate_height_m(ray_top, base["north_m"], base["east_m"], alt_agl, base["distance_m"])
    if height is None or height < HEIGHT_MIN_VALID_M:
        return None

    return {
        "footprint": footprint,
        "height_m": height,
        "base_distance_m": base["distance_m"],
        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
    }


# ---------------------------------------------------------------------------
# Exact GT mesh in the per-case window frame + solid voxelization
# ---------------------------------------------------------------------------
_MESH_CACHE: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _load_mesh_local() -> tuple[np.ndarray, np.ndarray]:
    """Welded OBJ -> Unreal-local meters (OBJ (x,y,z) = Unreal (x,z,y), cm)."""
    import trimesh

    mesh = trimesh.load(str(GT_MESH_OBJ), process=False)
    v = np.asarray(mesh.vertices, dtype=float)
    local = np.stack([v[:, 0], v[:, 2], v[:, 1]], axis=1) / 100.0
    return local, np.asarray(mesh.faces, dtype=np.int64)


def mesh_in_window(tower_label: str, bearing_rad: float, gt_actors: dict[str, dict]):
    """Mesh vertices in the case window frame (x = footprint major axis at
    compass bearing `bearing_rad`, z up from the locked pivot)."""
    key = f"{tower_label}|{bearing_rad:.6f}"
    if key in _MESH_CACHE:
        return _MESH_CACHE[key]
    if "local" not in _MESH_CACHE:
        _MESH_CACHE["local"] = _load_mesh_local()
    local, faces = _MESH_CACHE["local"]
    R = quat_to_R(gt_actors[tower_label]["world_rotation_quat"])
    d = (R @ local.T).T  # meters, rel pivot, Unreal world axes (E=+x, S=+y, U=+z)
    north, east, up = -d[:, 1], d[:, 0], d[:, 2]
    cb, sb = math.cos(bearing_rad), math.sin(bearing_rad)
    wx = north * cb + east * sb
    wy = -north * sb + east * cb
    out = (np.stack([wx, wy, up], axis=1), faces)
    _MESH_CACHE[key] = out
    return out


def _closest_pt_triangle_dist2(P: np.ndarray, A: np.ndarray, B: np.ndarray, C: np.ndarray) -> np.ndarray:
    """Vectorized Ericson 5.1.5: squared distance from points P (n,3) to triangle ABC."""
    ab = B - A
    ac = C - A
    ap = P - A
    d1 = ap @ ab
    d2 = ap @ ac
    closest = np.empty_like(P)

    m = (d1 <= 0) & (d2 <= 0)
    closest[m] = A

    bp = P - B
    d3 = bp @ ab
    d4 = bp @ ac
    m2 = (~m) & (d3 >= 0) & (d4 <= d3)
    closest[m2] = B

    vc = d1 * d4 - d3 * d2
    m3 = (~m) & (~m2) & (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    v = np.zeros(len(P))
    v[m3] = d1[m3] / (d1[m3] - d3[m3])
    closest[m3] = A + v[m3, None] * ab

    cp = P - C
    d5 = cp @ ab
    d6 = cp @ ac
    done = m | m2 | m3
    m4 = (~done) & (d6 >= 0) & (d5 <= d6)
    closest[m4] = C
    done |= m4

    vb = d5 * d2 - d1 * d6
    m5 = (~done) & (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    w = np.zeros(len(P))
    w[m5] = d2[m5] / (d2[m5] - d6[m5])
    closest[m5] = A + w[m5, None] * ac
    done |= m5

    va = d3 * d6 - d5 * d4
    m6 = (~done) & (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    w6 = np.zeros(len(P))
    denom = (d4[m6] - d3[m6]) + (d5[m6] - d6[m6])
    w6[m6] = (d4[m6] - d3[m6]) / denom
    closest[m6] = B + w6[m6, None] * (C - B)
    done |= m6

    rest = ~done
    den = va + vb + vc
    vv = np.zeros(len(P))
    ww = np.zeros(len(P))
    vv[rest] = vb[rest] / den[rest]
    ww[rest] = vc[rest] / den[rest]
    closest[rest] = A + ab * vv[rest, None] + ac * ww[rest, None]

    return np.sum((P - closest) ** 2, axis=1)


def voxelize_mesh_solid(verts: np.ndarray, faces: np.ndarray, window: dict, res: int = EVAL_RES):
    """Conservative surface voxelization + enclosed-interior fill (declared
    "enclosed-solid" convention). Returns (surface_occ, solid_occ)."""
    lows = np.array([window[a][0] for a in "xyz"])
    highs = np.array([window[a][1] for a in "xyz"])
    h = (highs - lows) / res
    half_diag = 0.5 * float(np.sqrt(h @ h))
    occ = np.zeros((res, res, res), dtype=bool)
    for tri in faces:
        p = verts[tri]
        lo = p.min(axis=0)
        hi = p.max(axis=0)
        i0 = np.maximum(np.floor((lo - lows) / h).astype(int), 0)
        i1 = np.minimum(np.floor((hi - lows) / h).astype(int), res - 1)
        if np.any(i1 < i0):
            continue
        xs = lows[0] + (np.arange(i0[0], i1[0] + 1) + 0.5) * h[0]
        ys = lows[1] + (np.arange(i0[1], i1[1] + 1) + 0.5) * h[1]
        zs = lows[2] + (np.arange(i0[2], i1[2] + 1) + 0.5) * h[2]
        gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
        pts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
        n = np.cross(p[1] - p[0], p[2] - p[0])
        norm = float(np.linalg.norm(n))
        if norm < 1e-12:
            continue
        n /= norm
        dist = (pts - p[0]) @ n
        tol_plane = 0.5 * (abs(n[0]) * h[0] + abs(n[1]) * h[1] + abs(n[2]) * h[2])
        keep = np.abs(dist) <= tol_plane
        if not np.any(keep):
            continue
        idx = np.argwhere(keep).ravel()
        pts2 = pts[idx]
        d2 = _closest_pt_triangle_dist2(pts2, p[0], p[1], p[2])
        hit = d2 <= (half_diag + 1e-9) ** 2
        if not np.any(hit):
            continue
        sub = np.unravel_index(idx[hit], (len(xs), len(ys), len(zs)))
        occ[sub[0] + i0[0], sub[1] + i0[1], sub[2] + i0[2]] = True
    solid = ndimage.binary_fill_holes(occ)
    return occ, solid


def enlarge_window_to_contain(window: dict, verts: np.ndarray) -> dict:
    """Declared enlargement: per axis, extend (never shrink) so the GT mesh
    AABB plus GT_CONTAIN_MARGIN_M is inside; symmetric expansion around the
    locked pivot for x/y (window stays centered on the pivot)."""
    out = {a: list(window[a]) for a in "xyz"}
    for i, a in enumerate("xyz"):
        lo, hi = float(verts[:, i].min()), float(verts[:, i].max())
        need_lo, need_hi = lo - GT_CONTAIN_MARGIN_M, hi + GT_CONTAIN_MARGIN_M
        if a in "xy":
            half = max(abs(out[a][0]), abs(out[a][1]), abs(need_lo), abs(need_hi))
            out[a] = [-half, half]
        else:
            out[a] = [min(out[a][0], need_lo), max(out[a][1], need_hi)]
    return {a: tuple(out[a]) for a in "xyz"} | {"nom": window["nom"]}


def voxel_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 0.0
    return float(np.count_nonzero(a & b) / union)


# ---------------------------------------------------------------------------
# Canonical per-tower frame (cross-view consistency)
# ---------------------------------------------------------------------------
def canonical_window(tower_label: str, gt_actors: dict[str, dict]) -> dict:
    """Fixed per-tower canonical window: x = North, y = East, z up from the
    pivot; E7 case_window sizing from the exact GT AABB + lattice_tower
    nominal, enlarged to contain the exact mesh (same declared rule)."""
    actor = gt_actors[tower_label]
    ext = actor["bounds_extent"]
    gt_len = 2 * float(ext["x"]) / 100.0
    gt_wid = 2 * float(ext["y"]) / 100.0
    gt_h = float(actor["bounds_height_m"])
    window = case_window(gt_len, gt_wid, gt_h, "lattice_tower")
    verts, _ = mesh_in_window(tower_label, 0.0, gt_actors)
    return enlarge_window_to_contain(window, verts)


def voxelize_actor_in_window(actor: list[dict], window: dict, bearing_rad: float, res: int = EVAL_RES) -> np.ndarray:
    """Evaluate the sealed primitive occupancy of a case-frame actor on the
    grid of `window`, whose x axis is North (canonical). Points are rotated
    into the case frame (bearing) before the sealed test - exact, no resample."""
    xs = cell_centers(window["x"], res)
    ys = cell_centers(window["y"], res)
    zs = cell_centers(window["z"], res)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij", sparse=True)
    cb, sb = math.cos(bearing_rad), math.sin(bearing_rad)
    xr = gx * cb + gy * sb
    yr = -gx * sb + gy * cb
    occ = np.zeros((res, res, res), dtype=bool)
    for prim in actor:
        occ |= mv._primitive_occupancy(prim, xr, yr, gz)
    return occ


def voxelize_boxes_in_window(boxes: list[dict], window: dict, bearing_rad: float, res: int = EVAL_RES) -> np.ndarray:
    """Axis-aligned-in-case-frame boxes with an optional per-box yaw inside
    the case frame (obb: yaw 0; aabb: yaw -bearing), evaluated on the
    canonical grid. Mirrors voxelize_oriented_box semantics."""
    xs = cell_centers(window["x"], res)
    ys = cell_centers(window["y"], res)
    zs = cell_centers(window["z"], res)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    cb, sb = math.cos(bearing_rad), math.sin(bearing_rad)
    xr = gx * cb + gy * sb
    yr = -gx * sb + gy * cb
    occ = np.zeros((res, res, res), dtype=bool)
    for box in boxes:
        dx = xr - box["center"][0]
        dy = yr - box["center"][1]
        cy, sy = math.cos(-box["yaw"]), math.sin(-box["yaw"])
        lx = dx * cy - dy * sy
        ly = dx * sy + dy * cy
        inside_xy = (np.abs(lx) <= box["size"][0] / 2) & (np.abs(ly) <= box["size"][1] / 2)
        z0 = box["center"][2] - box["size"][2] / 2
        z1 = box["center"][2] + box["size"][2] / 2
        inside_z = (zs >= z0) & (zs <= z1)
        occ |= inside_xy[:, :, None] & inside_z[None, None, :]
    return occ


def resample_occ_to_window(occ_case: np.ndarray, window_case: dict, bearing_rad: float,
                           window_can: dict, res: int = EVAL_RES) -> np.ndarray:
    """Nearest-neighbor resample of a case occupancy grid into the canonical
    window (declared approximation; only used for visual_hull / capsule
    consistency, never for metric (a))."""
    xs_c = cell_centers(window_case["x"], res)
    ys_c = cell_centers(window_case["y"], res)
    zs_c = cell_centers(window_case["z"], res)
    xs = cell_centers(window_can["x"], res)
    ys = cell_centers(window_can["y"], res)
    zs = cell_centers(window_can["z"], res)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
    cb, sb = math.cos(bearing_rad), math.sin(bearing_rad)
    xr = gx * cb + gy * sb
    yr = -gx * sb + gy * cb

    def to_idx(vals, centers):
        step = centers[1] - centers[0]
        return np.rint((vals - centers[0]) / step).astype(int)

    ix, iy, iz = to_idx(xr, xs_c), to_idx(yr, ys_c), to_idx(gz, zs_c)
    valid = (ix >= 0) & (ix < res) & (iy >= 0) & (iy < res) & (iz >= 0) & (iz < res)
    out = np.zeros((res, res, res), dtype=bool)
    out[valid] = occ_case[np.clip(ix[valid], 0, res - 1), np.clip(iy[valid], 0, res - 1), np.clip(iz[valid], 0, res - 1)]
    return out
