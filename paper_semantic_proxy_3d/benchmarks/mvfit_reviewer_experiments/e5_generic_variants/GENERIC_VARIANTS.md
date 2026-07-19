# GENERIC_VARIANTS.md — design criteria for E5 (frozen BEFORE measurement)

**Label:** exploratory post-hoc analysis (not confirmatory).
**Date of design freeze:** before any variant was fitted or evaluated. This
document records the design rules; `generic_variants.json` is the frozen
artifact; `run_e5_generic_variants.py` verifies the G4 derivation rule against
the sealed family graphs and aborts on mismatch.

## Motivation

The sealed `generic` graph (`method/graphs.json`, 8 ellipsoids, symmetric) is
hand-crafted. Reviewer question: how much of the SPPA-vs-generic gap
(Δ = 0.557 − 0.367 = 0.190) survives when the generic graph is designed
differently but still "reasonably"? We pre-register three alternative design
philosophies, all satisfying the frozen interface:

- exactly 8 slots (interface requirement of `build_actor`),
- slot 0 is the only non-secondary slot (matches every family graph),
- same primitive vocabulary (box / cylinder / ellipsoid, axis in {x, y, z}),
- proportions grounded in the family graphs' observed ranges, never in test
  results — no variant was tuned against any metric.

## G1 (control) — sealed generic

The frozen graph from `method/graphs.json` re-run for validation.

## G2 — "box/cylinder chassis" (mechanical-object generic)

Design rule: mirror the *structural pattern most common across the six family
graphs* without copying any family: a primary box main body, a smaller
secondary box upper body, four cylinder supports at the corners (wheel/leg
role), and two small box end attachments (front/rear). Box+cylinder is the
dominant vocabulary of the vehicle-like families (compact, articulated,
lattice); proportions are mid-ranges of those graphs, not of any single one.

- slot 0: box, center [0, 0, 0.90], size [3.00, 1.40, 1.00], axis z, primary
- slot 1: box, center [0, 0, 1.70], size [1.40, 1.20, 0.80], axis z
- slots 2–5: cylinder, centers [±1.00, ±0.55, 0.45], size [0.50, 0.30, 0.50], axis y
- slot 6: box, center [1.60, 0, 0.90], size [0.40, 1.20, 0.50], axis z
- slot 7: box, center [−1.60, 0, 0.90], size [0.40, 1.20, 0.50], axis z

## G3 — "vertical stack + legs" (organic-object generic)

Design rule: the complementary philosophy — a vertical chain of three
ellipsoids (trunk/torso/head roles, as in quadruped, branching_vertical,
rider_cycle) standing on four thin box legs, plus one thin cylinder side
appendage (arm/tail/handle role). Proportions are mid-ranges of the
organic-looking family graphs.

- slot 0: ellipsoid, center [0, 0, 1.20], size [1.60, 0.90, 0.90], axis x, primary
- slot 1: ellipsoid, center [0, 0, 2.00], size [1.00, 0.70, 0.80], axis z
- slot 2: ellipsoid, center [0, 0, 2.70], size [0.60, 0.50, 0.50], axis z
- slots 3–6: box, centers [±0.55, ±0.30, 0.50], size [0.18, 0.18, 1.00], axis z
- slot 7: cylinder, center [0.80, 0, 1.90], size [0.70, 0.15, 0.15], axis x

## G4 — "slot-wise mean of the family graphs" (data-driven generic)

Design rule (fully mechanical, no hand choices): for each slot index 0–7 take
the six family graphs' slots and compute

- **type:** majority vote; ties broken by global type frequency across all
  family graphs (cylinder 28 > box 12 > ellipsoid 8),
- **axis:** majority vote (first-most-common),
- **secondary:** majority vote,
- **center/size:** element-wise arithmetic mean across the six families.

Result (verified programmatically by the runner against `graphs.json`):

- slot 0: box z primary, center [−0.388, 0, 1.227], size [1.673, 0.862, 1.922]
- slots 1–6: cylinder z, centers/sizes per JSON
- slot 7: cylinder y, center [0.507, 0.080, 1.807], size [0.515, 1.047, 0.283]

## Hypothesis registered before measurement

If the generic design drives the gap, G4 (data-driven) should recover the
most IoU and shrink Δ noticeably; if the gap is dominated by *family-specific
structure* (articulated cabins, lattice platforms, crown arrangements), even a
well-designed single generic graph should stay far below SPPA and Δ should
remain large. We report each variant's mean IoU, the resulting Δ vs the
sealed SPPA per-case IoUs, and paired bootstrap CIs against the sealed
generic per-case IoUs (n = 240, clean).
