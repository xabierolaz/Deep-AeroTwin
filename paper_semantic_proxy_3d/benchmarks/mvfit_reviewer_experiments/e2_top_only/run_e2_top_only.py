"""E2 - View ablation: top-only / side-only fitting (exploratory post-hoc).

Replicates the frozen coordinate-descent loop of method.sppa_mvfit.fit_graph
(same STEP_FRACTIONS, same parameter order, same tie-break, 31 candidates)
with two changes per arm:

  top-only : objective = (1 - IoU_top) + regularizer   (side weight 0)
             init from the TOP mask only; z scale from an isotropic prior:
             log_scale_z = 0.5 * (log_scale_x + log_scale_y)  [documented]
  side-only: objective = (1 - IoU_side) + regularizer  (top weight 0)
             init from the SIDE mask only; y scale isotropic:
             log_scale_y = 0.5 * (log_scale_x + log_scale_z)

The regularizer is the frozen one (same formula as objective()). The correct
family token is used (this ablates VIEWS, not priors). n = 240 actors, clean.
Dual-view control is recomputed through the sealed infer_method and validated
bit-exactly against results/test/raw_metrics.csv.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, GtCache, bootstrap_paired, clean_view_masks, f3, load_masks,
    load_public_cases, load_sealed_clean_ious, mv, pooled_mean, voxel_iou,
    write_json, write_text, EXPLORATORY_LABEL,
)

OUT = EXPERIMENTS_ROOT / "e2_top_only"


def regularizer(theta: np.ndarray) -> float:
    return 0.01 * float(np.sum(theta[:3] ** 2)) + 0.005 * float((theta[3] - 1.0) ** 2) + 0.005 * float(theta[4] ** 2)


def init_single_view(graph_name: str, mask: np.ndarray, view: str) -> tuple[np.ndarray, bool]:
    """initialize_theta restricted to one view; missing axis gets the
    isotropic prior = geometric mean of the two observed scale ratios."""
    axis_uv = ("x", "y") if view == "top" else ("x", "z")
    extent = mv._mask_extent(mask, *axis_uv)
    if extent is None:
        return mv.default_theta(), True
    default_actor = mv.build_actor(graph_name, mv.default_theta())
    default_top, default_side = mv.render_actor_masks(default_actor, mask.shape[0])
    default_extent = mv._mask_extent(default_top if view == "top" else default_side, *axis_uv)
    if default_extent is None:
        raise RuntimeError("frozen graph has empty default projection")
    ratio_u = extent[2] / max(default_extent[2], 1e-9)
    ratio_v = extent[3] / max(default_extent[3], 1e-9)
    ratio_iso = float(np.sqrt(ratio_u * ratio_v))  # isotropic prior for the unobserved axis
    if view == "top":
        ratios = [ratio_u, ratio_v, ratio_iso]
    else:
        ratios = [ratio_u, ratio_iso, ratio_v]
    theta = mv.default_theta()
    theta[:3] = np.log(np.clip(ratios, np.exp(mv.BOUNDS[:3, 0]), np.exp(mv.BOUNDS[:3, 1])))
    return theta, False


def objective_single_view(graph_name: str, theta: np.ndarray, mask: np.ndarray, view: str) -> tuple[float, dict[str, float]]:
    actor = mv.build_actor(graph_name, theta)
    top_pred, side_pred = mv.render_actor_masks(actor, mask.shape[0])
    view_iou = mv._iou2d(top_pred if view == "top" else side_pred, mask)
    reg = regularizer(theta)
    return (1.0 - view_iou) + reg, {"view_iou": view_iou, "regularizer": reg}


def fit_single_view(graph_name: str, mask: np.ndarray, view: str) -> dict:
    """Line-by-line replica of fit_graph restricted to one view (31 evals)."""
    theta, empty = init_single_view(graph_name, mask, view)
    value, details = objective_single_view(graph_name, theta, mask, view)
    evaluations = 1
    spans = mv.BOUNDS[:, 1] - mv.BOUNDS[:, 0]
    for fraction in mv.STEP_FRACTIONS:
        for parameter_index in range(len(mv.PARAMETER_NAMES)):
            candidates = [(value, details, theta.copy())]
            for direction in (-1.0, 1.0):
                proposal = theta.copy()
                proposal[parameter_index] = np.clip(
                    proposal[parameter_index] + direction * fraction * spans[parameter_index],
                    mv.BOUNDS[parameter_index, 0], mv.BOUNDS[parameter_index, 1])
                proposal_value, proposal_details = objective_single_view(graph_name, proposal, mask, view)
                evaluations += 1
                candidates.append((proposal_value, proposal_details, proposal))
            value, details, theta = min(candidates, key=lambda item: mv._candidate_key(item[0], item[1], item[2]))
    if evaluations != 31:
        raise AssertionError(f"candidate budget drift: {evaluations}")
    return {"theta": theta.tolist(), "objective": value, "empty_observation": empty,
            "actor": mv.build_actor(graph_name, theta)}


def main() -> int:
    cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()

    iou_dual: dict[str, float] = {}
    iou_top: dict[str, float] = {}
    iou_side: dict[str, float] = {}
    t0 = time.perf_counter()
    for case_index, case in enumerate(cases):
        cid = case["case_id"]
        top, side = clean_view_masks(masks, case_index)
        gt_vox = gt.voxels(cid)
        dual = mv.infer_method("sppa_mvfit", case["family"], top, side)
        iou_dual[cid] = voxel_iou(gt_vox, mv.voxelize_actor(dual["actor"], 64))
        top_fit = fit_single_view(case["family"], top, "top")
        iou_top[cid] = voxel_iou(gt_vox, mv.voxelize_actor(top_fit["actor"], 64))
        side_fit = fit_single_view(case["family"], side, "side")
        iou_side[cid] = voxel_iou(gt_vox, mv.voxelize_actor(side_fit["actor"], 64))
    seconds = time.perf_counter() - t0

    max_err = max(abs(iou_dual[c["case_id"]] - sealed[(c["case_id"], "sppa_mvfit")]) for c in cases)
    if max_err > 1e-12:
        raise RuntimeError(f"dual-view control drifts from seal: {max_err}")

    pooled = {
        "dual_view": pooled_mean(list(iou_dual.values())),
        "top_only": pooled_mean(list(iou_top.values())),
        "side_only": pooled_mean(list(iou_side.values())),
    }
    paired = {
        "top_only_minus_dual": bootstrap_paired(cases, {cid: iou_top[cid] - iou_dual[cid] for cid in iou_dual}),
        "side_only_minus_dual": bootstrap_paired(cases, {cid: iou_side[cid] - iou_dual[cid] for cid in iou_dual}),
        "top_only_minus_side_only": bootstrap_paired(cases, {cid: iou_top[cid] - iou_side[cid] for cid in iou_dual}),
    }
    per_stratum: dict[str, dict] = {}
    for stratum in ("csg_id", "implicit_ood"):
        ids = [c["case_id"] for c in cases if c["stratum"] == stratum]
        per_stratum[stratum] = {
            "n": len(ids),
            "dual_view": pooled_mean([iou_dual[i] for i in ids]),
            "top_only": pooled_mean([iou_top[i] for i in ids]),
            "side_only": pooled_mean([iou_side[i] for i in ids]),
        }
    per_family: dict[str, dict] = {}
    for family in sorted({c["family"] for c in cases}):
        ids = [c["case_id"] for c in cases if c["family"] == family]
        per_family[family] = {
            "n": len(ids),
            "dual_view": pooled_mean([iou_dual[i] for i in ids]),
            "top_only": pooled_mean([iou_top[i] for i in ids]),
            "side_only": pooled_mean([iou_side[i] for i in ids]),
        }

    def row(name: str, value: float, diff: dict | None) -> str:
        if diff is None:
            return f"{name} & {f3(value)} & --- & --- & --- \\\\"
        return (f"{name} & {f3(value)} & {f3(diff['mean_difference'])} & "
                f"{f3(diff['ci95_low'])} & {f3(diff['ci95_high'])} \\\\")

    mc_open = "\\multicolumn{5}{@{}l}{"
    lines = [
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "Fit variant & Mean IoU & $\\Delta$ vs dual & CI95 low & CI95 high \\\\",
        "\\midrule",
        row("Dual-view (sealed SPPA-MVFit)", pooled["dual_view"], None),
        row("Top-only fit", pooled["top_only"], paired["top_only_minus_dual"]),
        row("Side-only fit", pooled["side_only"], paired["side_only_minus_dual"]),
        "\\midrule",
        mc_open + "Stratum csg\\_id: dual " + f3(per_stratum["csg_id"]["dual_view"])
        + ", top-only " + f3(per_stratum["csg_id"]["top_only"])
        + ", side-only " + f3(per_stratum["csg_id"]["side_only"]) + "} \\\\",
        mc_open + "Stratum implicit\\_ood: dual " + f3(per_stratum["implicit_ood"]["dual_view"])
        + ", top-only " + f3(per_stratum["implicit_ood"]["top_only"])
        + ", side-only " + f3(per_stratum["implicit_ood"]["side_only"]) + "} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "top_only_ablation_table.tex", "\n".join(lines))

    payload = {
        "experiment": "E2 top-only / side-only view ablation",
        "label": EXPLORATORY_LABEL,
        "n_actors": len(cases),
        "condition": "clean",
        "metric": "voxel_iou_64cubed",
        "fit_seconds_wallclock": seconds,
        "seal_validation": {"dual_control_max_abs_err": max_err},
        "design": {
            "objective_top_only": "(1 - IoU_top) + regularizer; side term weight 0",
            "objective_side_only": "(1 - IoU_side) + regularizer; top term weight 0",
            "init_unobserved_axis": "isotropic prior: log scale = mean of the two observed log scale ratios",
            "optimizer": "frozen coordinate descent, 31 candidates, correct family token",
        },
        "pooled_means": pooled,
        "paired_bootstrap": paired,
        "per_stratum": per_stratum,
        "per_family": per_family,
        "protocol": {"bootstrap_resamples": 10000, "bootstrap_seed": 77157},
    }
    write_json(OUT / "top_only_ablation.json", payload)

    print(f"dual={pooled['dual_view']:.4f} top={pooled['top_only']:.4f} side={pooled['side_only']:.4f} ({seconds:.1f}s)")
    for name, diff in paired.items():
        print(f"{name}: {diff['mean_difference']:.4f} [{diff['ci95_low']:.4f}, {diff['ci95_high']:.4f}] p={diff['null_centered_two_sided_p']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
