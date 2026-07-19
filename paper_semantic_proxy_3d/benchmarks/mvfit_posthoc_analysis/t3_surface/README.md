# T3 — Surface metrics: normalized symmetric Chamfer + F-score@1.5 voxels

**exploratory post-hoc analysis (not confirmatory)**

## Method

**(a) Chamfer.** `normalized_symmetric_chamfer` aggregated from the sealed
`raw_metrics.csv` (it is the sealed metric: symmetric surface EDT mean,
normalized by the world diagonal ≈ 12.06 units; lower is better). Mean per
method × condition (n = 240). Paired Δ = method − SPPA-MVFit on clean with
stratified bootstrap CI (12 family × stratum cells, 10 000 resamples, seed
77157); positive Δ = SPPA lower/better.

**(b) F-score@τ.** Computed from the sealed 64³ prediction grids
(`sealed_predictions.bin`) vs the released private GT re-voxelized with the
sealed `voxelize_source`. Surface masks via the sealed
`benchmark/metrics.py::surface_mask` (6-connectivity erosion); distances via
`scipy.ndimage.distance_transform_edt`. τ = 1.5 voxel grid-index units (note:
world cells are 0.15 × 0.10 × 0.10 units, so τ ≈ 0.15–0.23 world units).
F = harmonic mean of surface precision/recall; F = 1 if both surfaces empty,
0 if exactly one is. Methods: sppa_mvfit, generic_mvfit,
nonsemantic_visual_hull, sppa_text_only; clean; n = 240 per method.
Script: `t3_surface_metrics.py`.

## Results

Chamfer (clean, fraction of world diagonal; all 5 conditions in JSON/tex):

| Method | Clean | Mild | Moderate | Occlusion | Corruption | Δ vs SPPA (clean) |
|---|---|---|---|---|---|---|
| SPPA-MVFit | 0.008 | 0.009 | 0.014 | 0.008 | 0.008 | — |
| Visual hull | 0.009 | … | … | … | … | +0.001 [0.001, 0.001] |
| SPPA text-only | 0.012 | | | | | +0.004 [0.004, 0.005] |
| Generic-MVFit | 0.016 | | | | | +0.008 [0.008, 0.009] |
| Billboard | 0.017 | | | | | +0.009 |
| Ellipsoid | 0.018 | | | | | +0.010 |
| Capsule | 0.020 | | | | | +0.012 |
| Axis-aligned box | 0.026 | | | | | +0.018 |

F-score@1.5 voxels (clean, n = 240):

| Method | F | Δ vs SPPA | 95 % CI |
|---|---|---|---|
| SPPA-MVFit | 0.831 | — | — |
| Visual hull | 0.799 | −0.032 | [−0.040, −0.023] |
| SPPA text-only | 0.706 | −0.125 | [−0.140, −0.110] |
| Generic-MVFit | 0.560 | −0.271 | [−0.280, −0.262] |

## Notes

- SPPA-MVFit is the best method on both surface metrics. The visual hull is
  the closest competitor (Chamfer gap only 0.001 of the world diagonal, F gap
  0.032) — consistent with its high IoU (0.522); the volume-based IoU gap
  (0.036) and surface gap tell the same story.
- Exact per-condition numbers and all CIs: `surface_metrics.json`.
- LaTeX: `chamfer_conditions_table.tex` (8 methods × 5 conditions + clean Δ),
  `surface_metrics_table.tex` (F-score).
