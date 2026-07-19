"""E7 debug: reproduce the correct-token refit arm on one wrong-token case."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

E7_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(E7_ROOT))
from e7_common import CLASS_TO_FAMILY, iter_cases, load_gt_static, match_gt, mv, scaled_graphs_for_family  # noqa
from run_e7_real_stream import case_window, rasterize_masks, run_method, reprojection_iou  # noqa


def main() -> None:
    cases, _ = iter_cases()
    gt = load_gt_static()
    # find first wrong-token matched case
    target = None
    for case in cases:
        m = match_gt(case, gt)
        if m is not None and m["cls"] != case["det_class"]:
            target = (case, m)
            break
    case, m = target
    print("case:", case["case_id"], case["det_class"], "-> gt:", m["label"], m["cls"],
          f"match_d={m['match_distance_m']:.1f} m, conf={case['confidence']:.2f}")
    fp = case["footprint"]
    print(f"footprint: len={fp['length_m']:.2f} wid={fp['width_m']:.2f} height_est={case['height_m']:.2f} "
          f"base_dist={case['base_distance_m']:.1f} alt_agl={case['telemetry']['alt_agl']:.1f}")
    print("bbox:", case["bbox"])
    bearing = math.radians(fp["orientation_deg_axial"])

    for family in (case["family"], CLASS_TO_FAMILY[m["cls"]]):
        mv.GRAPHS = scaled_graphs_for_family(family)
        window = case_window(fp["length_m"], fp["width_m"], case["height_m"], family)
        mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}
        top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], case["height_m"])
        occ = run_method("sppa_mvfit", family, top, side, window, case["height_m"], case, bearing)
        ri = reprojection_iou(occ, window, case, bearing)
        idx = np.argwhere(occ)
        print(f"\nfamily={family}: window x={window['x']} z={window['z']}")
        print(f"  voxels={len(idx)} reproj_iou={ri:.4f}")
        if len(idx):
            from run_e7_real_stream import cell_centers
            from e7_common import EVAL_RES
            zs = cell_centers(window["z"], EVAL_RES)
            xs = cell_centers(window["x"], EVAL_RES)
            print(f"  occ x range: {xs[idx[:,0]].min():.1f}..{xs[idx[:,0]].max():.1f} m")
            print(f"  occ z range: {zs[idx[:,2]].min():.1f}..{zs[idx[:,2]].max():.1f} m")


if __name__ == "__main__":
    main()
