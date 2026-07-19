# external sanity check (exploratory, post-hoc)
"""Re-voxelize GT for all prepared cases with voxelize_gt_v2 (splat+parity+closing).
Masks are unchanged; only GT occupancy is recomputed from the saved normalized mesh.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import mesh_lib
from prepare_cases import qc_figure


def main() -> int:
    manifest = common.load_manifest()
    case_ids = sorted(manifest["cases"].keys())
    t0 = time.time()
    for i, case_id in enumerate(case_ids):
        if "gt_fill_v3" in manifest["cases"][case_id]:
            continue  # checkpoint: already re-voxelized with the fine-splat pipeline
        npz_path = common.CASES_DIR / f"{case_id}.npz"
        norm_obj = common.CASES_DIR / f"{case_id}_norm.obj"
        data = np.load(npz_path)
        top, side = data["top"], data["side"]
        mesh = mesh_lib.load_mesh(norm_obj)
        gt, info = mesh_lib.voxelize_gt_v2(mesh)
        np.savez_compressed(npz_path, top=top, side=side, gt=gt)
        meta_path = common.CASES_DIR / f"{case_id}_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["voxelization_v3"] = info
        meta["gt_fill_v3"] = float(gt.mean())
        problems = []
        if gt.sum() < 20:
            problems.append("GT v3 nearly empty")
        boundary = np.zeros_like(gt)
        boundary[[0, -1], :, :] = True
        boundary[:, [0, -1], :] = True
        boundary[:, :, -1] = True
        if bool((gt & boundary).any()):
            problems.append("GT v3 touches world boundary")
        meta["sanity_problems_v3"] = problems
        meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        qc_figure(case_id, top, side, gt, common.QC_DIR / f"{case_id}.png", extra=f"ext={meta['scale']['final_extents_m']}")
        manifest["cases"][case_id]["gt_fill_v3"] = float(gt.mean())
        manifest["cases"][case_id]["problems_v3"] = problems
        common.save_manifest(manifest)
        print(f"[{i+1}/{len(case_ids)}] {case_id} gt_fill={gt.mean():.4f} parity={info['parity_only_voxels']} splat={info['splat_voxels']} ({time.time()-t0:.0f}s)", flush=True)
    common.log_note(manifest, "GT re-voxelized with v3 = closing(fine_surface_splat U parity), masks unchanged")
    common.save_manifest(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
