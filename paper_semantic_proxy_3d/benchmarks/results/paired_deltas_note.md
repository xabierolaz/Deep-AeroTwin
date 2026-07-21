# Paired deltas vs baselines — restored table

**Generated:** 2026-07-20 by `run_confirmatory_editorial_tables.py` (new file).

- All Δ values and CIs are **SEALED** (`confirmatory_summary.json`: paired
  sppa_mvfit − method, clean 64³ voxel IoU, 240 actors, stratified bootstrap
  10,000 resamples, seed 77157; primary endpoint = vs generic\_mvfit; secondaries
  Holm-adjusted, all adjusted p = 0).
- Means/medians recomputed READ-ONLY from the sealed `raw_metrics.csv` (clean).

| method | mean | median | Δ sppa−method [CI] |
|---|---|---|---|
| sppa_mvfit | 0.5574 | 0.5625 | — |
| nonsemantic_visual_hull | 0.5217 | 0.5670 | +0.0357 [0.0273, 0.0441] |
| sppa_text_only | 0.4275 | 0.4414 | +0.1300 [0.1165, 0.1436] |
| generic_mvfit | 0.3674 | 0.3903 | +0.1900 [0.1809, 0.1991] |
| ellipsoid | 0.3417 | 0.2925 | +0.2158 [0.2069, 0.2245] |
| capsule | 0.3247 | 0.2605 | +0.2327 [0.2238, 0.2413] |
| bbox | 0.2479 | 0.1901 | +0.3096 [0.3013, 0.3176] |
| billboard | 0.1733 | 0.1482 | +0.3841 [0.3751, 0.3929] |

## Editor checks

- vs visual_hull +0.036 [0.027, 0.044]: **VERIFIED** (sealed: [0.0357315138089505, 0.02732944146927056, 0.04412991568984099])
- vs capsule +0.233: **VERIFIED** (sealed: 0.23271474138215087)
- vs bbox +0.310: **VERIFIED** (sealed: 0.3095780908573446)
- median inversion hull 0.567 > sppa 0.563: **VERIFIED** (sealed: [0.5670198483714988, 0.5625342090859332])

Median discussion: nonsemantic\_visual\_hull has a HIGHER median (0.5670) than sppa\_mvfit (0.5625) but a LOWER mean (0.5217 vs 0.5574); the sealed paired mean difference is +0.0357 [+0.0273, +0.0441]. The inversion is
real in the sealed data and should be discussed as a skew/heavy-tail property, not
as a contradiction.
