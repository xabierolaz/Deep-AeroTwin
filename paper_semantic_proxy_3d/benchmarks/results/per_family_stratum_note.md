# Family x stratum table — restored (preregistration §6)

**Generated:** 2026-07-20 by `run_confirmatory_editorial_tables.py` (new file).
 Sealed inputs read READ-ONLY from `reproducibility/sppa_mvfit/results/test/`;

nothing under `reproducibility/` was modified.

## Provenance

- **Point estimates and the aggregate row are SEALED** (`confirmatory_summary.json`,
  schema `sppa-mvfit-confirmatory-analysis-v2`; endpoint = clean 64³ voxel IoU,
  paired sppa_mvfit − generic_mvfit, 240 actors, stratified bootstrap 10k seed 77157).
- **Cell CIs are NEW (post-hoc)**: the sealed summary stores only per-cell point
  estimates. CIs here use the sealed bootstrap convention restricted to one cell:
  resample the 20 actors of the cell with replacement, 10,000 resamples,
  seed 77157, percentile 95%. Documented in `per_family_stratum_ci.json`.
- **Drop-one-family range** comes from the EXISTING exploratory post-hoc artifact
  `benchmarks/mvfit_posthoc_analysis/t5_drop_one_family/drop_one_family.json`
  (schema `sppa-mvfit-posthoc-drop-one-family-v1`) — it is NOT part of the sealed
  confirmatory package, and the table says so.

## Editor checks

- rider_cycle|csg_id ~= 0.458: **VERIFIED** (0.4577480700553391)
- compact_vehicle|implicit_ood ~= 0.043: **VERIFIED** (0.042979442731786034)
- aggregate 0.190 [0.181, 0.199]: **VERIFIED** ([0.19004632845046177, 0.1808601091611339, 0.1991332686472451])
- vs visual_hull +0.036 [0.027, 0.044]: **VERIFIED** ([0.0357315138089505, 0.02732944146927056, 0.04412991568984099])
- vs capsule +0.233: **VERIFIED** (0.23271474138215087)
- vs bbox +0.310: **VERIFIED** (0.3095780908573446)
- median inversion hull 0.567 > sppa 0.563: **VERIFIED** ([0.5670198483714988, 0.5625342090859332])
- drop-one-family range 0.152-0.214: **VERIFIED** ([0.15233763712930368, 0.21365009269225804]) — exploratory post-hoc artifact (t5_drop_one_family), not sealed confirmatory

## Cells (ΔIoU sppa−generic, clean)

| family | CSG-ID | implicit-OOD |
|---|---|---|
| articulated_vehicle | +0.1130 [0.100, 0.127] | +0.1251 [0.107, 0.144] |
| branching_vertical | +0.1995 [0.151, 0.247] | +0.2102 [0.175, 0.246] |
| compact_vehicle | +0.1011 [0.064, 0.137] | +0.0430 [0.028, 0.057] |
| lattice_tower | +0.1750 [0.136, 0.215] | +0.1628 [0.140, 0.186] |
| quadruped | +0.2048 [0.174, 0.234] | +0.1890 [0.169, 0.208] |
| rider_cycle | +0.4577 [0.402, 0.508] | +0.2994 [0.282, 0.315] |

Verification: all 12 cell point estimates reproduce the sealed summary exactly (12/12 match).
