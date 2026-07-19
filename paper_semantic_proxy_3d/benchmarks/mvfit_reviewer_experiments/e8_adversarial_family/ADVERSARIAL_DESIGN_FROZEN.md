# ADVERSARIAL_DESIGN_FROZEN.md — E8 adversarial anti-tautology stratum

**Status: FROZEN before any adversarial fit or IoU measurement.**
**Label: exploratory post-hoc analysis (not confirmatory).**

Freeze note: this document was written after reading the sealed generators
(`source/source_generators.py`), the sealed graphs (`method/graphs.json`), the
sealed fitter (`method/sppa_mvfit.py`) and the existing reviewer experiments
(e1–e6), but **before** running any fit on an adversarial actor. The only
computation performed before freezing was a *protocol equivalence* probe:
the 120 csg_id test actors regenerate bit-exactly from the seeds stored in
`data/test/private_source_actors.jsonl` (120/120), and the sealed csg_id
clean means are SPPA 0.5506 / Generic 0.3421 (Δ = 0.2085). No adversarial
actor was fitted or scored before this freeze.

## Reviewer question

"H1 is nearly tautological: the graph designed for family F wins on actors
built with the topology of F." Antidote: build actors that **keep the
semantic class but violate the structural prior** of the family graph, then
measure whether the family graph degrades with grace or collapses, and how
much of the clean Δ (SPPA − Generic) survives.

## Design (frozen)

- **Base actors.** The 120 csg_id held-out test actors, regenerated from
  their stored seeds (`generate_source_actor(family, "csg_id", seed)`); the
  runner aborts unless regeneration is bit-exact (JSON equality) for all
  120. Same base seeds as the sealed benchmark — the code allows it, so the
  clean↔adversarial pairing is exact per actor.
- **Adversarial actors.** 120 = 6 families × 20: per family, base actors
  0–9 → violation V1, base actors 10–19 → violation V2 (12 violation types
  total). Violation randomness (and only that) comes from
  `np.random.default_rng(880000000 + 1000 * family_index + actor_index)`,
  family_index in the sealed family order of `protocol_config.json`.
  These seeds are disjoint from the development seeds (110000+) and from
  the NIST-derived test seeds, and are frozen here.
- **Case ids.** `e8-adv-{family}-{index:03d}`; stratum label
  `adversarial_e8`. Each actor dict records: base case_id, base seed, e8
  seed, violation type, and measured violation quantities (e.g., cargo
  volume ratio) — the per-actor explicit documentation.
- **Representation.** Adversarial actors use only box / cylinder /
  ellipsoid components (the csg_id vocabulary), so the sealed analytic
  projection path (`render_source_masks`, 256→96) and `voxelize_source`
  apply unchanged; `actor["stratum"]` stays `"csg_id"` *as the projection
  dispatch key* (documented here; the case-level stratum is
  `adversarial_e8`). No tube/superellipsoid: the analytic projector does
  not handle them, and switching to ray-sampled projection would break
  protocol equivalence with the seal.
- **Fitting protocol.** Identical to the sealed primary: clean top+side
  masks at 96² (output of `render_source_masks`), `infer_method` with the
  TRUE family token for SPPA-MVFit and the generic graph for
  Generic-MVFit, frozen bounds, 31-candidate budget, deterministic
  coordinate descent. No monkeypatching of anything.
- **Evaluation.** Voxel IoU at 64³ vs `voxelize_source` of the adversarial
  actor. Clean references per base case come from the sealed
  `results/test/raw_metrics.csv` (clean condition, csg_id) — not
  recomputed.
- **World check.** Every adversarial actor must pass
  `validate_actor_inside_world` (80³ boundary check) before any fit; the
  runner aborts otherwise.
- **Violation predicates.** A battery of 12 predicates (one per violation
  type, listed below) runs before any fit and aborts on failure, so the
  documented violations are enforced, not just intended.

## Metrics (frozen)

- Primary: per-case Δ_adv = IoU(SPPA) − IoU(Generic) on adversarial
  actors; stratified paired bootstrap (cells = family, mean of cell means,
  10 000 resamples, seed 77157 — the sealed scheme).
- Degradation: per-case SPPA_adv − SPPA_clean and Generic_adv −
  Generic_clean (paired by base actor), same bootstrap.
- ΔΔ: per-case (SPPA_adv − Generic_adv) − (SPPA_clean − Generic_clean),
  same bootstrap — "how much of the family-prior advantage dies when the
  prior is wrong".
- Frontier map: share of actors with SPPA < Generic, per family and per
  violation type; families/violations where SPPA loses are reported, not
  hidden.
