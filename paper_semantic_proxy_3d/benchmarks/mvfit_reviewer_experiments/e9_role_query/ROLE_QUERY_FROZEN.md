# ROLE_QUERY_FROZEN.md — E9 operational utility of semantic roles

**Status: FROZEN before any role-query metric computation.**
**Label: exploratory post-hoc analysis (not confirmatory).**

Freeze note: written after reading `method/graphs.json`,
`source/source_generators.py`, the sealed method outputs and the frozen
`e6_role_aware/ROLE_MAPPING_FROZEN.md`, but **before** computing any
role-query metric. The only pre-freeze computations were protocol
equivalence probes (bit-exact base regeneration in E8; presence of sealed
generic θ for all 120 csg_id cases).

## Reviewer question

"The visual hull gives 0.522 IoU at 0.22 ms without roles — what are roles
FOR?" E6 showed slot↔role alignment exists (role IoU 0.319 vs 0.053
shuffle); E9 operationalizes roles as a TASK: **part query** ("where is the
cargo / the wheels / the cabin?") plus a **part counting** task.

## Frozen task definition

- **Query set.** The 920 matched (slot, GT component) pairs of the frozen
  e6 mapping (120 csg_id actors; stratum restriction inherited ex-ante from
  e6 — implicit_ood has no defensible slot↔component mapping). Each pair is
  one query: "return the voxels of role R in actor A".
- **Ground truth.** Voxels of the mapped GT component at 64³
  (`_component_occupancy` on the sealed grid, as in e6).
- **Answers per method** (all geometry from SEALED fits, no refitting):
  - **SPPA-MVFit**: voxels of the fitted slot for role R (sealed sppa θ,
    `build_actor(family, θ)`, slot voxelized at 64³ — identical pipeline to
    e6).
  - **Generic-MVFit**: voxels of generic slot g(R) from the sealed generic
    θ, with the frozen mapping g below.
  - **Hull-HEUR-A (`largest_cc`)**: the largest 26-connected component of
    the visual hull at 64³ (same answer for every role).
  - **Hull-HEUR-B (`lower_half_z`)**: hull voxels with z_center ≤
    (z_min + z_max)/2 of the occupied hull voxels (same answer for every
    role).
  The two hull heuristics are deliberately the strongest *role-free*
  answers one can give without semantics; they are frozen here before
  measurement.

## Frozen Generic-MVFit role mapping g

Rule: role R ↔ family slot s (e6 ROLES) ↔ generic slot g(s) = argmin over
the 8 generic slots of the Euclidean distance between DEFAULT graph centers
(`graphs.json`, θ = default); ties broken by the lower slot index. Derived
once from `graphs.json`, frozen here; the runner re-derives and aborts on
any drift.

| Family slot (role) | compact | articulated | quadruped | branching | lattice | rider |
|---|---|---|---|---|---|---|
| 0 | 0 | 1 | 0 | 0 | 7 | 1 |
| 1 | 0 | 1 | 2 | 7 | 7 | 2 |
| 2 | 3 | 2 | 3 | 7 | 7 | 0 |
| 3 | 4 | 3 | 4 | 7 | 7 | 0 |
| 4 | 5 | 1 | 5 | 7 | 7 | 0 |
| 5 | 6 | 3 | 6 | 7 | 0 | 7 |
| 6 | 1 | 5 | 2 | 7 | 7 | 7 |
| 7 | 2 | 2 | 1 | 7 | 7 | 2 |

Consequences are reported, not hidden: e.g. compact body and cabin both map
to generic slot 0 (Generic answers both queries identically); all branching
crowns and branches map to generic slot 7.

## Frozen metrics

Per query (case × role), for each method:
- precision = |sel ∩ GT| / |sel|, recall = |sel ∩ GT| / |GT|,
  F1 = 2PR/(P+R) (0/0 → 0).
- centroid error = ||centroid(sel) − centroid(GT)||₂ in world meters,
  normalized by the actor size = Euclidean diagonal of the GT occupancy
  bounding box at 64³ (cell units × cell size).
- Edge rule (frozen): empty selection with non-empty GT → P = R = F1 = 0,
  centroid error = 1.0. (GT components of matched pairs are never empty.)

Aggregation: per (family, role) means; family means over queries; overall =
pooled mean over all 920 queries (matches e6's pair pooling). Actor-macro
score = mean over the actor's queries, used for the stratified paired
bootstrap (cells = family, 10 000 resamples, seed 77157): SPPA − Generic,
SPPA − Hull-A, SPPA − Hull-B on F1; and the reversed differences on
centroid error (positive = SPPA better).

## Frozen counting task (bonus)

Multiplicity parts per family: compact wheels (GT 4), articulated wheels
(GT 4), quadruped legs (GT 4), lattice platforms (GT 4), branching crowns
(GT K ∈ {4..7}), rider wheels (GT 2).
Predicted counts (structural, no fitting):
- SPPA: number of graph slots with that role (4, 4, 4, 3, 4, 2).
- Generic: number of DISTINCT generic slots in the images of that role's
  family slots under g (4, 4, 4, 2, 1, 2).
- Hull: number of 26-connected components of the hull (role-free).
Metrics: exact-match accuracy and MAE per family.

## Validation gates (runner aborts on failure)

1. Hull recomputation: per-case hull IoU (64³, clean masks) must match the
   sealed `raw_metrics.csv` nonsemantic_visual_hull clean rows bit-exactly.
2. SPPA slot pipeline: role IoU per matched pair recomputed here must match
   `e6_role_aware/role_aware_iou.json` pair rows bit-exactly.
3. Generic mapping g re-derived from `graphs.json` must equal the table
   above.
4. Query count = 920; actors = 120.

## Outputs

`results.jsonl` (one row per query, 920), `role_query_results.json`,
`role_query_table.tex`, `role_count_table.tex`, `README.md`.
