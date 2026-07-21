# E10 token-validation AUC confidence intervals (JGSA editorial request)

**Generated:** 2026-07-20 by `run_e10_auc_ci.py` (new file; reads `results.jsonl` /
`e10_routing.json` READ-ONLY).

## Data availability

Per-case scores **were recoverable** from `results.jsonl` (217 GT-matched arm-A cases;
 prior mismatch recomputed as |ln(obs\_height/H\_family)| with the frozen H\_family
 recorded in `e10_routing.json`). A case-level bootstrap is therefore well defined:

- resampling unit: matched case; 10,000 resamples with replacement; seed 77157;
  percentile 95% CI; AUC = Mann-Whitney with 0.5 tie correction (same estimator as the
  original `run_e10_routing.py`).

## Results

| signal | point AUC | 95% CI (case bootstrap) |
|---|---|---|
| AUC(-confidence) | 0.847 | [0.792, 0.898] |
| AUC(-mismatch) | 1.000 | [1.000, 1.000] |
| AUC(-obs\_height) (secondary) | 1.000 | [1.000, 1.000] |

Notes / caveats:

- The editor's "AUC(-mismatch) = 1.000" equals 1 - `auc_prior_mismatch` stored in
 `e10_routing.json` (stored value 0.0); the sign convention is now explicit.
- AUC(-mismatch) = 1.0 reflects **perfect separation** on the 217 matched cases; the
  bootstrap CI is degenerate/near-degenerate at the boundary and should be read as
  "no observed overlap", not as evidence the population AUC is exactly 1.
- Degenerate resamples (single-class draw): 0/10,000.
- Verification vs `e10_routing.json`: 6/6 checks reproduce exactly (counts 217 = 138 + 79; both stored AUCs).
