# T4 — Failure analysis + local-search convergence

**exploratory post-hoc analysis (not confirmatory)**

Script: `t4_failure_convergence.py`. Main narrative document:
`failure_analysis.md`. Structured data: `failure_analysis.json`,
`convergence_stats.json`. LaTeX: `worst_cases_table.tex`.

## Headline numbers

**(a) Failures (voxel IoU < 0.25, sppa_mvfit, clean, n = 240):** 5/240
(2.1 %), all in `lattice_tower | csg_id` (5/40 within family, rate 0.125;
0 everywhere else). Case ids: test-csg_id-lattice_tower-017 (0.147), -007
(0.148), -011 (0.173), -018 (0.182), -008 (0.239) — matches the pre-verified
expectation (5/40, worst 0.147/0.148).

**(b) Sub-voxel hypothesis:** confirmed in refined form. The failing
lattice_tower actors have legs/ring plates 0.09–0.23 world-units thick vs
voxel cells 0.15 × 0.10 × 0.10; 512³-reference capture ratios ≈ 0.9–1.2 show
components do not vanish at 64³ but are only 1–2 voxels thick (GT ≈ 520–1088
voxels of 262 144). IoU on 1-voxel-thin structures is inherently unstable at
64³. Every method is poor on these cases (visual hull 0.18–0.43, all others
≤ 0.24), i.e. a resolution effect, not a graph-prior miss.

**(c) Convergence (clean, n = 240 per method, 31-evaluation trace):**

| Statistic | SPPA-MVFit | Generic-MVFit |
|---|---|---|
| Improvement in last sweep (fraction 0.05) | 88.7 % (213/240) | 92.1 % (221/240) |
| Final θ on a parameter bound | 0.0 % (0/240) | 57.9 % (139/240) |
| Init θ already the best | 0.4 % (1/240) | 0.0 % (0/240) |
| Mean objective init → final | 0.304 → 0.236 | 0.417 → 0.348 |

Improvement-per-evaluation curves (mean and p90 over cases, evaluations
1→30) are in `convergence_stats.json`. SPPA never saturates the θ bounds;
Generic pins θ at the bound in 57.9 % of cases — the frozen bounds constrain
the generic prior far more than the family prior.
