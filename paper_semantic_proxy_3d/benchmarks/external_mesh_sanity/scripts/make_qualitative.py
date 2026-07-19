# external sanity check (exploratory, post-hoc)
"""Qualitative figures: observed masks vs fitted SPPA actor render vs GT voxel projections."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

from method.sppa_mvfit import infer_method, render_actor_masks

PICKS = [
    "ext-compact_vehicle-modelnet40-car-00",
    "ext-articulated_vehicle-objaverse-trailer_truck-02",
    "ext-articulated_vehicle-objaverse-bus_(vehicle)-03",
    "ext-quadruped-objaverse-horse-00",
    "ext-quadruped-objaverse-horse-02",
    "ext-branching_vertical-objaverse-Christmas_tree-01",
    "ext-branching_vertical-modelnet40-plant-00",
    "ext-lattice_tower-objaverse-water_tower-02",
    "ext-lattice_tower-objaverse-clock_tower-01",
    "ext-rider_cycle-objaverse-bicycle-00",
    "ext-rider_cycle-objaverse-motorcycle-00",
    "ext-quadruped-objaverse-cow-00",
]


def main() -> int:
    out_dir = common.OUTPUT_ROOT / "qualitative"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (common.RESULTS_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    clean = {(r["case_id"], r["method"]): r["voxel_iou"] for r in rows if r["condition"] == "clean"}
    manifest = common.load_manifest()
    selection = manifest["final_selection"]
    fam_of = {cid: fam for fam, ids in selection.items() for cid in ids}
    available = set(fam_of)
    picks = [p for p in PICKS if p in available]
    if len(picks) < 6:  # fallback: first case per family
        picks = [ids[0] for ids in selection.values()]
    for cid in picks:
        fam = fam_of[cid]
        data = np.load(common.CASES_DIR / f"{cid}.npz")
        top, side, gt = data["top"], data["side"], data["gt"]
        actor = infer_method("sppa_mvfit", fam, top, side)["actor"]
        at, asd = render_actor_masks(actor, 96)
        gt_top = gt.any(axis=2)
        gt_side = gt.any(axis=1)
        iou_sppa = clean.get((cid, "sppa_mvfit"), float("nan"))
        iou_gen = clean.get((cid, "generic_mvfit"), float("nan"))
        iou_vh = clean.get((cid, "nonsemantic_visual_hull"), float("nan"))
        fig, axes = plt.subplots(2, 3, figsize=(9.0, 6.0))
        panels = [(top, "observed top"), (side, "observed side"),
                  (at, "SPPA actor top"), (asd, "SPPA actor side"),
                  (gt_top, "GT vox top proj"), (gt_side, "GT vox side proj")]
        for ax, (img, title) in zip(axes.ravel(), panels):
            ax.imshow(np.asarray(img), cmap="gray", interpolation="nearest")
            ax.set_title(title, fontsize=8)
            ax.axis("off")
        short = cid.replace("ext-", "")
        fig.suptitle(
            f"{short} [{fam}]\nIoU: SPPA {iou_sppa:.3f} | generic {iou_gen:.3f} | visual hull {iou_vh:.3f}",
            fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.90))
        out = out_dir / f"{short}.png"
        fig.savefig(out, dpi=110)
        plt.close(fig)
        print(f"  wrote qualitative/{out.name}", flush=True)
    manifest["steps"]["qualitative"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    common.save_manifest(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
