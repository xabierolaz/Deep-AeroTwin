# E8 — Adversarial anti-tautology stratum

**Label: exploratory post-hoc analysis (not confirmatory).**
**Design frozen in `ADVERSARIAL_DESIGN_FROZEN.md` before any fit.**

## Question

The reviewer critique: "H1 is nearly tautological — the graph designed for
family F wins on actors built with the topology of F." Antidote: actors that
**keep the semantic class but violate the structural prior** of their family
graph. Does the family graph degrade with grace or collapse? How much of the
clean Δ (SPPA − Generic) survives?

## Design

- **120 adversarial actors** = 6 families × 20 (2 frozen violation types per
  family, 10 actors each), derived from the exact 120 csg_id test actors
  (same stored seeds; regeneration validated bit-exact, 120/120). Violation
  randomness: `default_rng(880000000 + 1000·family_index + actor_index)`.
- Violations (all documented per-actor in `results.jsonl`):
  - compact_vehicle: `roof_cargo_250` (roof cargo = 2.5× cabin volume),
    `cab_rearward` (cabin at −0.34..−0.40·L + front cargo hood).
  - articulated_vehicle: `centered_cab_split_cargo` (cabin at vehicle
    center, trailer split in two), `double_trailer` (two trailers + 5th axle).
  - quadruped: `asymmetric_legs` (one end ×1.35–1.70, other ×0.55–0.72;
    short legs no longer reach the body), `giraffe_neck` (vertical neck
    1.6–2.1× body height, head on top).
  - branching_vertical: `leaning_25` (25° lean, trunk as 3 stacked segments),
    `cascade_crown` (all crowns on one side, heights cascading mid→top).
  - lattice_tower: `leaning_25` (25° staircase lean; core 3 boxes, legs 12
    cylinders, platforms translated level), `platforms_out_of_order`
    (platform sizes reversed bottom↔top, top ×1.25).
  - rider_cycle: `sidecar` (sidecar + third wheel at +y),
    `recumbent` (horizontal torso at frame height).
- **Same protocol as the sealed primary**: same clean top+side silhouettes
  pipeline (`render_source_masks`, 256→96), same fitter (`infer_method`,
  true family token, frozen bounds, 31-candidate budget), same voxel IoU at
  64³ vs `voxelize_source`. Clean references are the sealed
  `raw_metrics.csv` rows of the same base actors (csg_id, clean).
- Pre-fit gates: bit-exact base regeneration, 12/12 violation predicates,
  inside-world check, no empty-observation fallbacks. Two pre-measurement
  errata (clamp level, one predicate bound) are documented transparently in
  the frozen design doc.

## Headline numbers (n = 120, adversarial stratum)

| | SPPA-MVFit | Generic-MVFit | Δ (paired) |
|---|---|---|---|
| Clean (same actors, sealed) | 0.551 | 0.342 | **+0.209** [sealed CSV] |
| **Adversarial** | **0.417** | **0.276** | **+0.141 [+0.125, +0.157], p < 1e-4** |

- **ΔΔ (adv − clean) = −0.068 [−0.087, −0.048], p < 1e-4**: violating the
  prior kills ≈ 32 % of the family-graph advantage — but ≈ 68 % survives.
- Degradation is asymmetric as predicted by the critique: SPPA falls
  −0.134 [paired CI in JSON], Generic only −0.066. The family graph has
  more to lose, and does — without ever losing the family-level lead.
- **Frontier map (SPPA < Generic per-actor share): 8.3 % overall.**
  Per family: compact 10 %, branching 20 %, lattice 20 %, others 0 %.

## The frontier (per-violation table — the honest part)

