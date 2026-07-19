# T2 — Graph × fitting 2×2 decomposition (Generic-no-fit cell)

**exploratory post-hoc analysis (not confirmatory)**

## Method

The 2×2 design crosses the graph prior (generic vs SPPA family graph) with
fitting (none vs MVFit local search). Three cells are sealed (`raw_metrics.csv`,
clean condition, n = 240): SPPA-fit 0.557, SPPA-nofit (= sealed
`sppa_text_only`) 0.427, Generic-fit 0.367.

**Missing cell (computed here):** `Generic-nofit` =
`voxelize_actor(build_actor('generic', default_theta()), 64)` evaluated against
the released private GT re-voxelized with the sealed `voxelize_source(..., 64)`.
Choice of θ: `default_theta() = [0,0,0,1,0]` with **no mask-driven
initialization** — this mirrors the sealed `sppa_text_only` method, which also
ignores the observation masks entirely (`infer_method` returns
`build_actor(family, default_theta())`), so the no-fit cells are exactly
comparable across graphs. The generic-prior grid is identical for all 240
actors. Note the no-fit cells are condition-independent by construction.

Effects use the same stratified paired bootstrap as the sealed analysis
(12 family × stratum cells, equal weight per cell, 10 000 resamples, seed
77157). Script: `t2_graph_x_fitting_2x2.py`.

## Results (mean voxel IoU, clean, n = 240)

| Graph prior | No fit (θ₀) | MVFit | Fitting effect |
|---|---|---|---|
| Generic graph | **0.180** (new cell) | 0.367 | +0.187 [0.182, 0.193] |
| SPPA family graph | 0.427 | 0.557 | +0.130 [0.117, 0.143] |
| Graph effect (SPPA − Generic) | +0.248 [0.234, 0.261] | +0.190 [0.181, 0.199] | interaction −0.058 |

By stratum (cell means):

| Stratum | Generic-nofit | Generic-fit | SPPA-nofit | SPPA-fit |
|---|---|---|---|---|
| CSG-ID | 0.165 | 0.342 | 0.404 | 0.551 |
| Implicit-OOD | 0.195 | 0.393 | 0.451 | 0.564 |

Exact identities hold: 0.180 + 0.248 ≈ 0.427 (SPPA-nofit) and
0.180 + 0.187 ≈ 0.367 (Generic-fit); total 0.190 = 0.248 − 0.058.

## Interpretation

- The SPPA family graph contributes the larger share of the headline gap at
  the prior level (+0.248 with no evidence at all).
- Fitting helps the *generic* graph more than the SPPA graph (negative
  interaction −0.058): the generic prior starts far from the actor, so the
  local search recovers more, but it cannot close the prior gap — the fitted
  advantage of SPPA remains +0.190.
- Full precision and per-stratum effect CIs: `graph_x_fitting_2x2.json`.
- LaTeX: `graph_x_fitting_2x2_table.tex`, `graph_x_fitting_effects_table.tex`.
