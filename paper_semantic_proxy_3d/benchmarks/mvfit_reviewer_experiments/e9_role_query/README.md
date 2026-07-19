# E9 — Operational utility of semantic roles: part query + part counting

**Label: exploratory post-hoc analysis (not confirmatory).**
**Design frozen in `ROLE_QUERY_FROZEN.md` before any role-query metric.**

## Question

The reviewer critique: "the visual hull gives 0.522 IoU at 0.22 ms without
roles — what are roles FOR?" E6 showed slot↔role alignment exists
(role IoU 0.319 vs 0.053 shuffle). E9 turns roles into a TASK with a
quantified operational payoff: a **part query** ("where is the cargo / the
wheels / the cabin?") and a **part counting** task ("how many legs /
wheels / platforms?").

## Design (frozen)

- **Query set.** The 920 matched (slot, GT component) pairs of the frozen
  e6 mapping over the 120 csg_id actors (stratum restriction inherited
  ex-ante from e6: implicit_ood has no defensible slot↔component mapping).
  Each pair is one query: "return the voxels of role R in actor A".
- **Answers** (all geometry from SEALED fits, no refitting):
  - SPPA-MVFit: voxels of the fitted slot for role R (sealed sppa θ).
  - Generic-MVFit: voxels of generic slot g(R) from the sealed generic θ,
    with the frozen nearest-default-center mapping g (re-derived at
    runtime; runner aborts on drift).
  - Hull-HEUR-A (`largest_cc`): largest 26-connected component of the 64³
    visual hull.
  - Hull-HEUR-B (`lower_half_z`): hull voxels with z ≤ midpoint of the
    occupied z extent.
  Both heuristics answer EVERY role identically — they are the strongest
  role-free answers available, frozen before measurement.
- **Metrics per query.** precision / recall / F1 of the selected voxels vs
  the GT component voxels, and centroid error ‖c_sel − c_GT‖₂ normalized
  by the GT occupancy bbox diagonal (world meters).
- **Counting (bonus).** Multiplicity part per family; SPPA answers
  structurally from the graph, Generic from the frozen mapping g, the hull
  counts its 26-connected components. Exact-match accuracy + MAE.

## Validation gates (all passed bit-exactly)

1. Hull recomputation vs sealed `raw_metrics.csv` clean rows: max |err| = 0.
2. SPPA slot pipeline vs `e6_role_aware/role_aware_iou.json` pairs:
   max |err| = 0 (coverage and role IoU).
3. Generic mapping g re-derived from `graphs.json` equals the frozen table.
4. 920 queries generated over 120 actors.

## Errata (documented transparently; none changes the frozen design)

1. **Empty-GT exclusion (data-validity correction).** The frozen doc claimed
   "GT components of matched pairs are never empty". This is false at 64³
   for **33/920 pairs (3.6 %)** — thin parts (quadruped tail, rider frame
   tubes, lattice legs, branches, some quadruped legs) voxelize to zero
   cells. Recall and centroid error are undefined for an empty GT, so these
   queries are unscoreable: they are kept in `results.jsonl` (with
   `gt_voxels: 0`) for audit but excluded from every aggregate
   (**887 scored queries**). Sensitivity under the inclusion-as-zero rule:
   F1 sppa 0.418 / gen 0.140 / hullA 0.107 / hullB 0.084 — conclusions
   unchanged.
2. **Code fixes, pre-measurement:** (a) `lower_half_z` slicing crashed under
   NumPy 2.x (float slice index); reimplemented as the frozen rule
   literally states (voxel z ≤ midpoint), verified equivalent. (b) centroid
   error only guarded empty *selections*, not empty GT (NaN propagation);
   resolved by erratum 1. No metric was ever computed before these fixes.
3. **Frozen doc inaccuracy (doc-only):** branching crown GT counts are
   {3,4,5,6}, not {4..7} as written; GT counts are computed from the
   generator components at runtime, so no metric was affected.

## Headline numbers — part query (887 scored queries, 120 actors)

| Method | F1 | Precision | Recall | centroid err $d_c$ |
|---|---|---|---|---|
| **SPPA-MVFit** | **0.434** | 0.388 | 0.565 | **0.055** |
| Generic-MVFit | 0.145 | 0.156 | 0.259 | 0.177 |
| Hull-A (largest cc) | 0.111 | 0.070 | 0.959 | 0.221 |
| Hull-B (lower half z) | 0.087 | 0.057 | 0.617 | 0.249 |

Paired actor-macro bootstrap (10 000 resamples, seed 77157, family cells):

| Contrast | Δ | CI95 | p |
|---|---|---|---|
| SPPA − Generic, F1 | **+0.290** | [+0.268, +0.312] | < 1e-4 |
| SPPA − HullA, F1 | **+0.324** | [+0.304, +0.344] | < 1e-4 |
| SPPA − HullB, F1 | **+0.350** | [+0.330, +0.371] | < 1e-4 |
| Generic − SPPA, $d_c$ | +0.119 | [+0.111, +0.127] | < 1e-4 |
| HullA − SPPA, $d_c$ | +0.165 | [+0.161, +0.170] | < 1e-4 |
| HullB − SPPA, $d_c$ | +0.195 | [+0.189, +0.202] | < 1e-4 |

The diagnostic is sharp: Hull-A **covers** every part (recall 0.959 — its
answer is most of the actor) but cannot **select** it (precision 0.070).
Roles convert coverage into selection: SPPA selects the queried part at
~3–5× the F1 of any role-free or role-agnostic control, and localizes the
part centroid to 5.5 % of the actor size vs 18–25 % for controls.

Per family (F1 SPPA / Gen / HullA / HullB): compact 0.555/0.246/0.139/0.123,
articulated 0.412/0.171/0.140/0.150, quadruped 0.598/0.238/0.123/0.064,
branching 0.253/0.032/0.132/0.044, lattice 0.308/0.037/0.086/0.092,
rider 0.484/0.153/0.049/0.043.

## The frontier (the honest part — per-role losses and ties)

SPPA does **not** win every role. Reported in full in
`role_query_results.json → per_role`:

- **`branching_vertical` crowns 2–4: Hull-A beats SPPA.** crown_2 F1
  0.122 vs 0.183; crown_3 0.045 vs 0.205 (Generic 0.049 also edges SPPA
  here); crown_4 0.178 vs 0.183. The hull's largest connected component IS
  the fused crown mass, so "the biggest blob" is a strong answer to "where
  is crown k" when crowns merge into one component; SPPA's stacked crown
  slots split that mass and individualize poorly at 64³. This is the same
  weakness E8's `cascade_crown` violation exposes from the other side.
- **`rider_cycle/fork`: SPPA scores 0.000** (Hull-A 0.012, Hull-B 0.010).
  The fork is a thin tube; the fitted slot misses it almost everywhere at
  64³. Everyone is near zero; SPPA is exactly zero.
- **`lattice_tower/platform_high`: three-way tie** (SPPA 0.052, Generic
  0.051, Hull-A 0.046); `platform_mid` is also weak for all (0.090 best).
- **`articulated/trailer`: Hull-A nearly ties SPPA** (0.653 vs 0.662) —
  the trailer is the largest component, so the role-free heuristic is
  already right. The role adds nothing for the biggest part; it pays for
  the *other* parts (hitch: 0.268 vs 0.004).

## Counting task (bonus)

Exact-match accuracy (120 actors): **SPPA 70.0 %, Generic 66.7 %, Hull
0.0 %**. MAE: **SPPA 0.333, Generic 0.900, Hull 2.658**.

- Both semantic methods answer wheel/leg counts perfectly where the count
  is structurally constant (compact/articulated wheels 4, quadruped legs 4,
  rider wheels 2 → 100 % each).
- SPPA's structural answer is NOT always right — reported honestly:
  `lattice_tower` platforms: the graph has 3 platform slots but the
  generators build 4 platforms → 0 % exact (MAE 1.0; Generic 2.0).
  `branching_vertical` crowns: the graph fixes 4 crown slots, GT varies
  3–6 → 20 % exact (MAE 1.0; Generic predicts 1 distinct mapped slot →
  MAE 3.4).
- The hull almost never produces the right count (mean component count
  1.0–1.45; the actor fuses into one blob) → 0 % exact everywhere.

## Interpretation

Roles are not decorative: on an operational part-query task, the fitted
family graph turns a 0.522-IoU visual hull into selectable, localizable
parts (F1 0.434 vs ≤0.111 role-free; centroid 5.5 % vs ≥17.7 % of actor
size), and it answers counting queries structurally where the hull cannot
(70 % vs 0 % exact). The value is concentrated where parts are small or
numerous (wheels, legs, hitch, cabin) and vanishes — honestly — where the
part is the dominant connected component (trailer, fused crowns) or below
voxel resolution (fork, platform_high).

## Files

- `ROLE_QUERY_FROZEN.md` — frozen task definition, mapping g, metrics,
  edge rules, gates.
- `run_e9_role_query.py` — runner (read-only on the sealed package;
  exactly reproducible; ~8 s).
- `results.jsonl` — one row per query (920; includes the 33 excluded
  empty-GT rows with `gt_voxels: 0`).
- `role_query_results.json` — full payload (gates, overall, per-family,
  per-role, bootstraps, counting, sensitivity, erratum).
- `role_query_table.tex` — booktabs per-family part-query table.
- `role_count_table.tex` — booktabs counting table.

## Seeds / determinism

All geometry from sealed outputs (no refitting, no new randomness).
Bootstrap: 10 000 resamples, seed 77157 (sealed scheme), family cells over
the 120 csg_id actors.

## Limitations

- csg_id only (inherited from e6): implicit_ood actors have no defensible
  slot↔component mapping, so the query task cannot be scored there.
- The two hull heuristics are strong but not exhaustive; a learning-based
  part segmenter would be a tougher role-free control and is future work.
- Part-query scoring is at 64³: parts thinner than one cell cannot be
  scored (33/920 excluded) — a resolution limit, not a method property.
- SPPA's answer quality is bounded by the sealed fit quality; the task
  measures the *utility of the roles given the fit*, not fit quality itself
  (that is H1/E8).
- Counting GT multiplicity for branching crowns varies per actor ({3..6})
  while the graph arity is fixed; the task rewards structural answers, so a
  fixed-arity graph cannot reach 100 % there by construction.