| Violation | SPPA adv | Gen adv | Δ_adv | CI95 | SPPA<Gen |
|---|---|---|---|---|---|
| compact roof_cargo_250 | 0.390 | 0.328 | +0.063 | [+0.044, +0.082] | 0 % |
| compact cab_rearward | 0.571 | 0.524 | +0.048 | [−0.003, +0.093] | 20 % |
| articulated centered_cab_split_cargo | 0.436 | 0.360 | +0.076 | [+0.059, +0.096] | 0 % |
| articulated double_trailer | 0.494 | 0.379 | +0.114 | [+0.094, +0.133] | 0 % |
| quadruped asymmetric_legs | 0.526 | 0.358 | +0.168 | [+0.146, +0.191] | 0 % |
| quadruped giraffe_neck | 0.548 | 0.415 | +0.134 | [+0.090, +0.182] | 0 % |
| branching leaning_25 | 0.323 | 0.135 | +0.188 | [+0.148, +0.230] | 0 % |
| **branching cascade_crown** | **0.364** | **0.357** | **+0.007** | **[−0.015, +0.029]** | **40 %** |
| **lattice leaning_25** | **0.076** | **0.067** | **+0.009** | **[−0.008, +0.026]** | **40 %** |
| lattice platforms_out_of_order | 0.346 | 0.109 | +0.237 | [+0.176, +0.298] | 0 % |
| rider sidecar | 0.442 | 0.121 | +0.320 | [+0.252, +0.386] | 0 % |
| rider recumbent | 0.486 | 0.161 | +0.325 | [+0.278, +0.365] | 0 % |

**SPPA's advantage collapses to a statistical tie in two cells:**

1. `lattice_tower / leaning_25`: a 25°-leaning tower is a shear, and no
   amount of axis-aligned scaling (the only fit DOF) expresses it — SPPA
   falls to 0.076. But Generic is an equally rigid vertical stack (0.067):
   both methods sit at the floor. The family prior is destroyed, yet nothing
   semantics-free does better either.
2. `branching_vertical / cascade_crown`: crowns strung down one side
   mislead the crown slots (they cluster near the top), and the generic
   blob covers a one-sided mass about as well (0.364 vs 0.357, 40 % of
   actors inverted).
3. `compact / cab_rearward` is marginal (+0.048, CI touches 0): the cabin
   slot cannot reach far enough rearward for long bodies.

Everywhere else the family graph keeps a large, significant lead — including
violations one might have expected to hurt more (sidecar +0.320,
platforms_out_of_order +0.237, asymmetric_legs +0.168).

## Interpretation

H1 is **not tautological**: on actors that systematically violate the family
priors, the family graph retains ~2/3 of its clean advantage (Δ +0.141 vs
+0.209, p < 1e-4), because most violations break one slot's prior while the
remaining topology still shapes the fit. But the degradation is real and
larger for SPPA than for Generic (−0.134 vs −0.066), and the frontier is
mappable: violations that remove a *global* geometric regularity the
5-parameter fit cannot express at all (shear/lean of a vertical stack), or
that move mass where no slot can reach, erase the advantage to a tie. That
boundary — not a blanket win — is what the paper should claim.

## Files

- `ADVERSARIAL_DESIGN_FROZEN.md` — frozen design, 12 violation definitions,
  predicate battery, errata.
- `adversarial_generators.py` — the 12 transformations + predicates.
- `run_e8_adversarial_family.py` — runner (exactly reproducible).
- `results.jsonl` — one row per actor (120): ids, seeds, violation info,
  adversarial and sealed clean IoUs, deltas.
- `adversarial_results.json` — full payload (bootstraps, per-family,
  per-violation, validation gates).
- `adversarial_table.tex` — booktabs per-family table.
- `adversarial_violations_table.tex` — booktabs per-violation table.

## Seeds / determinism

Base actors: sealed test seeds (bit-exact regeneration). Violation RNG:
880 000 000 + 1000·family_index + actor_index. Fitter: deterministic.
Bootstrap: 10 000 resamples, seed 77157 (sealed scheme).

## Limitations

- Adversarial actors are synthetic CSG compositions (same primitive
  vocabulary as csg_id), not natural objects; "semantic class preserved" is
  by construction of the transformation, documented per type.
- The 25° leans are staircase approximations of a true shear (axis-aligned
  vocabulary); the lean direction is restricted to x-dominant cones
  (±0.55 rad) to stay inside the narrower y-world.
- Only the clean condition is tested (mirrors e1–e6 scope).
- Each violation type has n = 10; per-cell CIs are wide by design.
