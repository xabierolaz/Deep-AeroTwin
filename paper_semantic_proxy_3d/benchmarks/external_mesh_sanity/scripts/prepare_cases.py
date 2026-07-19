# external sanity check (exploratory, post-hoc)
"""Prepare cases: load -> orient -> scale/place -> masks 96x96 -> GT voxels 64^3.

Checkpoint-safe: skips cases already 'prepared' in manifest unless --force or the
case appears in orientation_overrides.json (then it is recomputed).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import mesh_lib

OVERRIDES_PATH = common.OUTPUT_ROOT / "orientation_overrides.json"

BASE_ROT_BY_SOURCE = {
    "modelnet40": "identity",  # ModelNet40 OFF is already z-up (verified by QC probes)
    "objaverse": "yup",  # glTF +Y up (verified by QC probes)
}


def load_overrides() -> dict:
    if OVERRIDES_PATH.exists():
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {}


def base_rot(name: str) -> np.ndarray:
    if name == "identity":
        return np.eye(3)
    if name == "yup":
        return mesh_lib.rot_about_x(90.0)
    if name == "negyup":
        return mesh_lib.rot_about_x(-90.0)
    raise ValueError(name)


def qc_figure(case_id: str, top: np.ndarray, side: np.ndarray, gt: np.ndarray, out: Path, extra: str = "") -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7, 7))
    gt_top = np.kron(gt.any(axis=2), np.ones((2, 2), dtype=bool))[:96, :96]
    gt_side = np.kron(gt.any(axis=1), np.ones((2, 2), dtype=bool))[:96, :96]
    for ax, mask, title in (
        (axes[0, 0], top, "observed top [x,y]"),
        (axes[0, 1], side, "observed side [x,z]"),
        (axes[1, 0], gt_top, "GT64 top proj"),
        (axes[1, 1], gt_side, "GT64 side proj"),
    ):
        ax.imshow(mask.T, origin="lower", cmap="gray", interpolation="nearest")
        ax.set_title(title, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"{case_id} {extra}", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


def prepare_case(cand: dict, overrides: dict, manifest: dict, force: bool = False) -> bool:
    case_id = cand["case_id"]
    mesh_path = common.OUTPUT_ROOT / cand["mesh_relpath"]
    npz_path = common.CASES_DIR / f"{case_id}.npz"
    meta_path = common.CASES_DIR / f"{case_id}_meta.json"
    qc_path = common.QC_DIR / f"{case_id}.png"
    ov = overrides.get(case_id, {})
    if npz_path.exists() and not force and not ov:
        return True  # checkpoint: already prepared
    try:
        mesh = mesh_lib.load_mesh(mesh_path)
        rot_name = ov.get("base", BASE_ROT_BY_SOURCE[cand["source"]])
        rot = base_rot(rot_name)
        yaw_overrides = list(ov.get("yaw_deg", []))
        mesh, oinfo = mesh_lib.apply_orientation(mesh, rot, not ov.get("disable_pca", False), yaw_overrides)
        if ov.get("flip_z"):
            flip = mesh_lib.rot_about_x(180.0)
            mesh.apply_transform(np.vstack([np.hstack([flip, np.zeros((3, 1))]), [0, 0, 0, 1]]))
        ref_axis, target = common.SCALE_CRITERIA[cand["external_class"]]
        mesh, sinfo = mesh_lib.normalize_scale_place(mesh, ref_axis, target)
        top, side = mesh_lib.render_masks(mesh)
        gt, vinfo = mesh_lib.voxelize_gt_v2(mesh)
    except Exception as exc:  # noqa: BLE001
        cand["status"] = "prepare_failed"
        cand["reject_reason"] = str(exc)[:300]
        common.log_note(manifest, f"prepare failed {case_id}: {exc}")
        return False

    # sanity checks
    problems = []
    if top.sum() < 10:
        problems.append("top mask nearly empty")
    if side.sum() < 10:
        problems.append("side mask nearly empty")
    if gt.sum() < 20:
        problems.append("GT occupancy nearly empty")
    boundary = np.zeros_like(gt)
    boundary[[0, -1], :, :] = True
    boundary[:, [0, -1], :] = True
    boundary[:, :, -1] = True
    if bool((gt & boundary).any()):
        problems.append("GT touches world boundary (clipped)")
    extents = mesh.extents
    if extents[0] > 9.6 or extents[1] > 6.4 or extents[2] > 6.4:
        problems.append(f"extents exceed world: {extents.round(2)}")

    meta = {
        "case_id": case_id,
        "family": cand["family"],
        "source": cand["source"],
        "external_class": cand["external_class"],
        "uid": cand.get("uid"),
        "mesh_relpath": cand["mesh_relpath"],
        "orientation": {**oinfo, "base": rot_name, "overrides": ov},
        "scale": sinfo,
        "voxelization": vinfo,
        "faces": int(len(mesh.faces)),
        "vertices": int(len(mesh.vertices)),
        "mask_fill_top": float(top.mean()),
        "mask_fill_side": float(side.mean()),
        "gt_fill": float(gt.mean()),
        "sanity_problems": problems,
    }
    np.savez_compressed(npz_path, top=top, side=side, gt=gt)
    meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    # save normalized mesh for qualitative renders
    norm_obj = common.CASES_DIR / f"{case_id}_norm.obj"
    mesh.export(norm_obj)
    qc_figure(case_id, top, side, gt, qc_path, extra=f"ext={extents.round(2)}m")
    cand["status"] = "prepared"
    cand["sanity_problems"] = problems
    manifest["cases"][case_id] = {
        "npz": str(npz_path.relative_to(common.OUTPUT_ROOT)),
        "meta": str(meta_path.relative_to(common.OUTPUT_ROOT)),
        "qc_png": str(qc_path.relative_to(common.OUTPUT_ROOT)),
        "gt_fill": float(gt.mean()),
        "problems": problems,
    }
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = common.load_manifest()
    overrides = load_overrides()
    todo = [c for c in manifest["candidates"] if c["status"] in {"downloaded", "prepared", "prepare_failed"}]
    # skip cases that were explicitly rejected in QC
    todo = [c for c in todo if c["status"] != "rejected"]
    n_ok = 0
    t0 = time.time()
    for i, cand in enumerate(todo):
        ok = prepare_case(cand, overrides, manifest, force=args.force)
        n_ok += int(ok)
        common.save_manifest(manifest)
        print(f"[{i+1}/{len(todo)}] {cand['case_id']} {'OK' if ok else 'FAIL'} ({time.time()-t0:.1f}s)")
    manifest["steps"]["prepare"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    common.save_manifest(manifest)
    print(f"prepared {n_ok}/{len(todo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
