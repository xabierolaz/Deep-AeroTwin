# E2 — View ablation: top-only / side-only fitting

**Label:** exploratory post-hoc analysis (not confirmatory).

## Question

How much of SPPA-MVFit's 3D quality comes from each observation view? (The
sealed objective is 0.5·(1−IoU_top) + 0.5·(1−IoU_side) + regularizer.)

## Method

- Line-by-line replica of the frozen coordinate descent
  (`method.sppa_mvfit.fit_graph`): same init scheme, same STEP_FRACTIONS
  (0.2/0.1/0.05), same parameter order and tie-break, 31 candidates,
  correct family token, frozen regularizer unchanged.
- **top-only arm:** objective = (1 − IoU_top) + regularizer; init from the top
  mask only. The unobserved z scale uses an *isotropic prior*:
  log_scale_z = mean(log_scale_x, log_scale_y) (geometric mean of the two
  observed extent ratios), documented here before measurement.
- **side-only arm (bonus):** symmetric; unobserved y scale from the isotropic
  prior over (x, z).
- n = 240 actors, clean condition, correct family token, voxel IoU at 64³ vs
  source GT. Dual-view control recomputed through the sealed `infer_method`
  and validated bit-exactly against `results/test/raw_metrics.csv`
  (max abs err 0.0).
- Bootstrap: stratified paired, cells (family, stratum), 10 000 resamples,
  seed 77157.

## Headline numbers (pooled voxel IoU, n = 240)

| Fit variant | Mean IoU | Δ vs dual | CI95 |
|---|---|---|---|
| Dual-view (= sealed SPPA-MVFit) | 0.557 | — | — |
| Top-only | 0.458 | −0.100 | [−0.112, −0.088], p < 1e-4 |
| Side-only | 0.545 | −0.012 | [−0.021, −0.004], p = 0.006 |

Per stratum — csg_id: dual 0.551 / top 0.457 / side 0.541; implicit_ood:
dual 0.564 / top 0.458 / side 0.550.

## Interpretation

Strong view asymmetry: the side view (x–z) carries most of the recoverable 3D
information — losing it costs ~0.10 IoU, while losing the top view costs only
~0.01. The dual-view combination is still significantly better than either
single view (both CIs exclude 0), so the 0.5/0.5 objective is justified
post-hoc: the top view adds a small but real increment over side-only.

## Files

- `run_e2_top_only.py` — runner (exactly reproducible; read-only on the seal).
- `top_only_ablation.json` — full numeric payload incl. per-family means.
- `top_only_ablation_table.tex` — booktabs table.

## Seeds / determinism

Fits deterministic; bootstrap seed 77157, 10 000 resamples.
