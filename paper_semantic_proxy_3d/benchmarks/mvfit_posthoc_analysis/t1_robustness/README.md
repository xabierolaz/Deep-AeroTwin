# T1 — Robustness across observation conditions

**exploratory post-hoc analysis (not confirmatory)**

## Method

- Source: sealed `reproducibility/sppa_mvfit/results/test/raw_metrics.csv`
  (9 600 rows = 240 actors × 5 conditions × 8 methods). Read-only.
- Mean `voxel_iou` per method × condition: plain actor-level mean, n = 240
  per cell.
- Paired Δ (SPPA-MVFit − Generic-MVFit) per condition: stratified bootstrap
  replicating the sealed `benchmark/analyze_test.py` — paired per-actor
  differences grouped into 12 family × stratum cells, point estimate =
  equal-weight mean of cell means, 10 000 resamples within cells, percentile
  95 % CI, fixed seed **77157** (the sealed protocol seed).
- Script: `t1_robustness_table.py` (run with system Python 3.12, `PYTHONUTF8=1`).

## Results (n = 240 actors per condition; IoU means and paired Δ with 95 % CI)

| Condition | SPPA-MVFit | Generic-MVFit | Δ paired | 95 % CI |
|---|---|---|---|---|
| Clean | 0.557 | 0.367 | 0.190 | [0.181, 0.199] |
| Mild morphology | 0.511 | 0.349 | 0.163 | [0.152, 0.173] |
| Moderate morphology | 0.418 | 0.299 | 0.118 | [0.106, 0.131] |
| Partial occlusion | 0.545 | 0.355 | 0.189 | [0.179, 0.200] |
| Mask corruption | 0.555 | 0.367 | 0.189 | [0.180, 0.198] |

Full-precision numbers: `robustness_conditions_table.json`.
LaTeX fragments: `robustness_conditions_table.tex` (focus table),
`robustness_conditions_all_methods_table.tex` (all 8 methods × 5 conditions,
means only).

## Sanity check

Clean Δ = 0.190046 vs sealed confirmatory 0.19004632845046177 — exact match
(same data, same estimator). SPPA clean mean 0.5574 and Generic clean mean
0.3674 match the known values.

## Notes

- Morphology perturbations (mild/moderate) degrade both methods and shrink Δ
  to 0.118 under moderate morphology; partial occlusion and mask corruption
  leave Δ essentially at the clean level (≈ 0.189). The SPPA advantage is
  therefore robust to missing/corrupted evidence but both methods lose
  accuracy when the observed morphology departs from the graph prior.
- All 8-method means per condition are in the JSON and the extended table.
