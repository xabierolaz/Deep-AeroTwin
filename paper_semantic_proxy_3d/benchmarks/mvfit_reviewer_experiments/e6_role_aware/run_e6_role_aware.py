"""E6 - Role-aware IoU (descriptive post-hoc, mapping frozen before computation).

Anti-cherry-picking protocol: the slot<->component mapping is frozen in
ROLE_MAPPING_FROZEN.md BEFORE this script was written or run. The analysis is
restricted to the csg_id stratum (120 actors) as declared there ex-ante.

Inputs:
  - fitted SPPA slots: SEALED theta from results/test/sealed_method_outputs.jsonl
    (method sppa_mvfit, condition clean) -> build_actor(family, theta); no refit.
  - GT components: data/test/private_source_actors.jsonl (post-seal release),
    voxelized per component at 64^3 with source_generators._component_occupancy
    on the identical grid used by voxelize_source.

Metrics per matched pair (slot s, component c), both voxelized at 64^3:
  role coverage = |s ∩ c| / |c|      (GT component covered by its correct slot)
  role IoU      = |s ∩ c| / |s ∪ c|

Shuffle controls (within each actor, using the precomputed m x m intersection
matrix): (i) deterministic cyclic shift +1; (ii) mean over 100 random
permutations (seed 77157).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parents[1] / "reproducibility" / "sppa_mvfit"))
from _common import (  # noqa: E402
    EXPERIMENTS_ROOT, GtCache, bootstrap_paired, f3, load_public_cases, mv,
    pooled_mean, write_json, write_text,
)
from source.source_generators import _component_occupancy  # noqa: E402

OUT = EXPERIMENTS_ROOT / "e6_role_aware"
SEALED_RECORDS = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\reproducibility\sppa_mvfit\results\test\sealed_method_outputs.jsonl")

ROLES: dict[str, list[str]] = {
    "compact_vehicle": ["body", "cabin", "wheel_rear_left", "wheel_rear_right",
                        "wheel_front_left", "wheel_front_right", "bumper_rear", "bumper_front"],
    "articulated_vehicle": ["tractor", "cabin", "trailer", "hitch",
                            "wheel_1", "wheel_2", "wheel_3", "wheel_4"],
    "quadruped": ["body", "head", "leg_rear_left", "leg_rear_right",
                  "leg_front_left", "leg_front_right", "neck", "tail"],
    "branching_vertical": ["trunk", "crown_1", "crown_2", "crown_3", "crown_4",
                           "branch_left", "branch_right", "branch_y"],
    "lattice_tower": ["core", "leg_1", "leg_2", "leg_3", "leg_4",
                      "platform_low", "platform_mid", "platform_high"],
    "rider_cycle": ["wheel_rear", "wheel_front", "frame_main", "frame_mid",
                    "frame_front", "torso", "head", "fork"],
}


def mapping_for(family: str, components: list[dict]) -> list[tuple[int, int]]:
    """Frozen mapping from ROLE_MAPPING_FROZEN.md: list of (slot, component)."""
    if family == "compact_vehicle":
        return [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (7, 6)]
    if family in ("articulated_vehicle", "quadruped", "rider_cycle"):
        return [(i, i) for i in range(8)]
    if family == "lattice_tower":
        platforms_gt = sorted(range(5, len(components)), key=lambda j: components[j]["center"][2])
        slots_platforms = [5, 6, 7]  # already z-ordered in the frozen graph
        return [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)] + [
            (s, j) for s, j in zip(slots_platforms, platforms_gt)]
    if family == "branching_vertical":
        n = len(components)
        k = n - 3  # crowns = comps 1..K; branches at K+1, K+2
        pairs = [(0, 0)]
        crown_slots = sorted((1, 2, 3, 4), key=lambda s: np.arctan2(mv.GRAPHS[family][s]["center"][1], mv.GRAPHS[family][s]["center"][0]))
        crown_comps = sorted(range(1, k + 1), key=lambda j: np.arctan2(components[j]["center"][1], components[j]["center"][0]))
        pairs += [(s, j) for s, j in zip(crown_slots, crown_comps)]
        branch_comps = sorted((k + 1, k + 2), key=lambda j: components[j]["center"][0])
        pairs += [(5, branch_comps[0]), (6, branch_comps[1])]
        return pairs
    raise ValueError(family)


def comp_voxels(components: list[dict], resolution: int = 64) -> list[np.ndarray]:
    x, y, z = np.meshgrid(
        mv._cell_centers("x", resolution), mv._cell_centers("y", resolution),
        mv._cell_centers("z", resolution), indexing="ij", sparse=True)
    return [_component_occupancy(c, x, y, z) for c in components]


def main() -> int:
    cases = {c["case_id"]: c for c in load_public_cases()}
    gt = GtCache()

    theta_by_case: dict[str, tuple[str, list[float]]] = {}
    with SEALED_RECORDS.open("r", encoding="utf-8") as handle:
        for line in handle:
            rec = json.loads(line)
            if rec["method"] == "sppa_mvfit" and rec["condition"] == "clean" and rec["stratum"] == "csg_id":
                theta_by_case[rec["case_id"]] = (rec["family"], rec["metadata"]["theta"])
    if len(theta_by_case) != 120:
        raise RuntimeError(f"expected 120 sealed csg_id sppa_mvfit records, got {len(theta_by_case)}")

    rng = np.random.default_rng(77157)
    n_random = 100

    pair_rows: list[dict] = []
    shuffle_cyclic_rows: list[dict] = []
    shuffle_random_rows: list[dict] = []
    actor_true_mean: dict[str, float] = {}
    actor_random_mean: dict[str, float] = {}

    for case_id, (family, theta) in sorted(theta_by_case.items()):
        actor = mv.build_actor(family, theta)
        components = gt.actor(case_id)["components"]
        pairs = mapping_for(family, components)
        slot_vox = [mv.voxelize_actor([actor[s]], 64) for s, _ in pairs]
        comp_vox_all = comp_voxels(components, 64)
        comp_vox = [comp_vox_all[j] for _, j in pairs]

        inter = np.zeros((len(pairs), len(pairs)), dtype=np.int64)
        comp_counts = np.array([np.count_nonzero(c) for c in comp_vox], dtype=np.int64)
        slot_counts = np.array([np.count_nonzero(s) for s in slot_vox], dtype=np.int64)
        for a in range(len(pairs)):
            for b in range(len(pairs)):
                inter[a, b] = np.count_nonzero(slot_vox[a] & comp_vox[b])

        m = len(pairs)
        actor_covs: list[float] = []
        actor_ious: list[float] = []
        for a in range(m):
            c = max(int(comp_counts[a]), 1)
            union = int(slot_counts[a]) + int(comp_counts[a]) - int(inter[a, a])
            coverage = float(inter[a, a] / c)
            role_iou = float(inter[a, a] / union) if union > 0 else 1.0
            slot_index = pairs[a][0]
            pair_rows.append({"case_id": case_id, "family": family, "slot": slot_index,
                              "role": ROLES[family][slot_index], "component": pairs[a][1],
                              "coverage": coverage, "role_iou": role_iou})
            actor_covs.append(coverage)
            actor_ious.append(role_iou)
        actor_true_mean[case_id] = pooled_mean(actor_ious)

        # cyclic shift +1 control
        cyc_covs, cyc_ious = [], []
        for a in range(m):
            b = (a + 1) % m
            c = max(int(comp_counts[b]), 1)
            union = int(slot_counts[a]) + int(comp_counts[b]) - int(inter[a, b])
            cyc_covs.append(float(inter[a, b] / c))
            cyc_ious.append(float(inter[a, b] / union) if union > 0 else 1.0)
        shuffle_cyclic_rows.append({"case_id": case_id, "family": family,
                                    "coverage": pooled_mean(cyc_covs), "role_iou": pooled_mean(cyc_ious)})

        # random permutation control (mean over 100)
        rand_covs, rand_ious = [], []
        for _ in range(n_random):
            perm = rng.permutation(m)
            covs, ious = [], []
            for a in range(m):
                b = int(perm[a])
                c = max(int(comp_counts[b]), 1)
                union = int(slot_counts[a]) + int(comp_counts[b]) - int(inter[a, b])
                covs.append(float(inter[a, b] / c))
                ious.append(float(inter[a, b] / union) if union > 0 else 1.0)
            rand_covs.append(pooled_mean(covs))
            rand_ious.append(pooled_mean(ious))
        shuffle_random_rows.append({"case_id": case_id, "family": family,
                                    "coverage": pooled_mean(rand_covs), "role_iou": pooled_mean(rand_ious)})
        actor_random_mean[case_id] = pooled_mean(rand_ious)

    if len(pair_rows) != 920:
        raise RuntimeError(f"expected 920 matched pairs per frozen mapping, got {len(pair_rows)}")

    csg_cases = [cases[cid] for cid in sorted(theta_by_case)]

    per_family: dict[str, dict] = {}
    for family in ROLES:
        rows = [r for r in pair_rows if r["family"] == family]
        cyc = [r for r in shuffle_cyclic_rows if r["family"] == family]
        rnd = [r for r in shuffle_random_rows if r["family"] == family]
        per_role: dict[str, dict] = {}
        for role in ROLES[family]:
            role_rows = [r for r in rows if r["role"] == role]
            if role_rows:
                per_role[role] = {"n": len(role_rows),
                                  "coverage": pooled_mean([r["coverage"] for r in role_rows]),
                                  "role_iou": pooled_mean([r["role_iou"] for r in role_rows])}
        per_family[family] = {
            "n_pairs": len(rows),
            "coverage": pooled_mean([r["coverage"] for r in rows]),
            "role_iou": pooled_mean([r["role_iou"] for r in rows]),
            "shuffle_cyclic_coverage": pooled_mean([r["coverage"] for r in cyc]),
            "shuffle_cyclic_role_iou": pooled_mean([r["role_iou"] for r in cyc]),
            "shuffle_random_coverage": pooled_mean([r["coverage"] for r in rnd]),
            "shuffle_random_role_iou": pooled_mean([r["role_iou"] for r in rnd]),
            "per_role": per_role,
        }

    overall = {
        "n_pairs": len(pair_rows),
        "coverage": pooled_mean([r["coverage"] for r in pair_rows]),
        "role_iou": pooled_mean([r["role_iou"] for r in pair_rows]),
        "shuffle_cyclic_coverage": pooled_mean([r["coverage"] for r in shuffle_cyclic_rows]),
        "shuffle_cyclic_role_iou": pooled_mean([r["role_iou"] for r in shuffle_cyclic_rows]),
        "shuffle_random_coverage": pooled_mean([r["coverage"] for r in shuffle_random_rows]),
        "shuffle_random_role_iou": pooled_mean([r["role_iou"] for r in shuffle_random_rows]),
    }
    true_minus_random = bootstrap_paired(
        csg_cases, {cid: actor_true_mean[cid] - actor_random_mean[cid] for cid in actor_true_mean})

    lines = [
        "\\begin{tabular}{@{}lrrrrr@{}}",
        "\\toprule",
        "Family & $n$ pairs & Role coverage & Role IoU & Shuffle IoU (cyclic) & Shuffle IoU (random) \\\\",
        "\\midrule",
    ]
    for family in ROLES:
        pf = per_family[family]
        fam_tex = family.replace("_", "\\_")
        lines.append(f"{fam_tex} & {pf['n_pairs']} & {f3(pf['coverage'])} & {f3(pf['role_iou'])} & "
                     f"{f3(pf['shuffle_cyclic_role_iou'])} & {f3(pf['shuffle_random_role_iou'])} \\\\")
    lines += [
        "\\midrule",
        f"Overall (csg\\_id) & {overall['n_pairs']} & {f3(overall['coverage'])} & {f3(overall['role_iou'])} & "
        f"{f3(overall['shuffle_cyclic_role_iou'])} & {f3(overall['shuffle_random_role_iou'])} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    write_text(OUT / "role_aware_iou_table.tex", "\n".join(lines))

    payload = {
        "experiment": "E6 role-aware IoU",
        "label": "descriptive post-hoc, mapping frozen before computation",
        "mapping_document": "ROLE_MAPPING_FROZEN.md",
        "stratum_restriction": "csg_id only (120 actors), declared ex-ante",
        "n_actors": len(theta_by_case),
        "metric_grid": "voxel IoU/coverage at 64^3",
        "theta_source": "sealed_method_outputs.jsonl (no refitting)",
        "overall": overall,
        "per_family": per_family,
        "true_minus_shuffle_random_actor_iou": true_minus_random,
        "shuffle_protocol": {"cyclic_shift": 1, "random_permutations": n_random, "seed": 77157},
        "pair_rows": pair_rows,
    }
    write_json(OUT / "role_aware_iou.json", payload)

    print(f"pairs={overall['n_pairs']}  coverage={overall['coverage']:.4f}  role IoU={overall['role_iou']:.4f}")
    print(f"shuffle cyclic IoU={overall['shuffle_cyclic_role_iou']:.4f}  random IoU={overall['shuffle_random_role_iou']:.4f}")
    print(f"true-random: {true_minus_random['mean_difference']:.4f} "
          f"[{true_minus_random['ci95_low']:.4f}, {true_minus_random['ci95_high']:.4f}] p={true_minus_random['null_centered_two_sided_p']:.4f}")
    for family in ROLES:
        pf = per_family[family]
        print(f"  {family:22s} cov={pf['coverage']:.3f} iou={pf['role_iou']:.3f} (rand {pf['shuffle_random_role_iou']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
