# E14 cluster-bootstrap re-analysis (JGSA editorial request)

**Generated:** 2026-07-20 by `run_e14_cluster_bootstrap.py` (new file; reads sealed-era
`results.jsonl` / `e14_analysis.json` READ-ONLY).

## Declared resampling unit

The **tower** is the independent unit (one fit per method per tower per arm).
 10,000 resamples with replacement over towers, seed 77157,
 percentile 95% CIs. Because each cluster contributes exactly one observation per
 method, the cluster bootstrap reduces to an ordinary bootstrap over towers; the
 declaration still fixes the independent unit unambiguously.

## n per arm (verified from `results.jsonl`)

- **clean**: 11 fitted towers of 11 attempted; no detection failures.
- **degraded**: 7 fitted towers of 11 attempted; detection failures: t1, t10, t2, tower13 (all methods).

## Results

| method | clean mean [cluster CI95] | degraded mean [cluster CI95] |
|---|---|---|
| sppa_mvfit | 0.0810 [0.0760, 0.0855] | 0.0821 [0.0758, 0.0880] |
| generic_mvfit | 0.0844 [0.0819, 0.0869] | 0.0963 [0.0942, 0.0985] |
| obb | 0.0660 [0.0642, 0.0679] | 0.0871 [0.0745, 0.1080] |
| aabb | 0.0575 [0.0534, 0.0615] | 0.0594 [0.0516, 0.0678] |
| visual_hull | 0.0655 [0.0634, 0.0676] | 0.0879 [0.0759, 0.1084] |
| capsule | 0.0833 [0.0820, 0.0847] | 0.1052 [0.0924, 0.1281] |

Verification vs `e14_analysis.json`: **14/14 checks match** (means, n per arm, detection-failure counts reproduce exactly).

Supplementary paired tower-level deltas (SPPA$-$baseline per arm) are in the JSON
(`paired_delta_sppa_minus_supplementary`).
