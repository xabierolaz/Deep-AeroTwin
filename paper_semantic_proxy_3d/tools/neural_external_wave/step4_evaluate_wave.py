"""Step 4 (Amendment 05 E5/E6): alignment, voxelization and metrics for the wave.

Modes:
  selftest   sanity-check the z-slice even-odd mesh voxelizer on an analytic box
  calibrate  select the fixed frame convention per method x condition on a small
             calibration subset (6 cases, 32-cubed grid), frozen afterwards
  eval       voxelize every output at 64-cubed with the frozen convention and
             write per-condition row files under wave_rows/
  aggregate  join rows with the sealed SPPA/context rows (read-only) and write
             benchmarks/results/<output-stem>.{json,md,tex}
             (default stem sppa_neural_external_wave; the E12 flagship extension
             uses --output-stem sppa_neural_flagship_wave so the published files
             are never overwritten)

E12 flagship extension (2026-07-19): events and mesh outputs are resolved across
RUN_DIRS (newest first for outputs, oldest first for events so newer logs win),
which lets the flagship run 20260719_flagship_wave extend the wave without
touching the 20260717_wave artifacts.

Alignment (prespecified, generous): rotate with the frozen frame convention,
uniform scale s = geometric mean of per-axis GT/mesh bbox extent ratios,
translate so the mesh bbox center matches the GT bbox center. No per-case
tuning; crashes/degenerates are reported, not silently excluded.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reproducibility" / "sppa_mvfit"))

from source.source_generators import voxelize_source  # noqa: E402
from wave_common import (  # noqa: E402
    RESULTS_ROOT,
    RESULTS_TEST,
    WAVE_ROOT,
    WORLD,
    cell_centers,
    load_case_actors,
    load_json,
    load_subset_manifest,
    sha256_file,
    write_json,
)

WORLD_SPAN = tuple(WORLD[a][1] - WORLD[a][0] for a in ("x", "y", "z"))

RUN_DIR = WAVE_ROOT / "runs" / "20260717_wave"
# E12: flagship extension run. Outputs resolved newest-first, events oldest-first.
RUN_DIRS = [WAVE_ROOT / "runs" / "20260719_flagship_wave", RUN_DIR]
ROWS_DIR = WAVE_ROOT / "wave_rows"
CALIB_PATH = WAVE_ROOT / "wave_calibration.json"

METHOD_DIRS = {
    "triposr": "triposr",
    "hunyuan3d_2mini_turbo": "hunyuan3d_2mini_turbo",
    "triposg": "triposg",
    "hunyuan3d_2_full": "hunyuan3d_2_full",
}
METHOD_EXT = {
    "triposr": ".obj",
    "hunyuan3d_2mini_turbo": ".glb",
    "triposg": ".glb",
    "hunyuan3d_2_full": ".glb",
}
MODEL_TO_METHOD = {
    "triposr_warm": "triposr",
    "hunyuan3d_2mini_turbo_shape": "hunyuan3d_2mini_turbo",
    "triposg": "triposg",
    "hunyuan3d_2_full_shape": "hunyuan3d_2_full",
}
CONDITIONS = ("oblique", "mask")

EXCLUDED_METHODS = [
    {"method": "SF3D (Stable Fast 3D)", "reason": "install/build failure under the Amendment 05 Python 3.12 / torch 2.10 / CUDA 12.9 stack (gpytoolbox, texture_baker build); an earlier Python 3.10 attempt produced no benchmark event before a 20-minute timeout; documented in benchmarks/neural_external_wave/exclusion_notes/sf3d_timeout_note.md"},
    {"method": "SPAR3D", "reason": "gated model weights; access not granted; documented in benchmarks/neural_external_wave/exclusion_notes/spar3d_access_note.md"},
    {"method": "TRELLIS.2", "reason": "no working Windows environment in this repo (setup.sh is Linux-only); not installed"},
]


# --------------------------------------------------------------------------- io


def load_events() -> dict:
    events: dict[str, dict] = {}
    for run_dir in reversed(RUN_DIRS):  # oldest first: newer run logs win on key collision
        for log in sorted(run_dir.glob("*_chunk*.stdout.log")):
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("SPPA_BENCH_OBJECT "):
                    payload = json.loads(line[len("SPPA_BENCH_OBJECT "):])
                    method = MODEL_TO_METHOD.get(payload.get("model"))
                    if method:
                        events[(method, payload["label"])] = payload
    return events


def _method_out_dir(method: str) -> Path:
    for run_dir in RUN_DIRS:  # newest first
        candidate = run_dir / "outputs" / METHOD_DIRS[method]
        if candidate.is_dir():
            return candidate
    return RUN_DIRS[0] / "outputs" / METHOD_DIRS[method]


def load_mesh(path: Path):
    import trimesh

    if path.suffix.lower() == ".glb":
        scene = trimesh.load(path, force="scene")
        mesh = scene.dump(concatenate=True)
    else:
        mesh = trimesh.load(path, force="mesh")
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    finite = np.isfinite(verts).all(axis=1)
    if not finite.all():
        keep = np.nonzero(finite)[0]
        remap = -np.ones(len(verts), dtype=np.int64)
        remap[keep] = np.arange(len(keep))
        fmask = np.isfinite(faces).all(axis=1) & (faces >= 0).all(axis=1) & (faces < len(verts)).all(axis=1)
        faces = faces[fmask]
        fmask = np.isin(faces.ravel(), keep).reshape(faces.shape).all(axis=1)
        faces = remap[faces[fmask]]
        verts = verts[keep]
    return verts, faces


# ------------------------------------------------------------------- voxelizer


def voxelize_mesh(verts: np.ndarray, faces: np.ndarray, res: int = 64) -> np.ndarray:
    """Solid occupancy on the sealed WORLD grid via z-slice even-odd fill.

    Fixed rule for watertight and non-watertight/degenerate outputs alike
    (Amendment 05 E5): slice the triangle soup at each z cell center
    (+1e-9 epsilon), rasterize each slice with the even-odd rule at x/y cell
    centers. Counted as-is.
    """
    xs = cell_centers("x", res)
    ys = cell_centers("y", res)
    zs = cell_centers("z", res)
    occ = np.zeros((res, res, res), dtype=bool)
    if len(verts) == 0 or len(faces) == 0:
        return occ
    tri = verts[faces]
    zmin = tri[:, :, 2].min(axis=1)
    zmax = tri[:, :, 2].max(axis=1)
    tol = 1e-6 * max(WORLD_SPAN)  # rescues exact bbox-to-cell-center alignments only
    for k, zk in enumerate(zs):
        z = zk + 1e-9
        m = (zmin <= z) & (zmax > z - tol)
        if not m.any():
            continue
        t = tri[m]
        tid_parts = []
        pt_parts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            za = t[:, a, 2]
            zb = t[:, b, 2]
            steep = np.abs(zb - za) > 1e-12  # horizontal edges carry no crossing information
            em = steep & (((za <= z + tol) & (zb > z - tol)) | ((zb <= z + tol) & (za > z - tol)))
            if not em.any():
                continue
            idx = np.nonzero(em)[0]
            w = np.clip((z - za[em]) / (zb[em] - za[em]), 0.0, 1.0)
            pxy = t[em, a, :2] + w[:, None] * (t[em, b, :2] - t[em, a, :2])
            tid_parts.append(idx)
            pt_parts.append(pxy)
        if not tid_parts:
            continue
        tids = np.concatenate(tid_parts)
        pts = np.concatenate(pt_parts)
        counts = np.bincount(tids, minlength=len(t))
        ok_tids = np.nonzero(counts >= 2)[0]
        if not len(ok_tids):
            continue
        order = np.argsort(tids, kind="stable")
        tids_s = tids[order]
        pts_s = pts[order]
        starts = np.searchsorted(tids_s, ok_tids)
        segs = np.stack([pts_s[starts], pts_s[starts + 1]], axis=1)  # (S,2,2)
        y0 = segs[:, 0, 1]
        y1 = segs[:, 1, 1]
        for j, yj in enumerate(ys):
            mrow = ((y0 <= yj + tol) & (y1 > yj - tol)) | ((y1 <= yj + tol) & (y0 > yj - tol))
            if not mrow.any():
                continue
            xa = segs[mrow, 0, 0]
            xb = segs[mrow, 1, 0]
            ya = y0[mrow]
            yb = y1[mrow]
            denom = yb - ya
            keep = np.abs(denom) > 1e-12  # horizontal segments carry no parity information
            if not keep.any():
                continue
            xa, xb, ya, denom = xa[keep], xb[keep], ya[keep], denom[keep]
            w = (yj - ya) / denom
            xi = xa + w * (xb - xa)
            xi.sort()
            if len(xi) < 2:
                continue
            xi = xi[: len(xi) // 2 * 2]
            lo = np.searchsorted(xs, xi[0::2] - tol)
            hi = np.searchsorted(xs, xi[1::2] + tol, side="right")
            diff = np.zeros(res + 1, dtype=np.int32)
            np.add.at(diff, lo, 1)
            np.add.at(diff, hi, -1)
            filled = np.cumsum(diff)[:res] > 0
            occ[:, j, k] = filled
    return occ


# ------------------------------------------------------------------- alignment


def rotation_oblique() -> np.ndarray:
    az = math.radians(45.0)
    el = math.radians(30.0)
    d = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    f = -d
    r = np.cross(f, np.array([0.0, 0.0, 1.0]))
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    u = u / np.linalg.norm(u)
    return np.stack([r, u, d], axis=1)  # columns: image right, image up, toward camera


def rotation_mask() -> np.ndarray:
    r = np.array([0.0, 1.0, 0.0])  # image right = +y (mask column axis)
    u = np.array([-1.0, 0.0, 0.0])  # image up = -x (mask row axis grows downward)
    d = np.array([0.0, 0.0, 1.0])  # camera above, looking down -z
    return np.stack([r, u, d], axis=1)


def candidate_rotations(base: np.ndarray) -> dict:
    """All 48 signed permutation conventions C (axis remap + sign), v_world = B @ C @ v_mesh.

    Covers every axis-aligned generator output convention (y-up/z-up, mirrored,
    upside-down, depth-reversed, ...), composed with the known render camera B.
    """
    import itertools

    out = {}
    for perm in itertools.permutations(range(3)):
        perm_m = np.zeros((3, 3))
        for i, j in enumerate(perm):
            perm_m[i, j] = 1.0
        for signs in itertools.product((1.0, -1.0), repeat=3):
            corr = np.diag(signs) @ perm_m
            name = f"p{''.join(str(i) for i in perm)}s{''.join('+' if s > 0 else '-' for s in signs)}"
            out[name] = base @ corr
    return out


def align_vertices(verts: np.ndarray, rot: np.ndarray, gt_bbox: dict):
    v = verts @ rot.T
    vmin = v.min(axis=0)
    vmax = v.max(axis=0)
    e = np.maximum(vmax - vmin, 1e-9)
    gt_min = np.asarray(gt_bbox["bbox_min"], dtype=np.float64)
    gt_max = np.asarray(gt_bbox["bbox_max"], dtype=np.float64)
    extent_gt = np.maximum(gt_max - gt_min, 1e-9)
    s = float(np.exp(np.mean(np.log(extent_gt / e))))
    s = float(np.clip(s, 1e-3, 1e3))
    c_mesh = 0.5 * (vmin + vmax)
    c_gt = 0.5 * (gt_min + gt_max)
    return (v - c_mesh) * s + c_gt, s


def binary_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 1.0
    return float(np.count_nonzero(a & b) / union)


# ------------------------------------------------------------------------ modes


def mode_selftest() -> int:
    import trimesh

    actors = load_case_actors()
    subset = load_subset_manifest()
    case = subset["cases"][0]
    gt = voxelize_source(actors[case["case_id"]], 64)
    # box the size of the GT bbox, centered: must reproduce a solid box occupancy
    gt_bbox = load_json(WAVE_ROOT / "gt_bboxes.json")[case["case_id"]]
    bmin = np.asarray(gt_bbox["bbox_min"])
    bmax = np.asarray(gt_bbox["bbox_max"])
    box = trimesh.creation.box(extents=bmax - bmin)
    box.apply_translation(0.5 * (bmin + bmax))
    occ = voxelize_mesh(np.asarray(box.vertices), np.asarray(box.faces), 64)
    # analytic reference for the same box
    xs = cell_centers("x", 64)
    ys = cell_centers("y", 64)
    zs = cell_centers("z", 64)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij", sparse=True)
    ref = (np.abs(gx - 0.5 * (bmin[0] + bmax[0])) <= (bmax[0] - bmin[0]) / 2) & (
        np.abs(gy - 0.5 * (bmin[1] + bmax[1])) <= (bmax[1] - bmin[1]) / 2
    ) & (np.abs(gz - 0.5 * (bmin[2] + bmax[2])) <= (bmax[2] - bmin[2]) / 2)
    iou = binary_iou(occ, ref)
    print(f"selftest aligned box IoU vs analytic reference: {iou:.4f} (occupied {int(occ.sum())} vs {int(ref.sum())})")
    print(f"gt sanity: case {case['case_id']} occupied voxels {int(gt.sum())}")
    # second box NOT aligned to cell centers: checks there is no systematic overfill
    off = np.array([0.37, 0.53, 0.71]) * ((bmax - bmin) / 20.0)
    b2min = bmin + off
    b2max = bmax + off
    box2 = trimesh.creation.box(extents=b2max - b2min)
    box2.apply_translation(0.5 * (b2min + b2max))
    occ2 = voxelize_mesh(np.asarray(box2.vertices), np.asarray(box2.faces), 64)
    ref2 = (np.abs(gx - 0.5 * (b2min[0] + b2max[0])) <= (b2max[0] - b2min[0]) / 2) & (
        np.abs(gy - 0.5 * (b2min[1] + b2max[1])) <= (b2max[1] - b2min[1]) / 2
    ) & (np.abs(gz - 0.5 * (b2min[2] + b2max[2])) <= (b2max[2] - b2min[2]) / 2)
    iou2 = binary_iou(occ2, ref2)
    print(f"selftest offset box IoU vs analytic reference: {iou2:.4f} (occupied {int(occ2.sum())} vs {int(ref2.sum())})")
    if iou < 0.95 or iou2 < 0.90:
        print("SELFTEST FAILED")
        return 1
    print("SELFTEST OK")
    return 0


def _calibration_cases(subset: dict) -> list[dict]:
    chosen: list[dict] = []
    seen = set()
    for case in subset["cases"]:
        key = (case["family"], case["stratum"])
        if key in seen:
            continue
        seen.add(key)
        chosen.append(case)
    # 12 family-by-stratum cells -> first case of each cell
    return chosen


def mode_calibrate(methods: list[str], conditions: list[str], stage: str) -> int:
    import trimesh  # noqa: F401

    subset = load_subset_manifest()
    actors = load_case_actors()
    gt_bboxes = load_json(WAVE_ROOT / "gt_bboxes.json")
    events = load_events()
    calib_cases = _calibration_cases(subset)
    calibration: dict = {"schema": "sppa-neural-external-wave-calibration-v1"}
    calibration["rule"] = (
        "frame convention selected once per method x condition on a fixed 12-case calibration subset "
        "(first case of each family-by-stratum cell), two passes: 48 discrete candidates (all signed "
        "axis permutations composed with the known render camera) at 32-cubed, shortlist top-8, then "
        "64-cubed final selection; frozen afterwards; no per-case tuning"
    )
    calibration["calibration_case_ids"] = [c["case_id"] for c in calib_cases]
    if CALIB_PATH.exists():
        calibration["choices"] = load_json(CALIB_PATH).get("choices", {})
    else:
        calibration["choices"] = {}

    for method in methods:
        out_dir = _method_out_dir(method)
        for condition in conditions:
            base = rotation_oblique() if condition == "oblique" else rotation_mask()
            key = f"{method}/{condition}"
            if stage == "coarse":
                cands = candidate_rotations(base)
                res_gt, res_mesh = 32, 32
                prev = calibration["choices"].get(key, {})
            else:
                prev = calibration["choices"].get(key, {})
                shortlist = prev.get("shortlist")
                if not shortlist:
                    raise RuntimeError(f"coarse stage missing for {key}")
                all_cands = candidate_rotations(base)
                cands = {name: all_cands[name] for name in shortlist}
                res_gt, res_mesh = 64, 64
            sums = {name: [] for name in cands}
            used = 0
            for case in calib_cases:
                label = f"{case['case_id']}__{condition}"
                ev = events.get((method, label))
                if not ev or ev.get("status") != "ok":
                    continue
                mesh_path = out_dir / label / f"{label}{METHOD_EXT[method]}"
                if not mesh_path.exists():
                    continue
                verts, faces = load_mesh(mesh_path)
                gt = voxelize_source(actors[case["case_id"]], res_gt)
                gt_bbox = gt_bboxes[case["case_id"]]
                for name, rot in cands.items():
                    v_aligned, _ = align_vertices(verts, rot, gt_bbox)
                    occ = voxelize_mesh(v_aligned, faces, res_mesh)
                    sums[name].append(binary_iou(gt, occ))
                used += 1
            means = {name: (float(np.mean(v)) if v else 0.0) for name, v in sums.items()}
            ranked = sorted(means, key=means.get, reverse=True)
            if stage == "coarse":
                calibration["choices"][key] = {
                    **prev,
                    "shortlist": ranked[:8],
                    "mean_iou_32_coarse_candidates": means,
                    "cases_used_coarse": used,
                }
                print(f"{key} coarse: top8 {ranked[:3]} ... best {means[ranked[0]]:.4f} over {used} cases")
            else:
                best = ranked[0]
                calibration["choices"][key] = {
                    **prev,
                    "chosen": best,
                    "mean_iou_64_chosen": means[best],
                    "mean_iou_64_shortlist": means,
                    "cases_used_fine": used,
                    "rotation_matrix": cands[best].round(9).tolist(),
                }
                print(f"{key} fine: chosen {best} meanIoU64={means[best]:.4f} over {used} cases")
    write_json(CALIB_PATH, calibration)
    print(f"wrote {CALIB_PATH}")
    return 0


def _gen_metrics(event: dict) -> dict:
    if event["model"] == "triposr_warm":
        generation_ms = (event.get("inference_sec", 0.0) + event.get("extract_sec", 0.0)) * 1000.0
        inference_ms = event.get("inference_sec", 0.0) * 1000.0
    else:
        generation_ms = event.get("generation_sec", 0.0) * 1000.0
        inference_ms = generation_ms
    return {
        "generation_ms": generation_ms,
        "inference_ms": inference_ms,
        "vram_peak_allocated_mb": event.get("torch_peak_allocated_mb"),
        "vram_peak_reserved_mb": event.get("torch_peak_reserved_mb"),
        "triangles": event.get("triangles"),
        "vertices": event.get("vertices"),
        "mesh_bytes": event.get("mesh_bytes"),
    }


def mode_eval(methods: list[str], conditions: list[str]) -> int:
    subset = load_subset_manifest()
    actors = load_case_actors()
    gt_bboxes = load_json(WAVE_ROOT / "gt_bboxes.json")
    events = load_events()
    calibration = load_json(CALIB_PATH)
    ROWS_DIR.mkdir(parents=True, exist_ok=True)

    for method in methods:
        out_dir = _method_out_dir(method)
        for condition in conditions:
            key = f"{method}/{condition}"
            choice = calibration["choices"][key]
            rot = np.asarray(choice["rotation_matrix"], dtype=np.float64)
            rows = []
            for case in subset["cases"]:
                label = f"{case['case_id']}__{condition}"
                ev = events.get((method, label))
                row = {
                    "case_id": case["case_id"],
                    "family": case["family"],
                    "stratum": case["stratum"],
                    "method": method,
                    "condition": condition,
                }
                if not ev or ev.get("status") != "ok":
                    row.update({"status": "excluded_hard_crash", "error": (ev or {}).get("error", "missing event")})
                    rows.append(row)
                    continue
                mesh_path = out_dir / label / f"{label}{METHOD_EXT[method]}"
                try:
                    verts, faces = load_mesh(mesh_path)
                    v_aligned, scale = align_vertices(verts, rot, gt_bboxes[case["case_id"]])
                    occ = voxelize_mesh(v_aligned, faces, 64)
                    gt64 = voxelize_source(actors[case["case_id"]], 64)
                    row.update(
                        {
                            "status": "ok",
                            "voxel_iou": binary_iou(gt64, occ),
                            "occupied_voxels": int(np.count_nonzero(occ)),
                            "alignment_scale": scale,
                            **_gen_metrics(ev),
                        }
                    )
                except Exception as exc:
                    row.update({"status": "excluded_hard_crash", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
                rows.append(row)
            out = ROWS_DIR / f"{method}_{condition}.json"
            write_json(out, {"schema": "sppa-neural-external-wave-rows-v1", "method": method, "condition": condition, "rows": rows})
            ok = [r for r in rows if r["status"] == "ok"]
            mean_iou = float(np.mean([r["voxel_iou"] for r in ok])) if ok else float("nan")
            print(f"{key}: ok={len(ok)}/{len(rows)} meanIoU64={mean_iou:.4f} -> {out}")
    return 0


def _sppa_context_rows() -> dict:
    rows: dict[str, dict] = {}
    with (RESULTS_TEST / "raw_metrics.csv").open("r", encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            if r["condition"] != "clean":
                continue
            rows.setdefault(r["case_id"], {})[r["method"]] = {
                "voxel_iou": float(r["voxel_iou"]),
                "inference_ms": float(r["inference_ms"]),
                "triangle_equiv": int(r["triangle_equiv"]),
                "descriptor_bytes": int(r["descriptor_bytes"]),
            }
    return rows


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(len(arr)),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def mode_aggregate(output_stem: str) -> int:
    subset = load_subset_manifest()
    context = _sppa_context_rows()
    calibration = load_json(CALIB_PATH)
    methods = [p.stem.rsplit("_", 1)[0] for p in ROWS_DIR.glob("*.json")]
    rows_by_mc: dict[tuple[str, str], list[dict]] = {}
    for path in ROWS_DIR.glob("*.json"):
        payload = load_json(path)
        rows_by_mc[(payload["method"], payload["condition"])] = payload["rows"]

    sppa_iou = {cid: context[cid]["sppa_mvfit"]["voxel_iou"] for cid in context if "sppa_mvfit" in context[cid]}

    aggregates: dict = {}
    for (method, condition), rows in sorted(rows_by_mc.items()):
        ok = [r for r in rows if r["status"] == "ok"]
        excl = [r for r in rows if r["status"] != "ok"]
        deltas = [r["voxel_iou"] - sppa_iou[r["case_id"]] for r in ok if r["case_id"] in sppa_iou]
        agg = {
            "n_cases": len(rows),
            "n_ok": len(ok),
            "n_excluded_hard_crash": len(excl),
            "excluded_cases": [{"case_id": r["case_id"], "error": r.get("error", "")} for r in excl],
            "voxel_iou": _stats([r["voxel_iou"] for r in ok]),
            "paired_delta_iou_vs_sppa_mvfit": _stats(deltas),
            "triangles": _stats([r["triangles"] for r in ok if r.get("triangles")]),
            "generation_ms": _stats([r["generation_ms"] for r in ok if r.get("generation_ms") is not None]),
            "vram_peak_allocated_mb": _stats([r["vram_peak_allocated_mb"] for r in ok if r.get("vram_peak_allocated_mb")]),
            "mesh_bytes": _stats([r["mesh_bytes"] for r in ok if r.get("mesh_bytes")]),
            "by_stratum": {},
        }
        for stratum in ("csg_id", "implicit_ood"):
            sub = [r for r in ok if r["stratum"] == stratum]
            sub_delta = [r["voxel_iou"] - sppa_iou[r["case_id"]] for r in sub if r["case_id"] in sppa_iou]
            agg["by_stratum"][stratum] = {
                "n_ok": len(sub),
                "voxel_iou": _stats([r["voxel_iou"] for r in sub]),
                "paired_delta_iou_vs_sppa_mvfit": _stats(sub_delta),
            }
        aggregates[f"{method}/{condition}"] = agg

    sppa_rows = [context[c["case_id"]]["sppa_mvfit"] for c in subset["cases"] if c["case_id"] in context]
    generic_rows = [context[c["case_id"]]["generic_mvfit"] for c in subset["cases"] if c["case_id"] in context]
    vh_rows = [context[c["case_id"]]["nonsemantic_visual_hull"] for c in subset["cases"] if c["case_id"] in context]
    sppa_summary = {
        "sppa_mvfit": {
            "voxel_iou": _stats([r["voxel_iou"] for r in sppa_rows]),
            "inference_ms": _stats([r["inference_ms"] for r in sppa_rows]),
            "triangle_equiv": _stats([r["triangle_equiv"] for r in sppa_rows]),
            "descriptor_bytes": _stats([r["descriptor_bytes"] for r in sppa_rows]),
        },
        "generic_mvfit": {
            "voxel_iou": _stats([r["voxel_iou"] for r in generic_rows]),
            "inference_ms": _stats([r["inference_ms"] for r in generic_rows]),
            "triangle_equiv": _stats([r["triangle_equiv"] for r in generic_rows]),
            "descriptor_bytes": _stats([r["descriptor_bytes"] for r in generic_rows]),
        },
        "nonsemantic_visual_hull": {
            "voxel_iou": _stats([r["voxel_iou"] for r in vh_rows]),
            "inference_ms": _stats([r["inference_ms"] for r in vh_rows]),
            "triangle_equiv": _stats([r["triangle_equiv"] for r in vh_rows]),
            "descriptor_bytes": _stats([r["descriptor_bytes"] for r in vh_rows]),
        },
    }

    environment = {
        "gpu": "NVIDIA GeForce RTX 5090 32 GB (torch cuda; nvidia-smi NVML unavailable this session)",
        "triposr": {"weights": "stabilityai/TripoSR", "mc_resolution": 128, "chunk_size": 4096, "venv": "_venvs/triposr"},
        "hunyuan3d_2mini_turbo": {"weights": "tencent/Hunyuan3D-2mini hunyuan3d-dit-v2-mini-turbo", "num_inference_steps": 5, "octree_resolution": 380, "num_chunks": 20000, "flashvdm": "enabled", "seed": 12345, "python": "system 3.12"},
    }
    if any(k.startswith("triposg/") for k in aggregates):
        environment["triposg"] = {
            "weights": "local VAST-AI/TripoSG 1.5B rectified flow (third_party/sota_3d_generators/TripoSG/pretrained_weights/TripoSG)",
            "num_inference_steps": 50,
            "guidance_scale": 7.0,
            "seed": 12345,
            "dtype": "float16",
            "preprocess": "input PNG as-is (RGB); no RMBG-1.4 / bbox crop, parity with the other wave runners; the official TripoSG script would additionally apply RMBG",
            "python": "system 3.12",
        }
    if any(k.startswith("hunyuan3d_2_full/") for k in aggregates):
        environment["hunyuan3d_2_full"] = {
            "weights": "tencent/Hunyuan3D-2 hunyuan3d-dit-v2-0 (+ hunyuan3d-vae-v2-0 via flashvdm)",
            "num_inference_steps": 50,
            "guidance_scale": 5.0,
            "octree_resolution": 380,
            "num_chunks": 20000,
            "flashvdm": "enabled",
            "seed": 12345,
            "python": "system 3.12",
        }

    result = {
        "schema": "sppa-neural-external-wave-v1",
        "amendment": "SPPA_PROTOCOL_AMENDMENT_05_20260717.md",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "status": "secondary descriptive analysis; does not alter sealed H1 or any sealed artifact",
        "output_stem": output_stem,
        "run_dir": str(RUN_DIR),
        "run_dirs": [str(d) for d in RUN_DIRS],
        "code_hashes": {
            p.name: sha256_file(p)
            for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
        },
        "environment": environment,
        "excluded_methods": EXCLUDED_METHODS,
        "alignment": calibration,
        "sppa_reference_rows_clean": sppa_summary,
        "aggregates": aggregates,
        "rows": {f"{m}/{c}": rows for (m, c), rows in sorted(rows_by_mc.items())},
    }
    out_json = RESULTS_ROOT / f"{output_stem}.json"
    write_json(out_json, result)
    print(f"wrote {out_json}")
    _write_md(result, RESULTS_ROOT / f"{output_stem}.md")
    _write_tex(result, RESULTS_ROOT / f"{output_stem}.tex")
    return 0


def _fmt(v: float | None, nd: int = 3) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    return f"{v:.{nd}f}"


def _fmt_int(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    return f"{int(round(v)):,}"


def _table_rows(result: dict) -> list[dict]:
    sppa = result["sppa_reference_rows_clean"]["sppa_mvfit"]
    generic = result["sppa_reference_rows_clean"]["generic_mvfit"]
    vh = result["sppa_reference_rows_clean"]["nonsemantic_visual_hull"]
    rows = [
        {
            "method": "SPPA-MVFit (ours)",
            "input": "top+side 96x96 telemetry masks",
            "iou": sppa["voxel_iou"]["mean"],
            "delta": 0.0,
            "triangles": sppa["triangle_equiv"]["mean"],
            "ms": sppa["inference_ms"]["mean"],
            "vram": None,
            "payload": sppa["descriptor_bytes"]["mean"],
        },
        {
            "method": "Generic-MVFit (context)",
            "input": "same masks",
            "iou": generic["voxel_iou"]["mean"],
            "delta": generic["voxel_iou"]["mean"] - sppa["voxel_iou"]["mean"],
            "triangles": generic["triangle_equiv"]["mean"],
            "ms": generic["inference_ms"]["mean"],
            "vram": None,
            "payload": generic["descriptor_bytes"]["mean"],
        },
        {
            "method": "Visual hull (context)",
            "input": "same masks",
            "iou": vh["voxel_iou"]["mean"],
            "delta": vh["voxel_iou"]["mean"] - sppa["voxel_iou"]["mean"],
            "triangles": vh["triangle_equiv"]["mean"],
            "ms": vh["inference_ms"]["mean"],
            "vram": None,
            "payload": vh["descriptor_bytes"]["mean"],
        },
    ]
    labels = {
        ("triposr", "oblique"): ("TripoSR (a)", "clean-crop shaded render"),
        ("triposr", "mask"): ("TripoSR (b)", "96x96 top mask"),
        ("hunyuan3d_2mini_turbo", "oblique"): ("Hunyuan3D-2mini-turbo (a)", "clean-crop shaded render"),
        ("hunyuan3d_2mini_turbo", "mask"): ("Hunyuan3D-2mini-turbo (b)", "96x96 top mask"),
        ("triposg", "oblique"): ("TripoSG (a)", "clean-crop shaded render"),
        ("triposg", "mask"): ("TripoSG (b)", "96x96 top mask"),
        ("hunyuan3d_2_full", "oblique"): ("Hunyuan3D-2 full (a)", "clean-crop shaded render"),
        ("hunyuan3d_2_full", "mask"): ("Hunyuan3D-2 full (b)", "96x96 top mask"),
    }
    for (method, condition), (name, inp) in labels.items():
        agg = result["aggregates"].get(f"{method}/{condition}")
        if not agg:
            continue
        rows.append(
            {
                "method": name,
                "input": inp,
                "iou": agg["voxel_iou"]["mean"],
                "delta": agg["paired_delta_iou_vs_sppa_mvfit"]["mean"],
                "triangles": agg["triangles"]["mean"],
                "ms": agg["generation_ms"]["mean"],
                "vram": agg["vram_peak_allocated_mb"]["mean"],
                "payload": agg["mesh_bytes"]["mean"],
            }
        )
    return rows


def _write_md(result: dict, out_path: Path) -> None:
    rows = _table_rows(result)
    title = "# SPPA external neural wave (Amendment 05) - measured results"
    if out_path.stem != "sppa_neural_external_wave":
        title = "# SPPA external neural wave (Amendment 05) - E12 flagship extension - measured results"
    lines = [
        title,
        "",
        f"Generated: {result['created_utc']} UTC. Secondary descriptive analysis; sealed H1 unchanged.",
        "",
        "Subset: 60 sealed held-out cases (6 families x 2 strata x 5, lexicographic).",
        "Alignment: frozen frame convention (48-candidate signed-permutation search on 12 disjoint calibration cases, coarse 32-cubed + fine 64-cubed passes), uniform scale to GT bbox, GT bbox center, GT yaw frame.",
        "Metrics: voxel IoU at 64-cubed (sealed voxelizer/grid), triangles, warm generation ms (model load excluded), peak CUDA VRAM, payload bytes.",
        "",
        "| Method | Input | IoU mean | dIoU vs SPPA | Triangles | Gen ms | VRAM MB | Payload B |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['method']} | {r['input']} | {_fmt(r['iou'])} | {_fmt(r['delta'], 3)} | "
            f"{_fmt_int(r['triangles'])} | {_fmt(r['ms'], 1)} | {_fmt_int(r['vram'])} | {_fmt_int(r['payload'])} |"
        )
    lines += [
        "",
        "## Hard-crash exclusions (reported, not silently dropped)",
        "",
    ]
    any_excl = False
    for key, agg in sorted(result["aggregates"].items()):
        for ex in agg["excluded_cases"]:
            lines.append(f"- {key}: {ex['case_id']} - {ex['error']}")
            any_excl = True
    if not any_excl:
        lines.append("- none")
    lines += ["", "## Method-level exclusions (environment)", ""]
    for ex in result["excluded_methods"]:
        lines.append(f"- {ex['method']}: {ex['reason']}")
    lines += [
        "",
        "## Stratum breakdown (mean IoU)",
        "",
        "| Method/condition | CSG-ID | implicit-OOD |",
        "|---|---:|---:|",
    ]
    for key, agg in sorted(result["aggregates"].items()):
        lines.append(
            f"| {key} | {_fmt(agg['by_stratum']['csg_id']['voxel_iou'].get('mean'))} | "
            f"{_fmt(agg['by_stratum']['implicit_ood']['voxel_iou'].get('mean'))} |"
        )
    lines += [
        "",
        "## Honesty boundaries (Amendment 05 E7)",
        "",
        "- Condition (a) gives neural generators richer input (clean shaded RGB) than the telemetry",
        "  masks SPPA consumes; condition (b) gives them input they were not trained for.",
        "  Neither is a leaderboard; the table measures an operating point (IoU vs triangles / ms / VRAM / payload).",
        "- Photoreal asset quality remains neural territory and is not claimed.",
        "- A visual beauty ranking against SOTA generators remains prohibited by the claim-evidence matrix.",
        "- SPPA-MVFit rows are the existing sealed clean-condition results on the same 60 cases (read-only).",
        "",
    ]
    out = out_path
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


def _write_tex(result: dict, out_path: Path) -> None:
    rows = _table_rows(result)
    lines = [
        "% Auto-generated by tools/neural_external_wave/step4_evaluate_wave.py (Amendment 05).",
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        "Method & Input & IoU & Triangles & Gen.\\ time (ms) & VRAM (MB) & Payload (B) \\\\",
        "\\midrule",
    ]
    for i, r in enumerate(rows):
        payload = _fmt_int(r["payload"])
        tex_method = r["method"].replace("_", "\\_")
        delta = "" if r["method"].startswith("SPPA") else f" ({'+' if (r['delta'] or 0) >= 0 else ''}{r['delta']:.3f})"
        lines.append(
            f"{tex_method} & {r['input']} & {_fmt(r['iou'])}{delta} & {_fmt_int(r['triangles'])} & "
            f"{_fmt(r['ms'], 1)} & {_fmt_int(r['vram'])} & {payload} \\\\"
        )
        if i == 2:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    out = out_path
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["selftest", "calibrate", "eval", "aggregate"])
    parser.add_argument("--methods", default="triposr,hunyuan3d_2mini_turbo")
    parser.add_argument("--conditions", default="oblique,mask")
    parser.add_argument("--stage", default="coarse", choices=["coarse", "fine"])
    parser.add_argument(
        "--output-stem",
        default="sppa_neural_external_wave",
        help="aggregate output file stem under benchmarks/results (E12 flagship extension: sppa_neural_flagship_wave)",
    )
    args = parser.parse_args()
    methods = [m for m in args.methods.split(",") if m]
    conditions = [c for c in args.conditions.split(",") if c]
    if args.mode == "selftest":
        return mode_selftest()
    if args.mode == "calibrate":
        return mode_calibrate(methods, conditions, args.stage)
    if args.mode == "eval":
        return mode_eval(methods, conditions)
    return mode_aggregate(args.output_stem)


if __name__ == "__main__":
    raise SystemExit(main())
