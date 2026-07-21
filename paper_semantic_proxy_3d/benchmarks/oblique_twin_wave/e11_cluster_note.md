# E11 cluster-bootstrap re-analysis (JGSA editorial request)

**Generated:** 2026-07-20 by `run_e11_cluster_bootstrap.py` (new file; reads sealed-era
`results.jsonl` / `e11_analysis.json` READ-ONLY; nothing under `reproducibility/` touched).

## Method

- Resampling unit: **tower** (11 clusters), drawn with replacement;
  all detections of a drawn tower enter the replicate (multiplicity preserved).
- 10,000 resamples, seed 20260720 (same seed as the original analysis),
  percentile 95% CIs. Pairing is exact: every case carries all 6 methods.
- Editor objection addressed: the previous CIs treated 149/154 detections from 11 towers
  as independent (12 azimuths per tower are correlated).

## Results (cluster CIs; pseudo-replicate CIs of the original analysis in the JSON)

### oblique30 (n=149 cases, 11 towers)

| method | mean [cluster CI95] | (was pseudo-rep CI) |
|---|---|---|
| sppa_mvfit | 0.118 [0.109, 0.125] | [0.112, 0.123] |
| generic_mvfit | 0.044 [0.042, 0.046] | [0.042, 0.045] |
| obb | 0.031 [0.030, 0.033] | [0.030, 0.032] |
| aabb | 0.023 [0.022, 0.025] | [0.022, 0.025] |
| visual_hull | 0.031 [0.030, 0.033] | [0.030, 0.033] |
| capsule | 0.040 [0.038, 0.042] | [0.039, 0.041] |

| paired Δ sppa−method | mean [cluster CI95] | P(Δ≤0) |
|---|---|---|
| sppa−generic_mvfit | +0.074 [+0.066, +0.081] | 0.0000 |
| sppa−obb | +0.087 [+0.076, +0.095] | 0.0000 |
| sppa−aabb | +0.094 [+0.084, +0.103] | 0.0000 |
| sppa−visual_hull | +0.086 [+0.076, +0.095] | 0.0000 |
| sppa−capsule | +0.078 [+0.068, +0.086] | 0.0000 |

Correct-token subset (n=140): sppa_mvfit 0.125 [0.122, 0.127]; generic_mvfit 0.045 [0.044, 0.047].

Wrong-token rate: 9/149 = 0.060, Wilson [0.032, 0.111], cluster [0.007, 0.129] (correct rate 0.940 = 140/149).

### oblique45 (n=154 cases, 11 towers)

| method | mean [cluster CI95] | (was pseudo-rep CI) |
|---|---|---|
| sppa_mvfit | 0.087 [0.061, 0.120] | [0.076, 0.099] |
| generic_mvfit | 0.024 [0.022, 0.026] | [0.023, 0.025] |
| obb | 0.035 [0.025, 0.044] | [0.032, 0.039] |
| aabb | 0.033 [0.023, 0.040] | [0.029, 0.037] |
| visual_hull | 0.035 [0.025, 0.044] | [0.032, 0.039] |
| capsule | 0.037 [0.028, 0.044] | [0.034, 0.040] |

| paired Δ sppa−method | mean [cluster CI95] | P(Δ≤0) |
|---|---|---|
| sppa−generic_mvfit | +0.063 [+0.039, +0.094] | 0.0000 |
| sppa−obb | +0.052 [+0.017, +0.095] | 0.0000 |
| sppa−aabb | +0.054 [+0.021, +0.097] | 0.0000 |
| sppa−visual_hull | +0.052 [+0.017, +0.095] | 0.0000 |
| sppa−capsule | +0.050 [+0.017, +0.091] | 0.0000 |

Correct-token subset (n=89): sppa_mvfit 0.147 [0.145, 0.150]; generic_mvfit 0.029 [0.028, 0.030].

Wrong-token rate: 65/154 = 0.422, Wilson [0.347, 0.501], cluster [0.194, 0.602] (correct rate 0.578 = 89/154).

## Verification vs `e11_analysis.json`

- Point estimates (means, n, wrong-token counts) reproduce `e11_analysis.json` exactly: **18/18 checks match**.
- 140/149 correct at 30° and 89/154 at 45° **verified from raw data** (wrong: 9/149 = 6.0% at 30°, 65/154 = 42.2% at 45°).

## Caveats

- Only 11 clusters exist; cluster CIs are wider than the original pseudo-replicate CIs
  and are the honest uncertainty statement at the tower level.
- Wilson CIs for token rates assume independent detections; the cluster CIs (braces in
  the table) are the conservative counterpart.
