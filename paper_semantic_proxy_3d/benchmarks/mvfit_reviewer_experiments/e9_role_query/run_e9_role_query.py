"""E9 - Operational utility of roles: part query + part counting (post-hoc).

Reviewer critique: "the visual hull gives 0.522 IoU at 0.22 ms without
roles -- what are roles FOR?" E9 turns roles into a TASK, frozen in
ROLE_QUERY_FROZEN.md before any metric computation:

  PART QUERY ("where is the cargo / the wheels / the cabin?"):
  each of the 920 frozen e6 matched pairs is one query; every method
  returns a voxel set; scored by precision/recall/F1 and by normalized
  centroid error against the GT component.
    - SPPA-MVFit:    voxels of the fitted slot for that role (sealed theta)
    - Generic-MVFit: voxels of the mapped generic slot (sealed theta,
                     frozen nearest-default-center mapping g)
    - Hull-HEUR-A:   largest 26-connected component of the visual hull
    - Hull-HEUR-B:   lower z half of the visual hull
    (both hull heuristics answer EVERY role identically -- they are the
    strongest role-free answers, frozen before measurement)

  PART COUNTING (bonus): how many wheels / legs / platforms / crowns?
  SPPA answers structurally from the graph; Generic from the frozen
  mapping; the hull counts its connected components.

Validation gates (abort on failure):
  1. hull recomputation matches sealed raw_metrics.csv bit-exactly
  2. SPPA slot pipeline reproduces e6 role_aware_iou.json pairs bit-exactly
  3. generic mapping g re-derived from graphs.json equals the frozen table
  4. 920 queries over 120 actors
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e6_role_aware"))
from _common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, EXPERIMENTS_ROOT, FAMILIES, GtCache,
    bootstrap_paired, clean_view_masks, f3, load_masks, load_public_cases,
    load_sealed_clean_ious, mv, pooled_mean, write_json, write_text,
    EXPLORATORY_LABEL,
)
from run_e6_role_aware import ROLES, mapping_for  # noqa: E402  (frozen e6 mapping)

OUT = EXPERIMENTS_ROOT / "e9_role_query"
E6_JSON = EXPERIMENTS_ROOT / "e6_role_aware" / "role_aware_iou.json"
SEALED_RECORDS = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\reproducibility\sppa_mvfit\results\test\sealed_method_outputs.jsonl")
RES = 64

# Frozen generic mapping g (family slot -> generic slot), from ROLE_QUERY_FROZEN.md
FROZEN_G: dict[str, list[int]] = {
    "compact_vehicle": [0, 0, 3, 4, 5, 6, 1, 2],
    "articulated_vehicle": [1, 1, 2, 3, 1, 3, 5, 2],
    "quadruped": [0, 2, 3, 4, 5, 6, 2, 1],
    "branching_vertical": [0, 7, 7, 7, 7, 7, 7, 7],
    "lattice_tower": [7, 7, 7, 7, 7, 0, 7, 7],
    "rider_cycle": [1, 2, 0, 0, 0, 7, 7, 2],
}

# Frozen counting spec: family -> (part name, GT component index rule, sppa slots)
COUNT_SPEC: dict[str, tuple[str, str, list[int]]] = {
    "compact_vehicle": ("wheel", "comps[2:6]", [2, 3, 4, 5]),
    "articulated_vehicle": ("wheel", "comps[4:8]", [4, 5, 6, 7]),
    "quadruped": ("leg", "comps[2:6]", [2, 3, 4, 5]),
    "lattice_tower": ("platform", "comps[5:]", [5, 6, 7]),
    "branching_vertical": ("crown", "comps[1:len-3]", [1, 2, 3, 4]),
    "rider_cycle": ("wheel", "comps[0:2]", [0, 1]),
}


def derive_generic_mapping() -> dict[str, list[int]]:
    """Re-derive g from graphs.json per the frozen rule (nearest default center)."""
    generic_centers = np.asarray([s["center"] for s in mv.GRAPHS["generic"]], dtype=np.float64)
    mapping: dict[str, list[int]] = {}
    for family in FAMILIES:
        row: list[int] = []
        for slot in mv.GRAPHS[family]:
            center = np.asarray(slot["center"], dtype=np.float64)
            distances = np.linalg.norm(generic_centers - center, axis=1)
            row.append(int(np.argmin(distances)))  # argmin breaks ties by lower index
        mapping[family] = row
    return mapping


def centroid(mask: np.ndarray) -> np.ndarray:
    idx = np.nonzero(mask)
    if not len(idx[0]):
        return np.full(3, np.nan)
    centers = [mv._cell_centers(axis, RES) for axis in ("x", "y", "z")]
    return np.asarray([centers[axis][idx[axis]].mean() for axis in range(3)])


def actor_size(gt_occ: np.ndarray) -> float:
    idx = np.nonzero(gt_occ)
    lengths = []
    for axis, world_axis in enumerate(("x", "y", "z")):
        low, high = mv.WORLD[world_axis]
        cell = (high - low) / RES
        lengths.append((int(idx[axis].max()) - int(idx[axis].min()) + 1) * cell)
    return float(np.linalg.norm(np.asarray(lengths)))


def prf1(sel: np.ndarray, gt: np.ndarray) -> tuple[float, float, float]:
    inter = int(np.count_nonzero(sel & gt))
    n_sel, n_gt = int(np.count_nonzero(sel)), int(np.count_nonzero(gt))
    precision = inter / n_sel if n_sel else 0.0
    recall = inter / n_gt if n_gt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def largest_cc(hull: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(hull.astype(bool), structure=np.ones((3, 3, 3), dtype=np.uint8))
    if count == 0:
        return np.zeros_like(hull, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(np.argmax(sizes))


def lower_half_z(hull: np.ndarray) -> np.ndarray:
    idx = np.nonzero(hull)
    if not len(idx[0]):
        return np.zeros_like(hull, dtype=bool)
    # frozen rule: hull voxels with z_center <= (z_min + z_max) / 2 of the
    # occupied hull voxels; constant cell size makes the index test equivalent
    z_mid = 0.5 * (int(idx[2].min()) + int(idx[2].max()))
    z_idx = np.arange(hull.shape[2])
    return hull & (z_idx <= z_mid)[None, None, :]


def gt_part_count(family: str, components: list[dict]) -> int:
    if family in ("compact_vehicle", "quadruped"):
        return len(components[2:6])
    if family == "articulated_vehicle":
        return len(components[4:8])
    if family == "lattice_tower":
        return len(components[5:])
    if family == "branching_vertical":
        return len(components[1: len(components) - 3])
    if family == "rider_cycle":
        return len(components[0:2])
    raise ValueError(family)


def main() -> int:
    t_start = time.perf_counter()
    g_derived = derive_generic_mapping()
    if g_derived != FROZEN_G:
        raise RuntimeError(f"generic mapping drifted from frozen table: {g_derived}")

    all_cases = load_public_cases()
    masks = load_masks()
    gt = GtCache()
    sealed = load_sealed_clean_ious()
    e6_pairs = json.loads(E6_JSON.read_text(encoding="utf-8"))["pair_rows"]
    e6_lookup = {(r["case_id"], r["slot"], r["component"]): (r["coverage"], r["role_iou"]) for r in e6_pairs}

    sppa_theta: dict[str, list[float]] = {}
    generic_theta: dict[str, list[float]] = {}
    with SEALED_RECORDS.open("r", encoding="utf-8") as handle:
        for line in handle:
            rec = json.loads(line)
            if rec["condition"] == "clean" and rec["stratum"] == "csg_id":
                if rec["method"] == "sppa_mvfit":
                    sppa_theta[rec["case_id"]] = rec["metadata"]["theta"]
                elif rec["method"] == "generic_mvfit":
                    generic_theta[rec["case_id"]] = rec["metadata"]["theta"]
    if len(sppa_theta) != 120 or len(generic_theta) != 120:
        raise RuntimeError("expected 120 sealed sppa+generic csg_id clean records")

    query_rows: list[dict] = []
    count_rows: list[dict] = []
    actor_macro: dict[str, dict[str, float]] = {}
    hull_check_max = 0.0
    e6_check_max = 0.0

    for case_index, case in enumerate(all_cases):
        if case["stratum"] != "csg_id":
            continue
        cid, family = case["case_id"], case["family"]
        top, side = clean_view_masks(masks, case_index)
        actor = gt.actor(cid)
        components = actor["components"]
        gt_occ = gt.voxels(cid)
        size_m = actor_size(gt_occ)

        # gate 1: hull equivalence with the seal
        hull, _ = mv.baseline_occupancy("nonsemantic_visual_hull", top, side, RES)
        hull_iou = float(np.count_nonzero(hull & gt_occ) / np.count_nonzero(hull | gt_occ))
        hull_check_max = max(hull_check_max, abs(hull_iou - sealed[(cid, "nonsemantic_visual_hull")]))

        # method voxel sets
        sppa_actor = mv.build_actor(family, sppa_theta[cid])
        generic_actor = mv.build_actor("generic", generic_theta[cid])
        heur_a = largest_cc(hull)
        heur_b = lower_half_z(hull)

        pairs = mapping_for(family, components)
        slot_vox = {s: mv.voxelize_actor([sppa_actor[s]], RES) for s, _ in pairs}
        generic_vox = {g: mv.voxelize_actor([generic_actor[g]], RES) for g in {FROZEN_G[family][s] for s, _ in pairs}}
        comp_vox = {j: mv.voxelize_actor([dict(type="box", center=[0, 0, -1e6], size=[1e-4, 1e-4, 1e-4])], RES) for j in []}  # placeholder no-op
        from source.source_generators import _component_occupancy
        x, y, z = np.meshgrid(
            mv._cell_centers("x", RES), mv._cell_centers("y", RES),
            mv._cell_centers("z", RES), indexing="ij", sparse=True)
        comp_vox = {j: _component_occupancy(components[j], x, y, z) for _, j in pairs}

        gt_c = {j: centroid(v) for j, v in comp_vox.items()}
        sel_c = {
            "sppa_mvfit": {s: centroid(v) for s, v in slot_vox.items()},
            "generic_mvfit": {g: centroid(v) for g, v in generic_vox.items()},
        }
        heur_a_c, heur_b_c = centroid(heur_a), centroid(heur_b)

        per_method_f1: dict[str, list[float]] = {"sppa_mvfit": [], "generic_mvfit": [], "hull_largest_cc": [], "hull_lower_half_z": []}
        per_method_d: dict[str, list[float]] = {"sppa_mvfit": [], "generic_mvfit": [], "hull_largest_cc": [], "hull_lower_half_z": []}

        for slot_index, comp_index in pairs:
            gt_v = comp_vox[comp_index]
            n_gt = int(np.count_nonzero(gt_v))
            selections = {
                "sppa_mvfit": slot_vox[slot_index],
                "generic_mvfit": generic_vox[FROZEN_G[family][slot_index]],
                "hull_largest_cc": heur_a,
                "hull_lower_half_z": heur_b,
            }
            row: dict = {"case_id": cid, "family": family, "slot": slot_index,
                         "role": ROLES[family][slot_index], "component": comp_index,
                         "gt_voxels": n_gt}
            for method, sel in selections.items():
                p, r, f1 = prf1(sel, gt_v)
                c_sel = (sel_c["sppa_mvfit"][slot_index] if method == "sppa_mvfit"
                         else sel_c["generic_mvfit"][FROZEN_G[family][slot_index]] if method == "generic_mvfit"
                         else heur_a_c if method == "hull_largest_cc" else heur_b_c)
                d = float(np.linalg.norm(c_sel - gt_c[comp_index]) / size_m) if not np.isnan(c_sel).any() else 1.0
                row[method] = {"precision": p, "recall": r, "f1": f1, "centroid_err": d}
                # ERRATUM (pre-registered rule correction, see README): the frozen
                # claim "GT components of matched pairs are never empty" is false
                # for 33/920 pairs at 64^3 (thin parts: tail, frame, legs). A query
                # with an empty GT voxel set is unscoreable (recall and centroid
                # error undefined); such rows are kept in results.jsonl for audit
                # but excluded from every aggregate. Sensitivity under the
                # inclusion-as-zero rule is reported alongside.
                if n_gt > 0:
                    per_method_f1[method].append(f1)
                    per_method_d[method].append(d)
            # gate 2: e6 pair equivalence (sppa pipeline)
            inter = int(np.count_nonzero(slot_vox[slot_index] & gt_v))
            comp_count = max(int(np.count_nonzero(gt_v)), 1)
            union = int(np.count_nonzero(slot_vox[slot_index])) + int(np.count_nonzero(gt_v)) - inter
            cov = inter / comp_count
            riou = inter / union if union else 1.0
            ref = e6_lookup[(cid, slot_index, comp_index)]
            e6_check_max = max(e6_check_max, abs(cov - ref[0]), abs(riou - ref[1]))
            query_rows.append(row)

        actor_macro[cid] = {m: pooled_mean(v) for m, v in per_method_f1.items()}
        actor_macro[cid].update({f"{m}_d": pooled_mean(v) for m, v in per_method_d.items()})

        # counting task
        gt_count = gt_part_count(family, components)
        sppa_count = len(COUNT_SPEC[family][2])
        generic_count = len({FROZEN_G[family][s] for s in COUNT_SPEC[family][2]})
        hull_count = int(ndimage.label(hull, structure=np.ones((3, 3, 3), dtype=np.uint8))[1])
        count_rows.append({"case_id": cid, "family": family, "part": COUNT_SPEC[family][0],
                           "gt": gt_count, "sppa": sppa_count, "generic": generic_count, "hull": hull_count})

    if hull_check_max > 1e-12:
        raise RuntimeError(f"hull recomputation drifts from seal: {hull_check_max}")
    if e6_check_max > 1e-12:
        raise RuntimeError(f"sppa slot pipeline drifts from e6: {e6_check_max}")
    if len(query_rows) != 920:
        raise RuntimeError(f"expected 920 queries, got {len(query_rows)}")

    csg_cases = [c for c in all_cases if c["stratum"] == "csg_id"]
    METHODS = ["sppa_mvfit", "generic_mvfit", "hull_largest_cc", "hull_lower_half_z"]

    # Aggregates run over SCORED queries only (gt_voxels > 0; see erratum above).
    scored_rows = [r for r in query_rows if r["gt_voxels"] > 0]
    n_excluded = len(query_rows) - len(scored_rows)
    # sensitivity: overall F1 if empty-GT queries were instead kept as zeros
    sensitivity_f1_include_empty = {m: pooled_mean([r[m]["f1"] for r in query_rows]) for m in METHODS}

    # aggregation
    per_family: dict[str, dict] = {}
    for family in FAMILIES:
        rows = [r for r in scored_rows if r["family"] == family]
        per_family[family] = {
            "n_queries": len(rows),
            **{f"{m}_f1": pooled_mean([r[m]["f1"] for r in rows]) for m in METHODS},
            **{f"{m}_precision": pooled_mean([r[m]["precision"] for r in rows]) for m in METHODS},
            **{f"{m}_recall": pooled_mean([r[m]["recall"] for r in rows]) for m in METHODS},
            **{f"{m}_centroid_err": pooled_mean([r[m]["centroid_err"] for r in rows]) for m in METHODS},
        }
    per_role: dict[str, dict] = {}
    for family in FAMILIES:
        for role in ROLES[family]:
            rows = [r for r in scored_rows if r["family"] == family and r["role"] == role]
            if rows:
                per_role[f"{family}/{role}"] = {
                    "n": len(rows),
                    **{f"{m}_f1": pooled_mean([r[m]["f1"] for r in rows]) for m in METHODS},
                    **{f"{m}_centroid_err": pooled_mean([r[m]["centroid_err"] for r in rows]) for m in METHODS},
                }
    overall = {
        "n_queries": len(scored_rows),
        **{f"{m}_f1": pooled_mean([r[m]["f1"] for r in scored_rows]) for m in METHODS},
        **{f"{m}_precision": pooled_mean([r[m]["precision"] for r in scored_rows]) for m in METHODS},
        **{f"{m}_recall": pooled_mean([r[m]["recall"] for r in scored_rows]) for m in METHODS},
        **{f"{m}_centroid_err": pooled_mean([r[m]["centroid_err"] for r in scored_rows]) for m in METHODS},
    }

    boots: dict[str, dict] = {}
    for control in ("generic_mvfit", "hull_largest_cc", "hull_lower_half_z"):
        boots[f"sppa_minus_{control}_f1"] = bootstrap_paired(
            csg_cases, {cid: actor_macro[cid]["sppa_mvfit"] - actor_macro[cid][control] for cid in actor_macro})
        boots[f"{control}_minus_sppa_centroid"] = bootstrap_paired(
            csg_cases, {cid: actor_macro[cid][f"{control}_d"] - actor_macro[cid]["sppa_mvfit_d"] for cid in actor_macro})

    # counting aggregation
    count_per_family: dict[str, dict] = {}
    for family in FAMILIES:
        rows = [r for r in count_rows if r["family"] == family]
        count_per_family[family] = {
            "part": COUNT_SPEC[family][0],
            "n": len(rows),
            "gt_counts": sorted({r["gt"] for r in rows}),
            "sppa_pred": rows[0]["sppa"],
            "generic_pred": rows[0]["generic"],
            "hull_pred_mean": pooled_mean([r["hull"] for r in rows]),
            "sppa_exact": pooled_mean([1.0 if r["sppa"] == r["gt"] else 0.0 for r in rows]),
            "generic_exact": pooled_mean([1.0 if r["generic"] == r["gt"] else 0.0 for r in rows]),
            "hull_exact": pooled_mean([1.0 if r["hull"] == r["gt"] else 0.0 for r in rows]),
            "sppa_mae": pooled_mean([abs(r["sppa"] - r["gt"]) for r in rows]),
            "generic_mae": pooled_mean([abs(r["generic"] - r["gt"]) for r in rows]),
            "hull_mae": pooled_mean([abs(r["hull"] - r["gt"]) for r in rows]),
        }

    # results.jsonl (one row per query)
    with (OUT / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in query_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    # tables
    def fam_tex(name: str) -> str:
        return name.replace("_", "\\_")

    lines = [
        "\\begin{tabular}{@{}lrrrrrrrrr@{}}",
        "\\toprule",
        "Family & $n$ & SPPA F1 & Gen F1 & HullA F1 & HullB F1 & SPPA $d_c$ & Gen $d_c$ & HullA $d_c$ & HullB $d_c$ \\\\",
        "\\midrule",
    ]
    for family in FAMILIES:
        pf = per_family[family]
        lines.append(
            f"{fam_tex(family)} & {pf['n_queries']} & {f3(pf['sppa_mvfit_f1'])} & {f3(pf['generic_mvfit_f1'])} & "
            f"{f3(pf['hull_largest_cc_f1'])} & {f3(pf['hull_lower_half_z_f1'])} & {f3(pf['sppa_mvfit_centroid_err'])} & "
            f"{f3(pf['generic_mvfit_centroid_err'])} & {f3(pf['hull_largest_cc_centroid_err'])} & {f3(pf['hull_lower_half_z_centroid_err'])} \\\\")
    lines += [
        "\\midrule",
        f"Overall & {overall['n_queries']} & {f3(overall['sppa_mvfit_f1'])} & {f3(overall['generic_mvfit_f1'])} & "
        f"{f3(overall['hull_largest_cc_f1'])} & {f3(overall['hull_lower_half_z_f1'])} & {f3(overall['sppa_mvfit_centroid_err'])} & "
        f"{f3(overall['generic_mvfit_centroid_err'])} & {f3(overall['hull_largest_cc_centroid_err'])} & {f3(overall['hull_lower_half_z_centroid_err'])} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "role_query_table.tex", "\n".join(lines))

    clines = [
        "\\begin{tabular}{@{}lllrrrrrr@{}}",
        "\\toprule",
        "Family & Part & GT count & SPPA & Generic & Hull (mean) & SPPA exact & Generic exact & Hull exact \\\\",
        "\\midrule",
    ]
    for family in FAMILIES:
        cf = count_per_family[family]
        gt_counts = "--".join(str(v) for v in cf["gt_counts"])
        clines.append(
            f"{fam_tex(family)} & {cf['part']} & {gt_counts} & {cf['sppa_pred']} & {cf['generic_pred']} & "
            f"{cf['hull_pred_mean']:.2f} & {100.0 * cf['sppa_exact']:.0f}\\% & {100.0 * cf['generic_exact']:.0f}\\% & "
            f"{100.0 * cf['hull_exact']:.0f}\\% \\\\")
    clines += ["\\bottomrule", "\\end{tabular}", ""]
    write_text(OUT / "role_count_table.tex", "\n".join(clines))

    payload = {
        "experiment": "E9 operational utility of roles: part query + part counting",
        "label": EXPLORATORY_LABEL,
        "design_document": "ROLE_QUERY_FROZEN.md (frozen before any metric)",
        "n_actors": len(actor_macro),
        "n_queries": len(query_rows),
        "n_queries_scored": len(scored_rows),
        "empty_gt_excluded": {"n": n_excluded,
                              "erratum": "frozen doc claimed GT components of matched pairs are never empty; "
                                         "33/920 are empty at 64^3 (thin parts). Empty-GT queries are unscoreable "
                                         "(recall/centroid undefined): kept in results.jsonl, excluded from all "
                                         "aggregates. Sensitivity under inclusion-as-zero reported below.",
                              "roles_affected": sorted({f"{r['family']}/{r['role']}" for r in query_rows if r["gt_voxels"] == 0})},
        "sensitivity_f1_include_empty_gt_as_zero": sensitivity_f1_include_empty,
        "theta_source": "sealed_method_outputs.jsonl (sppa_mvfit + generic_mvfit, clean, csg_id; no refitting)",
        "hull_heuristics": {"A": "largest 26-connected component of the 64^3 visual hull",
                            "B": "hull voxels with z <= midpoint of occupied z extent"},
        "generic_mapping": FROZEN_G,
        "validation_gates": {"hull_vs_seal_max_abs_err": hull_check_max,
                             "e6_pairs_max_abs_err": e6_check_max,
                             "generic_mapping_matches_frozen": True,
                             "queries": len(query_rows)},
        "overall": overall,
        "per_family": per_family,
        "per_role": per_role,
        "paired_bootstrap_actor_macro": boots,
        "counting": {"per_family": count_per_family,
                     "overall_exact": {m: pooled_mean([1.0 if r[m] == r["gt"] else 0.0 for r in count_rows]) for m in ("sppa", "generic", "hull")},
                     "overall_mae": {m: pooled_mean([abs(r[m] - r["gt"]) for r in count_rows]) for m in ("sppa", "generic", "hull")}},
        "protocol": {"bootstrap_resamples": BOOTSTRAP_RESAMPLES, "bootstrap_seed": BOOTSTRAP_SEED,
                     "cells": "family (csg_id only), mean of cell means",
                     "centroid_normalizer": "GT occupancy bbox diagonal, world meters"},
        "wallclock_seconds_total": time.perf_counter() - t_start,
    }
    write_json(OUT / "role_query_results.json", payload)

    print(f"queries={len(query_rows)} scored={len(scored_rows)} excluded_empty_gt={n_excluded}  "
          f"gates: hull_err={hull_check_max:.2e} e6_err={e6_check_max:.2e}")
    print("part-query F1 (overall): "
          f"sppa={overall['sppa_mvfit_f1']:.4f} generic={overall['generic_mvfit_f1']:.4f} "
          f"hullA={overall['hull_largest_cc_f1']:.4f} hullB={overall['hull_lower_half_z_f1']:.4f}")
    print("centroid err (overall): "
          f"sppa={overall['sppa_mvfit_centroid_err']:.4f} generic={overall['generic_mvfit_centroid_err']:.4f} "
          f"hullA={overall['hull_largest_cc_centroid_err']:.4f} hullB={overall['hull_lower_half_z_centroid_err']:.4f}")
    for name, boot in boots.items():
        print(f"{name}: {boot['mean_difference']:.4f} [{boot['ci95_low']:.4f}, {boot['ci95_high']:.4f}] "
              f"p={boot['null_centered_two_sided_p']:.4f}")
    for family in FAMILIES:
        pf = per_family[family]
        print(f"  {family:22s} F1 sppa={pf['sppa_mvfit_f1']:.3f} gen={pf['generic_mvfit_f1']:.3f} "
              f"hA={pf['hull_largest_cc_f1']:.3f} hB={pf['hull_lower_half_z_f1']:.3f} | "
              f"d sppa={pf['sppa_mvfit_centroid_err']:.3f} gen={pf['generic_mvfit_centroid_err']:.3f}")
    print("counting exact-match:", {m: round(v, 3) for m, v in payload['counting']['overall_exact'].items()})
    print(f"total {time.perf_counter() - t_start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
