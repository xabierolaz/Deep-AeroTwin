# ROLE_MAPPING_FROZEN.md — slot ↔ GT component mapping for E6

**Status: FROZEN before any role-aware computation.**
**Label: descriptive post-hoc, mapping frozen before computation.**
Date/freeze note: this document was written after reading
`method/graphs.json` (slot geometry) and `source/source_generators.py`
(component construction order) but **before** computing any role-level metric.

## Stratum restriction (declared ex-ante)

The analysis is **restricted to the csg_id stratum (120 actors)**.

Justification: csg_id sources are CSG compositions of the same primitive
vocabulary as the graphs (box / cylinder / ellipsoid), generated in a fixed,
documented order, so a geometric slot↔component mapping is well-defined. The
implicit_ood generators use different primitive kinds (superellipsoid,
tapered_extrusion, tube, torus_y) whose component inventories do **not**
align 1:1 with the 8 graph slots (e.g., compact_vehicle OOD has 5 components
vs 8 slots — 2 torus wheels instead of 4 wheel slots, no bumper; lattice OOD
has 8 components but 4 are diagonal leg tubes with no slot analog; crown
counts differ). Any OOD mapping would need per-family fudge rules decided
while looking at the data — not defensible. Declared here, before seeing any
result.

## General rules

1. Mapping is defined **per family** between graph slot indices (0–7) and GT
   component indices in the exact construction order of
   `_generate_csg_id` in `source/source_generators.py`.
2. Matches follow (a) construction order when it is identical on both sides,
   or (b) an explicit geometric sort key (x-position or azimuth), stated per
   family below.
3. Slots or components without a counterpart are **unmatched** and excluded
   from role metrics (counted and reported).
4. The fitted slot geometry comes from the SEALED θ
   (`results/test/sealed_method_outputs.jsonl`, method `sppa_mvfit`,
   condition `clean`) via `build_actor(family, theta)`; no refitting.
5. Metrics per matched pair (slot s, component c) at 64³:
   - role coverage = |vox(s) ∩ vox(c)| / |vox(c)|  (fraction of the GT
     component covered by its correct slot),
   - role IoU = |vox(s) ∩ vox(c)| / |vox(s) ∪ vox(c)|.
6. Shuffle control: (i) deterministic cyclic shift +1 of the matched
   component assignment within each actor; (ii) mean over 100 random
   permutations (seed 77157) of the within-actor assignment.

## Per-family mapping (csg_id)

### compact_vehicle — GT 7 components / 8 slots
GT order: 0 body box, 1 cabin ellipsoid, 2 wheel(−axle,−y), 3 wheel(−axle,+y),
4 wheel(+axle,−y), 5 wheel(+axle,+y), 6 front box (x = +0.51·L).

| Slot | Role | GT comp | Rule |
|---|---|---|---|
| 0 | body | 0 | order |
| 1 | cabin | 1 | order |
| 2 | wheel_rear_left | 2 | order (same quadrant convention) |
| 3 | wheel_rear_right | 3 | order |
| 4 | wheel_front_left | 4 | order |
| 5 | wheel_front_right | 5 | order |
| 6 | bumper_rear | — | unmatched (GT has no rear bumper) |
| 7 | bumper_front | 6 | sign of center x (front = +x) |

### articulated_vehicle — GT 8 / 8
GT order: 0 tractor box, 1 cabin ellipsoid, 2 trailer box, 3 hitch box,
4–7 wheels (x-ordered by construction: tractor−0.25L, tractor+0.27L,
trailer−0.27L, trailer+0.30L).

| Slot | Role | GT comp | Rule |
|---|---|---|---|
| 0 | tractor | 0 | order |
| 1 | cabin | 1 | order |
| 2 | trailer | 2 | order |
| 3 | hitch | 3 | order |
| 4–7 | wheel_1..4 | 4–7 | both sides x-ordered |

### quadruped — GT 8 / 8
GT order matches slot order exactly (body, head, legs in the same quadrant
convention, neck at +x, tail at −x): slot i ↔ comp i for all 8.
Roles: body, head, leg_rear_left, leg_rear_right, leg_front_left,
leg_front_right, neck, tail.

### branching_vertical — GT 1 + K + 2 (K ∈ {4..7}) / 8
GT order: 0 trunk, 1..K crown ellipsoids (azimuth ≈ 2π·idx/K + jitter),
K+1 branch cylinder at x = −0.48, K+2 branch cylinder at x = +0.48.

| Slot | Role | GT comp | Rule |
|---|---|---|---|
| 0 | trunk | 0 | order |
| 1–4 | crown_1..4 | 4 of the K crowns | sort slots 1–4 and GT crowns by azimuth atan2(cy, cx), match in order; GT crowns beyond the 4th unmatched |
| 5 | branch_left | K+1 | sign of center x |
| 6 | branch_right | K+2 | sign of center x |
| 7 | branch_y | — | unmatched (GT has no y-branch) |

### lattice_tower — GT 9 / 8
GT order: 0 core box, 1–4 legs (same quadrant convention), 5–8 platform boxes
at z = 0.22H, 0.48H, 0.74H, 0.93H.

| Slot | Role | GT comp | Rule |
|---|---|---|---|
| 0 | core | 0 | order |
| 1–4 | leg_1..4 | 1–4 | order (same quadrant convention) |
| 5 | platform_low | 5 | both sides sorted by z, matched in order |
| 6 | platform_mid | 6 | z order |
| 7 | platform_high | 7 | z order; GT top platform (8) unmatched |

### rider_cycle — GT 8 / 8
GT order matches slot order exactly (rear wheel, front wheel, three frame
tubes in x order, torso, head, fork/handlebar): slot i ↔ comp i for all 8.
Roles: wheel_rear, wheel_front, frame_main, frame_mid, frame_front, torso,
head, fork.

## Expected unmatched inventory (csg_id)

- compact_vehicle: slot 6 (bumper_rear) — 20 actors × 1 slot.
- branching_vertical: slot 7 (branch_y); GT crowns beyond the 4th (K−4 per
  actor).
- lattice_tower: GT top platform (comp 8) — 20 actors × 1 comp.
- All other slots/components matched. Matched pairs per actor: compact 7,
  articulated 8, quadruped 8, branching 7, lattice 8 (1 core + 4 legs + 3
  platforms), rider 8 → total expected 20×(7+8+8+7+8+8) = 920 pairs.
  *(Erratum corregido al escribir el runner: la primera versión de esta línea
  decía "lattice 7 / 900" por un error aritmético al sumar; la tabla de
  mapeo de lattice_tower — la parte congelada — siempre tuvo 8 pares.)*
