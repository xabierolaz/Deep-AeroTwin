# E1 — Wrong-family token (off-diagonal family prior)

**Label:** exploratory post-hoc analysis (not confirmatory).

## Question

Reviewer hypothesis: "a bad family prior may actively hurt the fit — is a wrong
family token worse than having no family prior at all (Generic-MVFit)?"

## Method

- For each of the 240 held-out test actors (6 families × 2 strata × 20), clean
  condition (public binary orthographic masks 96×96, top+side), run the frozen
  SPPA-MVFit coordinate-descent fit with **each of the 6 family tokens**
  (240 × 6 = 1 440 deterministic fits, 1 200 off-diagonal).
- Fitting path is exactly the sealed one: `method.sppa_mvfit.infer_method`
  (1 init + 3 step fractions × 5 parameters × 2 directions = 31 candidates).
  No RNG anywhere in the fit; the sealed runner is likewise deterministic.
- Evaluation: voxel IoU at 64³ against `voxelize_source` GT from
  `private_source_actors.jsonl` (post-seal release), same as
  `benchmark/evaluate_test.py`.
- Validation: the recomputed diagonal (correct token) and the Generic-MVFit
  per-case IoUs match `results/test/raw_metrics.csv` with max abs error 0.0 —
  the harness is bit-equivalent to the sealed protocol.
- Uncertainty: stratified paired bootstrap on per-case differences, cells =
  (family, stratum), mean of cell means, 10 000 resamples, seed 77157,
  null-centered two-sided p — identical scheme to `benchmark/analyze_test.py`.

## Headline numbers (pooled voxel IoU)

| Variant | Mean IoU |
|---|---|
| Correct family token (= sealed SPPA-MVFit) | 0.557 |
| **Wrong token (mean over the 5 wrong tokens)** | **0.205** |
| Wrong token (best of the 5 per actor) | 0.361 |
| Generic-MVFit (sealed anchor) | 0.367 |

- Wrong − correct: −0.353 [CI95 −0.362, −0.343], p < 1e-4.
- **Wrong − generic: −0.162 [CI95 −0.167, −0.158], p < 1e-4** → a wrong token
  is *far worse* than no family prior. 98.3 % of actors score below their own
  generic fit when fitted with wrong tokens; even the per-actor *best* wrong
  token (0.361) does not beat generic on average.
- Holds in both strata: csg_id wrong−generic = −0.144 [−0.150, −0.138];
  implicit_ood = −0.181 [−0.187, −0.175].
- The 6×6 matrix is strongly diagonal-dominant: for every true family the
  correct token is the best column (margin ≥ 0.031, typically ≥ 0.10).
- Most damaging confusions: branching_vertical → rider_cycle (0.060),
  compact_vehicle → branching_vertical (0.063). Vertical/graph-structured
  priors destroy boxy vehicles and vice versa.

## Answer to reviewer question (a)

Yes — a wrong family token damages much more than the generic graph:
0.205 vs 0.367 mean IoU (Δ = −0.162, CI95 [−0.167, −0.158], p < 1e-4,
n = 240 actors, 1 200 wrong-token fits). Family-token errors are not a benign
degradation toward the generic baseline; they fall well below it.

## Files

- `run_e1_wrong_family.py` — runner (this analysis is exactly reproducible by
  re-running it; read-only on the sealed package).
- `wrong_family_matrix.json` — full numeric payload (matrix, per-family,
  per-stratum, bootstraps).
- `wrong_family_matrix.tex` — 6×6 booktabs matrix (row = true family,
  column = token given).
- `wrong_family_comparisons.tex` — paired-comparison booktabs table.

## Seeds / determinism

Fitting is deterministic; bootstrap seed 77157 (fixed), 10 000 resamples.
No sealed file was written or modified; no configuration file edited.
