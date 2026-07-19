# E4 — Optimizer budget sweep

**Label:** exploratory post-hoc analysis (not confirmatory).

## Question

The sealed fit evaluates 31 candidates (1 init + 3 step fractions × 5
parameters × 2 directions). Is 31 a justified operating point, or would a
larger budget materially raise IoU (and what does a smaller one cost)?

## Method (documented monkeypatch)

- `method.sppa_mvfit.STEP_FRACTIONS` is read at call time by `fit_graph`; we
  set it in memory (never on disk) together with
  `PROTOCOL["fit_candidate_budget"]`, and restore both in a `finally` block.
- Budgets and step fractions: 11 → (0.2); 21 → (0.2, 0.1); 31 → (0.2, 0.1,
  0.05) [sealed]; 61 → (0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625) — the same
  coordinate-descent scheme extended with the natural geometric (halving)
  tail.
- The budget-31 arm is validated bit-exactly against
  `results/test/raw_metrics.csv` (max abs err 0.0) before trusting the sweep.
- n = 240 actors, clean, correct family token, voxel IoU at 64³; wall-clock
  ms via `time.perf_counter` per fit (includes voxelization of the actor).

## Headline numbers (n = 240)

| Budget | Mean IoU | Mean ms | p95 ms |
|---|---|---|---|
| 11 | 0.528 | 3.57 | 4.99 |
| 21 | 0.547 | 7.59 | 9.36 |
| 31 (sealed) | 0.557 | 12.57 | 14.18 |
| 61 | 0.560 | 24.03 | 27.69 |

Paired bootstrap vs budget 31 (seed 77157, 10 000 resamples):
- 11 − 31 = −0.029 [−0.036, −0.023], p < 1e-4 (significant loss).
- 21 − 31 = −0.011 [−0.015, −0.006], p < 1e-4 (significant loss).
- 61 − 31 = +0.003 [−0.001, +0.006], p = 0.108 (**not** significant).

## Interpretation

The IoU-vs-budget curve has its knee exactly at the sealed budget: halving
the budget loses significant IoU, doubling it gains a non-significant +0.003
at 2× latency. The 31-candidate budget is a defensible accuracy/latency
operating point, not an under-budgeted corner.

## Files

- `run_e4_budget.py` — runner (exactly reproducible).
- `budget_sweep.json` — full payload incl. per-stratum means.
- `budget_sweep_table.tex` — booktabs table.

## Seeds / determinism

Fits deterministic; bootstrap seed 77157, 10 000 resamples.
