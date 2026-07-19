# E6 — Role-aware IoU (slot ↔ GT component correspondence)

**Label: descriptive post-hoc, mapping frozen before computation.**

## Question

Does SPPA-MVFit assign the *right* geometry to the *right* slot, or does it
reach its global IoU by spreading mass across slots? Role-aware evaluation of
the fitted actors against GT components.

## Anti-cherry-picking protocol

1. `ROLE_MAPPING_FROZEN.md` was written **before** any computation: explicit
   slot↔component mapping per family, based only on the graph slot geometry
   (`graphs.json`) and the construction order of the csg_id generators.
2. The same document declares **ex-ante** the restriction to the csg_id
   stratum (120 actors): implicit_ood component inventories (superellipsoids,
   tubes, tori, tapered extrusions) do not align 1:1 with the 8 slots, and no
   defensible mapping exists there.
3. Fitted slots come from the **sealed** θ
   (`sealed_method_outputs.jsonl`, sppa_mvfit, clean) — no refitting.
4. One documentation erratum was corrected transparently when writing the
   runner (lattice matched-pair count 7→8 in the *expected-inventory* note;
   the frozen mapping table itself was not touched).

## Method

Per matched pair (slot s, GT component c), both voxelized at 64³:
- role coverage = |s ∩ c| / |c| (fraction of the GT component covered by its
  correct slot),
- role IoU = |s ∩ c| / |s ∪ c|.

Controls: within-actor cyclic shift +1, and mean over 100 random permutations
(seed 77157) of the slot→component assignment, computed from the precomputed
m×m intersection matrix per actor.

## Headline numbers (120 actors, 920 matched pairs)

| Family | n pairs | Coverage | Role IoU | Shuffle IoU (random) |
|---|---|---|---|---|
| compact_vehicle | 140 | 0.724 | 0.413 | 0.062 |
| articulated_vehicle | 160 | 0.614 | 0.285 | 0.046 |
| quadruped | 160 | 0.707 | 0.423 | 0.062 |
| branching_vertical | 140 | 0.304 | 0.187 | 0.066 |
| lattice_tower | 160 | 0.344 | 0.231 | 0.032 |
| rider_cycle | 160 | 0.569 | 0.372 | 0.052 |
| **Overall** | **920** | **0.545** | **0.319** | **0.053** |

True mapping − random control (actor-level, stratified paired bootstrap,
10 000 resamples, seed 77157): **+0.265 [+0.250, +0.281], p < 1e-4**.

## Interpretation

The fitted slots are semantically aligned with the GT parts far above chance
(role IoU 0.319 vs 0.053 random, 0.017 cyclic): the fit is not an amorphous
blob. Alignment is strongest for compact_vehicle and quadruped and weakest
for branching_vertical and lattice_tower — the same families with the lowest
global IoU, so the role analysis is consistent with (and explains part of)
the family difficulty ranking. Descriptive only; no confirmatory claim.

## Files

- `ROLE_MAPPING_FROZEN.md` — frozen mapping + ex-ante stratum restriction.
- `run_e6_role_aware.py` — runner (exactly reproducible).
- `role_aware_iou.json` — full payload incl. per-pair rows.
- `role_aware_iou_table.tex` — booktabs table.

## Seeds / determinism

Sealed θ (deterministic); shuffle RNG seed 77157; bootstrap seed 77157.