- Reference: clean csg_id Δ from the sealed CSV (0.2085; the sealed
  two-stratum H1 Δ is 0.190).
- Aggregation: mean of family means for global numbers (matches the sealed
  cell scheme); per-family and per-violation breakdowns reported.

## The 12 violations (frozen definitions)

Notation: components are indexed by the csg_id construction order documented
in `e6_role_aware/ROLE_MAPPING_FROZEN.md`. L/W/H = the actor's own body
length/width/height; u ~ U(0,1) draws from the actor's e8 rng.

### compact_vehicle (graph prior: cabin front-of-center, wheels ±axle, small front box)

- **V1 `roof_cargo_250` (idx 0–9).** Append a roof cargo box centered on the
  cabin: footprint (0.50·L, 0.95·cabin_width), volume = 2.5 × the actor's
  cabin bounding-box volume (height derived from the volume, safety clamp
  2.5 m, never binding: the generator ranges need at most ≈ 2.46 m). Sits on
  the cabin top.
  Violates: the only secondary mass above the body is the cabin prior
  (secondary_scale ≤ 1.35 cannot express a separate 2.5× volume).
- **V2 `cab_rearward` (idx 10–19).** Cabin moved to x = −(0.34 + 0.06·u)·L
  (outside the fitter's reachable cabin offset for long bodies:
  secondary_offset·default_length·sx bottoms out ≈ −1.06·sx); the small
  front box is replaced by a front cargo hood (0.42·L, 0.88·W, 0.85·body_h)
  at x = +0.30·L. Violates: cabin-position prior and front-box scale prior.

### articulated_vehicle (graph prior: front tractor+cabin, single trailer, 4 axles)

- **V1 `centered_cab_split_cargo` (idx 0–9).** Cabin centered at the
  tractor–trailer midpoint; the trailer is split into two boxes of length
  (trailer_L − 0.45)/2 separated by a 0.45 m gap. Violates: single
  contiguous cargo prior and cabin-over-tractor prior.
- **V2 `double_trailer` (idx 10–19).** The trailer becomes two trailers in
  series (each 0.44·trailer_L, centers ±0.25·trailer_L, staying inside the
  original envelope), plus a drawbar box between them and a **5th axle**
  wheel cylinder at the trailer midpoint. Violates: single-trailer prior
  and 4-axle prior (graph has exactly 4 wheel slots).

### quadruped (graph prior: 4 equal legs supporting the body)

