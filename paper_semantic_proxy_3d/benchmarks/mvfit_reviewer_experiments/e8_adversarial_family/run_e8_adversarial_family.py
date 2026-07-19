"""E8 - Adversarial anti-tautology stratum (exploratory post-hoc, not confirmatory).

Reviewer critique: "H1 is nearly tautological: the graph designed for family F
wins on actors built with the topology of F." Here every actor keeps its
semantic class but VIOLATES the structural prior of its family graph (12
violation types, 2 per family, frozen in ADVERSARIAL_DESIGN_FROZEN.md before
any fit). We measure whether the family graph degrades with grace or
collapses, and how much of the clean Delta survives.

Frozen design (see ADVERSARIAL_DESIGN_FROZEN.md):
  - base actors: the 120 csg_id test actors, regenerated from their stored
    seeds; runner aborts unless regeneration is bit-exact (120/120)
  - adversarial actors: 20 per family (idx 0-9 -> V1, 10-19 -> V2);
    violation randomness from default_rng(880000000 + 1000*fam_idx + idx)
  - same protocol as the sealed primary: render_source_masks (256->96),
    infer_method with true family token / generic graph, 31-candidate budget,
    voxel IoU at 64^3 vs voxelize_source of the adversarial actor
  - clean references from sealed results/test/raw_metrics.csv (not recomputed)
  - stratified paired bootstrap, cells = family, 10000 resamples, seed 77157
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, EXPERIMENTS_ROOT, FAMILIES,
    bootstrap_paired, f3, load_public_cases, load_sealed_clean_ious, mv,
    pooled_mean, voxel_iou, write_json, write_text, EXPLORATORY_LABEL,
)
from source.source_generators import (  # noqa: E402
    generate_source_actor, render_source_masks, validate_actor_inside_world, voxelize_source,
)

from adversarial_generators import VIOLATIONS, check_violation, violation_for_index  # noqa: E402

OUT = EXPERIMENTS_ROOT / "e8_adversarial_family"
PRIVATE_ACTORS = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\reproducibility\sppa_mvfit\data\test\private_source_actors.jsonl")
E8_SEED_BASE = 880000000


def load_private_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with PRIVATE_ACTORS.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            rows[row["case_id"]] = row
    return rows


def build_adversarial_actors() -> tuple[list[dict], list[dict]]:
    """Returns (e8_cases, e8_actors) after all pre-fit validation gates."""
    private = load_private_rows()
    public = {c["case_id"]: c for c in load_public_cases()}

    # gate 1: bit-exact base regeneration for all 120 csg_id actors
    csg_cases = [c for c in load_public_cases() if c["stratum"] == "csg_id"]
    regen_ok = 0
    base_actors: dict[str, dict] = {}
    for case in csg_cases:
        row = private[case["case_id"]]
        regen = generate_source_actor(case["family"], "csg_id", row["seed"])
        if json.dumps(regen, sort_keys=True) != json.dumps(row["actor"], sort_keys=True):
            raise RuntimeError(f"base regeneration drifted for {case['case_id']}")
        regen_ok += 1
        base_actors[case["case_id"]] = row["actor"]
    if regen_ok != 120:
        raise RuntimeError(f"expected 120 regenerated csg_id actors, got {regen_ok}")

    e8_cases: list[dict] = []
    e8_actors: list[dict] = []
    for family_index, family in enumerate(FAMILIES):
        family_cases = sorted((c for c in csg_cases if c["family"] == family), key=lambda c: c["index"])
        assert len(family_cases) == 20
        for case in family_cases:
            actor_index = case["index"]
            v_idx = violation_for_index(actor_index)
            v_name, transform = VIOLATIONS[family][v_idx]
            rng = np.random.default_rng(E8_SEED_BASE + 1000 * family_index + actor_index)
            base = base_actors[case["case_id"]]
            adv_components, info = transform(base["components"], rng)
            # gate 2: violation predicates (documented violations are enforced)
            check_violation(family, v_name, base["components"], adv_components)
            adv_actor = {
                "schema_version": base["schema_version"],
                "provenance": "synthetic_geometry_adversarial_e8",
                "family": family,
                "stratum": "csg_id",  # projection dispatch key (see frozen design)
                "seed": E8_SEED_BASE + 1000 * family_index + actor_index,
                "generator": "adversarial_e8_v1",
                "components": adv_components,
            }
            # gate 3: inside world
            if not validate_actor_inside_world(adv_actor):
                raise RuntimeError(f"adversarial actor outside world: {family} {actor_index} {v_name}")
            e8_cases.append({
                "case_id": f"e8-adv-{family}-{actor_index:03d}",
                "family": family,
                "stratum": "adversarial_e8",
                "index": actor_index,
                "violation": v_name,
                "violation_index": v_idx,
                "base_case_id": case["case_id"],
                "base_seed": private[case["case_id"]]["seed"],
                "e8_seed": E8_SEED_BASE + 1000 * family_index + actor_index,
                "violation_info": info,
            })
            e8_actors.append(adv_actor)
    assert len(e8_cases) == 120
    return e8_cases, e8_actors


def main() -> int:
    t_start = time.perf_counter()
    e8_cases, e8_actors = build_adversarial_actors()
    sealed = load_sealed_clean_ious()

    # --- fits ---------------------------------------------------------------
    sppa_adv: dict[str, float] = {}
    generic_adv: dict[str, float] = {}
    gt_voxels: dict[str, np.ndarray] = {}
    empty_obs = 0
    fit_seconds = 0.0
    for case, actor in zip(e8_cases, e8_actors):
        top, side = render_source_masks(actor)  # sealed clean-condition pipeline
        t0 = time.perf_counter()
        sppa = mv.infer_method("sppa_mvfit", case["family"], top, side)
        generic = mv.infer_method("generic_mvfit", case["family"], top, side)
        fit_seconds += time.perf_counter() - t0
        empty_obs += int(bool(sppa["empty_observation"]) or bool(generic["empty_observation"]))
        gt = voxelize_source(actor, 64)
        gt_voxels[case["case_id"]] = gt
        sppa_adv[case["case_id"]] = voxel_iou(gt, mv.voxelize_actor(sppa["actor"], 64))
        generic_adv[case["case_id"]] = voxel_iou(gt, mv.voxelize_actor(generic["actor"], 64))
    if empty_obs:
        raise RuntimeError(f"{empty_obs} adversarial fits hit the empty-observation fallback")

    # clean references from the seal (same base actors, clean condition)
    sppa_clean = {c["case_id"]: sealed[(c["base_case_id"], "sppa_mvfit")] for c in e8_cases}
    generic_clean = {c["case_id"]: sealed[(c["base_case_id"], "generic_mvfit")] for c in e8_cases}

    ids = [c["case_id"] for c in e8_cases]
    delta_adv = {cid: sppa_adv[cid] - generic_adv[cid] for cid in ids}
    delta_clean = {cid: sppa_clean[cid] - generic_clean[cid] for cid in ids}

    boot_delta_adv = bootstrap_paired(e8_cases, delta_adv)
    boot_delta_clean = bootstrap_paired(e8_cases, delta_clean)
    boot_sppa_degradation = bootstrap_paired(e8_cases, {cid: sppa_adv[cid] - sppa_clean[cid] for cid in ids})
    boot_generic_degradation = bootstrap_paired(e8_cases, {cid: generic_adv[cid] - generic_clean[cid] for cid in ids})
    boot_delta_delta = bootstrap_paired(e8_cases, {cid: delta_adv[cid] - delta_clean[cid] for cid in ids})

    share_sppa_below_generic = pooled_mean([1.0 if sppa_adv[cid] < generic_adv[cid] else 0.0 for cid in ids])

    per_family: dict[str, dict] = {}
    for family in FAMILIES:
        fcs = [c for c in e8_cases if c["family"] == family]
        fids = [c["case_id"] for c in fcs]
        per_family[family] = {
            "n": len(fids),
            "sppa_clean": pooled_mean([sppa_clean[i] for i in fids]),
            "sppa_adv": pooled_mean([sppa_adv[i] for i in fids]),
            "generic_clean": pooled_mean([generic_clean[i] for i in fids]),
            "generic_adv": pooled_mean([generic_adv[i] for i in fids]),
            "delta_clean": pooled_mean([delta_clean[i] for i in fids]),
            "delta_adv": pooled_mean([delta_adv[i] for i in fids]),
            "delta_adv_boot": bootstrap_paired(fcs, {i: delta_adv[i] for i in fids}),
            "sppa_degradation_boot": bootstrap_paired(fcs, {i: sppa_adv[i] - sppa_clean[i] for i in fids}),
            "generic_degradation_boot": bootstrap_paired(fcs, {i: generic_adv[i] - generic_clean[i] for i in fids}),
            "share_sppa_below_generic": pooled_mean([1.0 if sppa_adv[i] < generic_adv[i] else 0.0 for i in fids]),
            "min_sppa_adv": float(min(sppa_adv[i] for i in fids)),
        }

    per_violation: dict[str, dict] = {}
    for family in FAMILIES:
        for v_idx, (v_name, _) in sorted(VIOLATIONS[family].items()):
            vcs = [c for c in e8_cases if c["family"] == family and c["violation_index"] == v_idx]
            vids = [c["case_id"] for c in vcs]
            key = f"{family}/{v_name}"
            per_violation[key] = {
                "family": family,
                "violation": v_name,
                "n": len(vids),
                "sppa_adv": pooled_mean([sppa_adv[i] for i in vids]),
                "generic_adv": pooled_mean([generic_adv[i] for i in vids]),
                "delta_adv": pooled_mean([delta_adv[i] for i in vids]),
                "delta_adv_boot": bootstrap_paired(vcs, {i: delta_adv[i] for i in vids}),
                "sppa_degradation": pooled_mean([sppa_adv[i] - sppa_clean[i] for i in vids]),
                "generic_degradation": pooled_mean([generic_adv[i] - generic_clean[i] for i in vids]),
                "share_sppa_below_generic": pooled_mean([1.0 if sppa_adv[i] < generic_adv[i] else 0.0 for i in vids]),
            }

    # --- results.jsonl (one row per adversarial actor) ----------------------
    with (OUT / "results.jsonl").open("w", encoding="utf-8") as handle:
        for case in e8_cases:
            cid = case["case_id"]
            handle.write(json.dumps({
                "case_id": cid,
                "family": case["family"],
                "stratum": "adversarial_e8",
                "violation": case["violation"],
                "base_case_id": case["base_case_id"],
                "base_seed": case["base_seed"],
                "e8_seed": case["e8_seed"],
                "violation_info": case["violation_info"],
                "sppa_adv_iou": sppa_adv[cid],
                "generic_adv_iou": generic_adv[cid],
                "sppa_clean_iou_sealed": sppa_clean[cid],
                "generic_clean_iou_sealed": generic_clean[cid],
                "delta_adv": delta_adv[cid],
                "delta_clean_sealed": delta_clean[cid],
                "sppa_wins": bool(sppa_adv[cid] >= generic_adv[cid]),
            }, sort_keys=True) + "\n")

    # --- tables -------------------------------------------------------------
    def fam_tex(name: str) -> str:
        return name.replace("_", "\\_")

    lines = [
        "\\begin{tabular}{@{}lrrrrrrrr@{}}",
        "\\toprule",
        "Family & $n$ & SPPA clean & SPPA adv & Gen clean & Gen adv & $\\Delta_{\\rm adv}$ & CI95 & SPPA$<$Gen \\\\",
        "\\midrule",
    ]
    for family in FAMILIES:
        pf = per_family[family]
        boot = pf["delta_adv_boot"]
        share = f"{100.0 * pf['share_sppa_below_generic']:.0f}\\%"
        lines.append(
            f"{fam_tex(family)} & {pf['n']} & {f3(pf['sppa_clean'])} & {f3(pf['sppa_adv'])} & "
            f"{f3(pf['generic_clean'])} & {f3(pf['generic_adv'])} & {f3(pf['delta_adv'])} & "
            f"[{f3(boot['ci95_low'])}, {f3(boot['ci95_high'])}] & {share} \\\\")
    overall = {
        "sppa_clean": pooled_mean([sppa_clean[i] for i in ids]),
        "sppa_adv": pooled_mean([sppa_adv[i] for i in ids]),
        "generic_clean": pooled_mean([generic_clean[i] for i in ids]),
        "generic_adv": pooled_mean([generic_adv[i] for i in ids]),
    }
    lines += [
        "\\midrule",
        f"Overall & 120 & {f3(overall['sppa_clean'])} & {f3(overall['sppa_adv'])} & {f3(overall['generic_clean'])} & "
        f"{f3(overall['generic_adv'])} & {f3(boot_delta_adv['mean_difference'])} & "
        f"[{f3(boot_delta_adv['ci95_low'])}, {f3(boot_delta_adv['ci95_high'])}] & {100.0 * share_sppa_below_generic:.0f}\\% \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "adversarial_table.tex", "\n".join(lines))

    vlines = [
        "\\begin{tabular}{@{}llrrrrrr@{}}",
        "\\toprule",
        "Family & Violation & $n$ & SPPA adv & Gen adv & $\\Delta_{\\rm adv}$ & CI95 & SPPA$<$Gen \\\\",
        "\\midrule",
    ]
    for key, pv in per_violation.items():
        boot = pv["delta_adv_boot"]
        share = f"{100.0 * pv['share_sppa_below_generic']:.0f}\\%"
        vlines.append(
            f"{fam_tex(pv['family'])} & {fam_tex(pv['violation'])} & {pv['n']} & {f3(pv['sppa_adv'])} & "
            f"{f3(pv['generic_adv'])} & {f3(pv['delta_adv'])} & "
            f"[{f3(boot['ci95_low'])}, {f3(boot['ci95_high'])}] & {share} \\\\")
    vlines += ["\\bottomrule", "\\end{tabular}", ""]
    write_text(OUT / "adversarial_violations_table.tex", "\n".join(vlines))

    payload = {
        "experiment": "E8 adversarial anti-tautology stratum",
        "label": EXPLORATORY_LABEL,
        "design_document": "ADVERSARIAL_DESIGN_FROZEN.md (frozen before any fit)",
        "n_actors": len(e8_cases),
        "violations_per_family": 2,
        "actors_per_violation": 10,
        "condition": "clean-equivalent (render_source_masks, same pipeline as sealed clean)",
        "metric": "voxel_iou_64cubed",
        "e8_seed_base": E8_SEED_BASE,
        "validation_gates": {
            "base_regeneration_bit_exact": "120/120",
            "violation_predicates": "12/12 families x types passed pre-fit",
            "inside_world": "120/120",
            "empty_observation_fallbacks": empty_obs,
        },
        "clean_reference": {
            "source": "sealed results/test/raw_metrics.csv (clean, csg_id), same base actors",
            "sppa_mean": overall["sppa_clean"],
            "generic_mean": overall["generic_clean"],
            "delta": boot_delta_clean["mean_difference"],
            "delta_ci95": [boot_delta_clean["ci95_low"], boot_delta_clean["ci95_high"]],
        },
        "adversarial_means": {
            "sppa": overall["sppa_adv"],
            "generic": overall["generic_adv"],
        },
        "paired_bootstrap": {
            "delta_adv_sppa_minus_generic": boot_delta_adv,
            "delta_clean_same_actors": boot_delta_clean,
            "sppa_adv_minus_clean": boot_sppa_degradation,
            "generic_adv_minus_clean": boot_generic_degradation,
            "delta_delta_adv_minus_clean": boot_delta_delta,
        },
        "share_sppa_below_generic": share_sppa_below_generic,
        "per_family": per_family,
        "per_violation": per_violation,
        "fit_seconds_wallclock": fit_seconds,
        "protocol": {"bootstrap_resamples": BOOTSTRAP_RESAMPLES, "bootstrap_seed": BOOTSTRAP_SEED,
                     "cells": "family (single adversarial stratum), mean of cell means"},
        "wallclock_seconds_total": time.perf_counter() - t_start,
    }
    write_json(OUT / "adversarial_results.json", payload)

    print(f"actors=120  fits in {fit_seconds:.1f}s  total {time.perf_counter() - t_start:.1f}s")
    print(f"clean ref (same actors, sealed): sppa={overall['sppa_clean']:.4f} generic={overall['generic_clean']:.4f} "
          f"delta={boot_delta_clean['mean_difference']:.4f}")
    print(f"adversarial: sppa={overall['sppa_adv']:.4f} generic={overall['generic_adv']:.4f}")
    print(f"DELTA_adv = {boot_delta_adv['mean_difference']:.4f} "
          f"[{boot_delta_adv['ci95_low']:.4f}, {boot_delta_adv['ci95_high']:.4f}] p={boot_delta_adv['null_centered_two_sided_p']:.4f}")
    print(f"DELTADELTA (adv - clean) = {boot_delta_delta['mean_difference']:.4f} "
          f"[{boot_delta_delta['ci95_low']:.4f}, {boot_delta_delta['ci95_high']:.4f}] p={boot_delta_delta['null_centered_two_sided_p']:.4f}")
    print(f"SPPA degradation = {boot_sppa_degradation['mean_difference']:.4f}; "
          f"Generic degradation = {boot_generic_degradation['mean_difference']:.4f}")
    print(f"share SPPA<Generic: {share_sppa_below_generic:.3f}")
    for family in FAMILIES:
        pf = per_family[family]
        print(f"  {family:22s} sppa {pf['sppa_adv']:.3f} (clean {pf['sppa_clean']:.3f})  "
              f"gen {pf['generic_adv']:.3f} (clean {pf['generic_clean']:.3f})  "
              f"D_adv {pf['delta_adv']:+.3f}  loses {100.0 * pf['share_sppa_below_generic']:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
