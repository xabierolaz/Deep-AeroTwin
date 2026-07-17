"""Step 2 (Amendment 05 E4): generate the two prespecified input conditions.

(a) clean-crop  : one shaded oblique render of the source actor (RGB PNG,
                  white background, fixed orthographic camera az=45 el=30).
                  Rendered by voxel splatting of voxelize_source(actor, 256) -
                  handles every source component type (CSG and implicit).
(b) telemetry-matched: the actual clean 96x96 top observation mask as an RGB
                  PNG (white silhouette on black), native resolution.

Also writes per-case GT bounding boxes (cell-center convention on the sealed
64-cubed grid) for the prespecified alignment, objects CSVs in 2 chunks for
the batch runners, and an input manifest with SHA-256 of every PNG.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reproducibility" / "sppa_mvfit"))

from source.source_generators import voxelize_source  # noqa: E402
from wave_common import (  # noqa: E402
    CAM_AZIMUTH_DEG,
    CAM_ELEVATION_DEG,
    DATA_TEST,
    IMAGE_SIZE,
    MASK_CONDITION_INDEX,
    MASK_TOP_INDEX,
    RENDER_RESOLUTION,
    WAVE_ROOT,
    cell_centers,
    load_case_actors,
    load_subset_manifest,
    sha256_file,
    write_json,
)

CHUNK_CASES = 15


def camera_basis():
    az = math.radians(CAM_AZIMUTH_DEG)
    el = math.radians(CAM_ELEVATION_DEG)
    d = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])  # origin -> camera
    f = -d
    up_w = np.array([0.0, 0.0, 1.0])
    r = np.cross(f, up_w)
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    u = u / np.linalg.norm(u)
    return r, u, d


def render_oblique(occupancy: np.ndarray, image_size: int = IMAGE_SIZE) -> Image.Image:
    res = occupancy.shape[0]
    xs = cell_centers("x", res)
    ys = cell_centers("y", res)
    zs = cell_centers("z", res)

    occ = occupancy
    eroded = occ.copy()
    eroded[1:, :, :] &= occ[:-1, :, :]
    eroded[:-1, :, :] &= occ[1:, :, :]
    eroded[:, 1:, :] &= occ[:, :-1, :]
    eroded[:, :-1, :] &= occ[:, 1:, :]
    eroded[:, :, 1:] &= occ[:, :, :-1]
    eroded[:, :, :-1] &= occ[:, :, 1:]
    surface = occ & ~eroded
    if not np.any(surface):
        surface = occ

    field = occ.astype(np.float32)
    try:
        from scipy.ndimage import gaussian_filter

        field = gaussian_filter(field, sigma=1.2)
    except Exception:
        pad = np.pad(field, 1, mode="constant")
        field = sum(
            pad[di : di + field.shape[0], dj : dj + field.shape[1], dk : dk + field.shape[2]]
            for di in range(3)
            for dj in range(3)
            for dk in range(3)
        ) / 27.0
    gx, gy, gz = np.gradient(field)
    ii, jj, kk = np.nonzero(surface)
    px = xs[ii]
    py = ys[jj]
    pz = zs[kk]
    nx = -gx[ii, jj, kk]
    ny = -gy[ii, jj, kk]
    nz = -gz[ii, jj, kk]
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    norm[norm < 1e-9] = 1.0
    nx, ny, nz = nx / norm, ny / norm, nz / norm

    r, u, d = camera_basis()
    pts = np.stack([px, py, pz], axis=1)
    xi = pts @ r
    yi = pts @ u
    di = pts @ d

    span_x = float(xi.max() - xi.min()) or 1.0
    span_y = float(yi.max() - yi.min()) or 1.0
    scale = 0.84 * image_size / max(span_x, span_y)
    ox = 0.5 * (image_size - span_x * scale)
    oy = 0.5 * (image_size - span_y * scale)
    col = (xi - xi.min()) * scale + ox
    row_up = (yi - yi.min()) * scale + oy
    row = (image_size - 1) - row_up

    light = d + 0.55 * u + 0.25 * r
    light = light / np.linalg.norm(light)
    ndotl = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0.0, 1.0)
    gray = np.clip(0.35 + 0.55 * ndotl, 0.0, 1.0)

    c0 = np.floor(col).astype(np.int64)
    r0 = np.floor(row).astype(np.int64)
    offsets = (-1, 0, 1)
    cols = np.concatenate([c0 + dc for dc in offsets for _ in offsets])
    rows = np.concatenate([r0 + dr for _ in offsets for dr in offsets])
    vals = np.concatenate([gray] * 9)
    depth = np.concatenate([di] * 9)
    valid = (cols >= 0) & (cols < image_size) & (rows >= 0) & (rows < image_size)
    cols, rows, vals, depth = cols[valid], rows[valid], vals[valid], depth[valid]

    order = np.argsort(depth, kind="stable")  # far first; nearest written last
    img = np.full((image_size, image_size), 255, dtype=np.uint8)
    flat = rows[order] * image_size + cols[order]
    img.reshape(-1)[flat] = (vals[order] * 255.0).round().astype(np.uint8)
    return Image.fromarray(img, mode="L").convert("RGB")


def mask_image(mask: np.ndarray) -> Image.Image:
    img = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
    img[mask.astype(bool)] = 255
    return Image.fromarray(img, mode="RGB")


def gt_bbox_world(occupancy: np.ndarray) -> dict:
    res = occupancy.shape[0]
    idx = np.argwhere(occupancy)
    if not len(idx):
        raise RuntimeError("empty GT occupancy")
    lo = idx.min(axis=0)
    hi = idx.max(axis=0)
    centers = (cell_centers("x", res), cell_centers("y", res), cell_centers("z", res))
    bbox_min = [float(centers[a][lo[a]]) for a in range(3)]
    bbox_max = [float(centers[a][hi[a]]) for a in range(3)]
    return {"bbox_min": bbox_min, "bbox_max": bbox_max}


def main() -> int:
    subset = load_subset_manifest()
    actors = load_case_actors()
    masks = np.load(DATA_TEST / "observation_masks.npy", allow_pickle=False)

    inputs_dir = WAVE_ROOT / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    gt_bboxes: dict[str, dict] = {}
    input_hashes: dict[str, dict] = {}

    for case in subset["cases"]:
        case_id = case["case_id"]
        actor = actors[case_id]

        occ_hi = voxelize_source(actor, RENDER_RESOLUTION)
        oblique = render_oblique(occ_hi)
        oblique_path = inputs_dir / f"{case_id}__oblique.png"
        oblique.save(oblique_path)

        top_mask = masks[case["index"], MASK_CONDITION_INDEX, MASK_TOP_INDEX]
        mimg = mask_image(top_mask)
        mask_path = inputs_dir / f"{case_id}__mask.png"
        mimg.save(mask_path)

        occ_eval = voxelize_source(actor, 64)
        gt_bboxes[case_id] = gt_bbox_world(occ_eval)
        input_hashes[case_id] = {
            "oblique_png_sha256": sha256_file(oblique_path),
            "mask_png_sha256": sha256_file(mask_path),
            "gt_occupied_voxels_64": int(np.count_nonzero(occ_eval)),
        }

        prompt = case["family"].replace("_", " ")
        rows.append({"label": f"{case_id}__oblique", "image": str(oblique_path), "prompt": prompt})
        rows.append({"label": f"{case_id}__mask", "image": str(mask_path), "prompt": prompt})

    write_json(WAVE_ROOT / "gt_bboxes.json", gt_bboxes)

    chunk_paths = []
    for start in range(0, len(rows), CHUNK_CASES * 2):
        chunk = rows[start : start + CHUNK_CASES * 2]
        chunk_path = WAVE_ROOT / f"objects_chunk{start // (CHUNK_CASES * 2)}.csv"
        with chunk_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["label", "image", "prompt"])
            writer.writeheader()
            writer.writerows(chunk)
        chunk_paths.append(str(chunk_path))

    manifest = {
        "schema": "sppa-neural-external-wave-inputs-v1",
        "amendment": "SPPA_PROTOCOL_AMENDMENT_05_20260717.md (E4)",
        "condition_a": "shaded oblique render of the source actor, RGB PNG on white, fixed orthographic camera az=45 deg el=30 deg, voxel-splat render of voxelize_source(actor, 256)",
        "condition_b": "actual clean 96x96 top observation mask as RGB PNG (white silhouette on black), native resolution",
        "image_size_oblique": IMAGE_SIZE,
        "render_voxel_resolution": RENDER_RESOLUTION,
        "objects_csv_chunks": chunk_paths,
        "row_count": len(rows),
        "cases": input_hashes,
    }
    write_json(WAVE_ROOT / "inputs_manifest.json", manifest)
    print(f"rendered {len(subset['cases'])} cases -> {len(rows)} input rows")
    print("chunks:", *chunk_paths, sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