- **V1 `asymmetric_legs` (idx 0–9).** One end (front or rear, coin flip)
  gets leg factor u_t ∈ [1.35, 1.70], the other u_s ∈ [0.55, 0.72]; feet
  stay on the ground (leg center = h′/2); the body rests on the TALL legs
  (body z = tall_top + 0.46·body_h), head/neck/tail shift with the body.
  Short legs no longer reach the body. Violates: symmetric-support prior
  (the graph's 4 identical leg slots with one shared z-scale).
- **V2 `giraffe_neck` (idx 10–19).** The horizontal neck cylinder is
  replaced by a vertical cylinder of height u ∈ [1.6, 2.1]·body_h at the
  same x; the head sits on top of it. Violates: neck orientation/height
  prior (graph neck is a short horizontal x-cylinder; no fit DOF can stand
  it up).

### branching_vertical (graph prior: vertical trunk, top-centered crowns)

- **V1 `leaning_25` (idx 0–9).** A 25° lean (tan 25° = 0.4663) with azimuth
  φ = choice(0, π) + U(−0.55, +0.55) (x-dominant cones, keeps the actor
  inside the narrower y-world). The trunk becomes 3 stacked cylinders
  offset by tan25°·z_mid per tier; every crown/branch is translated by
  tan25°·z_center along the lean direction. Violates: vertical-axis prior
  (the 5-parameter fit has no shear).
- **V2 `cascade_crown` (idx 10–19).** All K crowns on ONE side (azimuth
  φ0 ± U(−0.3, 0.3), radial 0.35–0.75) at cascaded heights
  z_i = trunk_H·(0.42 + 0.55·i/(K−1)). Violates: crown-at-top and
  uniform-azimuth priors (graph crowns cluster at z ≈ 3.2–3.8 around the
  trunk).

### lattice_tower (graph prior: vertical core/legs, platforms shrinking with z)

- **V1 `leaning_25` (idx 0–9).** Same 25° staircase scheme as
  branching_vertical V1: core → 3 stacked boxes, each leg → 3 stacked
  cylinders (offset tan25°·z_mid per tier), platforms translated by
  tan25°·z and kept level. 19 components. Violates: vertical-axis prior.
- **V2 `platforms_out_of_order` (idx 10–19).** The four platform sizes are
  reversed bottom↔top (largest platform on top, then ×1.25 in x/y) at the
  same heights. Violates: taper prior (platform size order is graph-fixed;
  the fit can only scale all secondary slots together).

### rider_cycle (graph prior: y-symmetric, upright rider)

- **V1 `sidecar` (idx 0–9).** Add a sidecar box (0.72, 0.62, 0.38) at
  (x = −0.25·sep + U(−0.1, 0.1)·sep, y = +0.72, z = 0.52) and a third
  wheel (r = 0.34, axis y) at (same x, y = +0.95, z = 0.34). Violates:
  y-symmetry prior (every graph slot is centered at y = 0).
- **V2 `recumbent` (idx 10–19).** The torso becomes horizontal
  (size (max(0.8, 0.9·torso_h), 0.36, 0.44), center z = frame_z + 0.28,
  x = −0.05·sep) and the head moves to its front end
  (x = torso_x + torso_len/2 + 0.4·head_r, z = frame_z + 0.52). Violates:
  upright-rider prior (graph torso is a vertical ellipsoid; slots cannot
  rotate).

## Violation predicate battery (runs pre-fit, aborts on failure)

1. compact V1: exists a box with volume ≥ 2.4 × cabin bbox volume and
   z_center > cabin z_center.
2. compact V2: cabin x < −0.30·L and exists a box with size_x ≥ 0.35·L
   and center_x > 0 (the hood).
3. articulated V1: |cabin_x − (tractor_x + trailer_x)/2| < 1e-6 and two
   cargo boxes with lengths (trailer_L − 0.45)/2 ± 1e-6.
4. articulated V2: exactly 5 axis-y wheel cylinders and 2 trailer boxes
   and 1 drawbar.
5. quadruped V1: tall/short leg height ratio ≥ 1.8 and short-leg top <
   body bottom − 0.2.
6. quadruped V2: neck is a z-cylinder with size_z ≥ 1.5·body_h and head
   z_center above the neck base.
7. branching V1: trunk replaced by 3 z-cylinders whose (x,y) offsets equal
   tan25°·z_mid·(cosφ, sinφ) within 1e-6; crowns offset by tan25°·z within
   1e-6.
8. branching V2: all crown azimuths within 0.65 rad (circular distance)
   of φ0; crown z-span ≥ 0.4·trunk_H.
9. lattice V1: core replaced by 3 boxes and legs by 12 cylinders with
   tier offsets tan25°·z_mid within 1e-6; platform z unchanged.
10. lattice V2: platform size_x strictly ascending with z; top platform
    size_x ≥ 1.2 × original bottom platform size_x.
11. rider V1: exists components with center_y > 0.4; exactly 3 axis-y
    wheel cylinders.
12. rider V2: torso size_x > size_z and torso z_center < frame_z + 0.45
    (well below the upright-torso prior z ≈ frame_z + 0.62·wheel_r +
    0.48·torso_h).

## Analysis outputs (frozen)

- `results.jsonl` — one row per adversarial actor (120): ids, seeds,
  violation info, SPPA/Generic adversarial IoU, sealed clean IoUs, deltas.
- `adversarial_results.json` — full payload (bootstraps, per-family,
  per-violation, frontier shares, validation records).
- `adversarial_table.tex` — booktabs per-family table (pattern of
  `e3_obb/obb_baseline_table.tex`; supplement wraps it in \scriptsize).
- `adversarial_violations_table.tex` — booktabs per-violation table.
- `README.md` — question, protocol, headline numbers, honest interpretation.

## Honesty clause

If SPPA-MVFit loses to Generic-MVFit (or collapses below the visual-hull
class of semantics-free methods) for some family or violation, that is the
frontier map the paper wants and it will be reported as-is.

## Errata (transparent, pre-measurement)

- The safety clamp of `roof_cargo_250` was first written as 2.2 m with the
  claim "never binding for the generator ranges"; the pre-fit predicate
  battery caught that this arithmetic was wrong (the volume-derived height
  reaches ≈ 2.46 m for the largest cabins, so a 2.2 m clamp WOULD bind and
  silently weaken the violation below the frozen 2.5× ratio). Corrected to
  2.5 m (never binding) before any fit was run; the frozen violation itself
  (cargo volume = 2.5 × cabin volume) is unchanged.
- Predicate 12 (`recumbent`) was first written as torso z < 1.3·frame_z;
  for small wheels (frame_z ≈ 0.45) that bound sits BELOW the violated
  torso position, so the predicate — not the violation — was inconsistent.
  Rewritten as torso z < frame_z + 0.45 (always consistent with the frozen
  transformation and still far below the upright-torso prior) before any
  fit was run.
