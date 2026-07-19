# T5 — Drop-one-family robustness of the headline Δ

**exploratory post-hoc analysis (not confirmatory)**

## Method

Recompute the headline paired Δ (SPPA-MVFit − Generic-MVFit, clean voxel IoU)
excluding each of the 6 families in turn. Aggregation follows the sealed
protocol: equal-weight mean over the remaining family × stratum cells (10
cells after a drop, 20 actors each; 12 cells for "all"). Stratified bootstrap
95 % CI, 10 000 resamples within cells, seed 77157. Source: sealed
`raw_metrics.csv` (n = 200 after each drop; 240 for "all").
Script: `t5_drop_one_family.py`.

## Results

| Excluded family | Δ IoU | 95 % CI | n |
|---|---|---|---|
| None (all families) | 0.190 | [0.181, 0.199] | 240 |
| compact_vehicle | 0.214 | [0.203, 0.224] | 200 |
| articulated_vehicle | 0.204 | [0.194, 0.215] | 200 |
| quadruped | 0.189 | [0.178, 0.199] | 200 |
| branching_vertical | 0.187 | [0.178, 0.196] | 200 |
| lattice_tower | 0.194 | [0.184, 0.204] | 200 |
| rider_cycle | **0.152** | [0.143, 0.162] | 200 |

## Notes

- Sanity checks pass: all-families = 0.190 (sealed headline) and
  drop-rider_cycle = 0.152 (pre-verified expectation).
- The headline Δ stays in [0.152, 0.214] under every single-family exclusion
  — always ≥ 5× the prespecified 0.03 superiority margin. rider_cycle is the
  largest single contributor (its removal drops Δ by 0.038, consistent with
  its family-level Δ ≈ 0.379 in the sealed family table); no family drives
  the result on its own.
- Full precision: `drop_one_family.json`. LaTeX: `drop_one_family_table.tex`.
