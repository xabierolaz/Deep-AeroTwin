# external sanity check (exploratory, post-hoc)
"""Evaluate frozen SPPA-MVFit methods + baselines on the external real-mesh cases.

Methods are imported from the sealed package (never modified, never re-run as scripts):
- infer_method: sppa_mvfit / generic_mvfit / sppa_text_only
- baseline_occupancy: bbox / ellipsoid / capsule / billboard / nonsemantic_visual_hull
- benchmark.metrics.voxel_iou

Conditions: clean (primary) and mild_morphology (robustness probe; the _morph and
case_seed operators are re-implemented verbatim from the sealed run_benchmark.py —
that module cannot be imported because it requires a .git checkout at import time).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from download_meshes import stable_jitter

from benchmark.metrics import voxel_iou
from method.sppa_mvfit import baseline_occupancy, infer_method, voxelize_actor

RESULTS_JSONL = common.RESULTS_DIR / "results.jsonl"
ACTOR_METHODS = ("sppa_mvfit", "generic_mvfit", "sppa_text_only")
BASELINE_METHODS = ("bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull")
METHODS = ACTOR_METHODS + BASELINE_METHODS
ROBUSTNESS_METHODS = ("sppa_mvfit", "generic_mvfit")


def case_seed(base_seed: int, *labels: str) -> int:
    payload = f"{base_seed}|" + "|".join(labels)
    return int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")


def _morph(mask: np.ndarray, seed: int, iterations: int = 1) -> np.ndarray:
    if seed % 2:
        return ndimage.binary_dilation(mask, structure=np.ones((3, 3), dtype=bool), iterations=iterations)
    return ndimage.binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), iterations=iterations, border_value=0)


def mild_condition(top: np.ndarray, side: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    return (
        _morph(top, case_seed(seed, "mild", "0")),
        _morph(side, case_seed(seed, "mild", "1")),
    )


def run_method(method: str, family: str, top: np.ndarray, side: np.ndarray) -> tuple[np.ndarray, float, dict]:
    start = time.perf_counter()
    if method in ACTOR_METHODS:
        result = infer_method(method, family, top, side)
        occupancy = voxelize_actor(result["actor"], 64)
        extra = {"top_iou_2d": result.get("top_iou"), "side_iou_2d": result.get("side_iou")}
    else:
        occupancy, _ = baseline_occupancy(method, top, side, 64)
        extra = {}
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return occupancy, elapsed_ms, extra


def main() -> int:
    manifest = common.load_manifest()
    selection = manifest.get("final_selection")
    if not selection:
        raise RuntimeError("final_selection missing - run selection first")
    done = manifest.setdefault("evaluations", {})
    out_rows: list[dict] = []
    t0 = time.time()
    n_total = 0
    for family, case_ids in selection.items():
        for case_id in case_ids:
            data = np.load(common.CASES_DIR / f"{case_id}.npz")
            top, side, gt = data["top"], data["side"], data["gt"]
            case_done = done.setdefault(case_id, {})
            for condition in ("clean", "mild_morphology"):
                if condition in case_done:
                    continue
                if condition == "clean":
                    ctop, cside = top, side
                else:
                    ctop, cside = mild_condition(top, side, stable_jitter(case_id))
                methods = METHODS if condition == "clean" else ROBUSTNESS_METHODS
                for method in methods:
                    occupancy, elapsed_ms, extra = run_method(method, family, ctop, cside)
                    row = {
                        "case_id": case_id,
                        "family": family,
                        "condition": condition,
                        "method": method,
                        "voxel_iou": float(voxel_iou(gt, occupancy)),
                        "inference_ms": elapsed_ms,
                        "gt_voxels": int(gt.sum()),
                        "pred_voxels": int(occupancy.sum()),
                        **extra,
                    }
                    out_rows.append(row)
                    n_total += 1
            case_done["clean"] = True
            case_done["mild_morphology"] = True
            common.save_manifest(manifest)
            print(f"{case_id} done ({time.time()-t0:.1f}s)", flush=True)
    with RESULTS_JSONL.open("a", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row) + "\n")
    manifest["steps"]["evaluate"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    common.log_note(manifest, f"evaluation finished: {n_total} new runs appended to results.jsonl")
    common.save_manifest(manifest)
    print(f"total new runs: {n_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
