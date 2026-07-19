"""E5 - Generic-graph sensitivity (exploratory post-hoc, not confirmatory).

Design criteria are frozen in GENERIC_VARIANTS.md BEFORE measurement; the
variant graphs live in generic_variants.json in THIS folder (the sealed
method/graphs.json is never modified).

Monkeypatch (documented): build_actor / initialize_theta / fit_graph all read
the module-level GRAPHS dict at call time, so assigning
    mv.GRAPHS["generic"] = <variant slots>
inside a try/finally (restoring the original entry) swaps the generic graph
in memory only. Nothing on disk changes.

Arms (n = 240 actors each, clean condition):
  G1 control   : sealed generic graph, recomputed and validated bit-exactly
                 against results/test/raw_metrics.csv (generic_mvfit rows).
  G2           : box/cylinder chassis (mechanical-object generic).
  G3           : vertical ellipsoid stack + box legs (organic-object generic).
  G4           : slot-wise mean of the six family graphs (rule in
                 GENERIC_VARIANTS.md); the runner re-derives it from the
                 sealed family graphs and aborts if the JSON drifts from the
                 rule.

Report: mean voxel IoU per variant, Delta vs sealed SPPA per-case IoUs,
paired bootstrap CIs (10 000 resamples, seed 77157), and how much of the
sealed Delta = 0.190 (SPPA - generic) each variant closes.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, FAMILIES, GtCache, bootstrap_paired, clean_view_masks, f3,
    load_masks, load_public_cases, load_sealed_clean_ious, mv, pooled_mean,
    voxel_iou, write_json, write_text, EXPLORATORY_LABEL,
)

OUT = EXPERIMENTS_ROOT / "e5_generic_variants"


def derive_g4_rule() -> list[dict]:
    """Re-derive G4 from the sealed family graphs per GENERIC_VARIANTS.md."""
    global_counts: Counter = Counter()
    for family in FAMILIES:
        for slot in mv.GRAPHS[family]:
            global_counts[slot["type"]] += 1
    tie_order = [t for t, _ in global_counts.most_common()]
    derived: list[dict] = []
    for index in range(8):
        slots = [mv.GRAPHS[family][index] for family in FAMILIES]
        types = Counter(s["type"] for s in slots)
        top = max(types.values())
        tied = [t for t, c in types.items() if c == top]
        kind = tied[0] if len(tied) == 1 else next(t for t in tie_order if t in tied)
        axis = Counter(s.get("axis", "z") for s in slots).most_common(1)[0][0]
        secondary = Counter(bool(s["secondary"]) for s in slots).most_common(1)[0][0]
        center = np.mean([s["center"] for s in slots], axis=0)
        size = np.mean([s["size"] for s in slots], axis=0)
        derived.append({"type": kind, "axis": axis, "secondary": secondary,
                        "center": [round(float(v), 4) for v in center],
                        "size": [round(float(v), 4) for v in size]})
    return derived


def fit_with_generic(slots: list[dict], cases, masks, gt) -> dict[str, float]:
    original = mv.GRAPHS["generic"]
    mv.GRAPHS["generic"] = slots
    try:
        ious: dict[str, float] = {}
        for case_index, case in enumerate(cases):
            top, side = clean_view_masks(masks, case_index)
            result = mv.fit_graph("generic", top, side)
            ious[case["case_id"]] = voxel_iou(gt.voxels(case["case_id"]), mv.voxelize_actor(result["actor"], 64))
        return ious
    finally:
        mv.GRAPHS["generic"] = original


def main() -> int:
    variants = json.loads((OUT / "generic_variants.json").read_text(encoding="utf-8"))["variants"]
    g4_check = derive_g4_rule()
    if g4_check != variants["G4_slotwise_family_mean"]:
        raise RuntimeError("generic_variants.json G4 drifts from the documented derivation rule")

    cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()
    sppa_iou = {c["case_id"]: sealed[(c["case_id"], "sppa_mvfit")] for c in cases}

    t0 = time.perf_counter()
    results: dict[str, dict[str, float]] = {}
    results["G1_sealed_generic"] = fit_with_generic(mv.GRAPHS["generic"], cases, masks, gt)
    max_err = max(abs(results["G1_sealed_generic"][c["case_id"]] - sealed[(c["case_id"], "generic_mvfit")]) for c in cases)
    if max_err > 1e-12:
        raise RuntimeError(f"G1 control drifts from seal: {max_err}")
    for name in ("G2_box_cylinder_chassis", "G3_vertical_stack_legs", "G4_slotwise_family_mean"):
        results[name] = fit_with_generic(variants[name], cases, masks, gt)
    seconds = time.perf_counter() - t0

    sppa_mean = pooled_mean(list(sppa_iou.values()))
    sealed_delta = sppa_mean - pooled_mean(list(results["G1_sealed_generic"].values()))

    arms: dict[str, dict] = {}
    for name, ious in results.items():
        mean = pooled_mean(list(ious.values()))
        arms[name] = {
            "mean_iou": mean,
            "delta_sppa_minus_variant": sppa_mean - mean,
            "gap_closure_vs_sealed_generic": (mean - pooled_mean(list(results["G1_sealed_generic"].values()))) / sealed_delta,
            "variant_minus_G1": bootstrap_paired(
                cases, {c["case_id"]: ious[c["case_id"]] - results["G1_sealed_generic"][c["case_id"]] for c in cases}),
            "sppa_minus_variant": bootstrap_paired(
                cases, {c["case_id"]: sppa_iou[c["case_id"]] - ious[c["case_id"]] for c in cases}),
        }
    per_family: dict[str, dict] = {}
    for family in FAMILIES:
        ids = [c["case_id"] for c in cases if c["family"] == family]
        per_family[family] = {name: pooled_mean([ious[i] for i in ids]) for name, ious in results.items()}
        per_family[family]["sppa_mvfit"] = pooled_mean([sppa_iou[i] for i in ids])
    per_stratum: dict[str, dict] = {}
    for stratum in ("csg_id", "implicit_ood"):
        ids = [c["case_id"] for c in cases if c["stratum"] == stratum]
        per_stratum[stratum] = {name: pooled_mean([ious[i] for i in ids]) for name, ious in results.items()}
        per_stratum[stratum]["sppa_mvfit"] = pooled_mean([sppa_iou[i] for i in ids])

    labels = {
        "G1_sealed_generic": "G1 sealed generic (control)",
        "G2_box_cylinder_chassis": "G2 box/cylinder chassis",
        "G3_vertical_stack_legs": "G3 vertical stack + legs",
        "G4_slotwise_family_mean": "G4 slot-wise family mean",
    }
    lines = [
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "Generic graph variant & Mean IoU & $\\Delta$ SPPA $-$ variant & CI95 & Gap closed \\\\",
        "\\midrule",
    ]
    for name, label in labels.items():
        arm = arms[name]
        if name == "G1_sealed_generic":
            lines.append(f"{label} & {f3(arm['mean_iou'])} & {f3(arm['delta_sppa_minus_variant'])} & --- & --- \\\\")
        else:
            boot = arm["sppa_minus_variant"]
            closure_pct = f"{100.0 * arm['gap_closure_vs_sealed_generic']:.1f}\\%"
            lines.append(f"{label} & {f3(arm['mean_iou'])} & {f3(arm['delta_sppa_minus_variant'])} & "
                         f"[{f3(boot['ci95_low'])}, {f3(boot['ci95_high'])}] & {closure_pct} \\\\")
    lines += [
        "\\midrule",
        f"SPPA-MVFit (sealed) & {f3(sppa_mean)} & 0.000 & --- & 100.0\\% \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "generic_graph_sensitivity_table.tex", "\n".join(lines))

    payload = {
        "experiment": "E5 generic-graph sensitivity",
        "label": EXPLORATORY_LABEL,
        "n_actors": len(cases),
        "condition": "clean",
        "metric": "voxel_iou_64cubed",
        "fit_seconds_wallclock": seconds,
        "design_document": "GENERIC_VARIANTS.md (frozen before measurement)",
        "g4_rule_reverified": True,
        "g1_control_max_abs_err_vs_seal": max_err,
        "sealed_reference": {"sppa_mvfit": sppa_mean, "generic_mvfit": pooled_mean(list(results["G1_sealed_generic"].values())), "delta": sealed_delta},
        "arms": arms,
        "per_family": per_family,
        "per_stratum": per_stratum,
        "protocol": {"bootstrap_resamples": 10000, "bootstrap_seed": 77157},
    }
    write_json(OUT / "generic_graph_sensitivity.json", payload)

    print(f"sealed: sppa={sppa_mean:.4f} generic={pooled_mean(list(results['G1_sealed_generic'].values())):.4f} delta={sealed_delta:.4f}")
    for name, label in labels.items():
        arm = arms[name]
        print(f"{label}: IoU {arm['mean_iou']:.4f}  delta {arm['delta_sppa_minus_variant']:.4f}  "
              f"closure {100.0 * arm['gap_closure_vs_sealed_generic']:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
