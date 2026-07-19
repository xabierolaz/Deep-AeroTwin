# SPPA-MVFit post-hoc re-analysis — SUMMARY

**All experiments below are exploratory post-hoc analyses (not confirmatory).**
They read only sealed artifacts (`reproducibility/sppa_mvfit/`, never written)
plus the released post-seal private GT, and write only inside
`benchmarks/mvfit_posthoc_analysis/`. Every number is reproducible by the
script in the corresponding subfolder (system Python 3.12, `PYTHONUTF8=1`).
Bootstrap: stratified paired bootstrap replicating the sealed
`benchmark/analyze_test.py` (family × stratum cells, equal weight per cell,
10 000 resamples, fixed seed **77157**). Rounding: 3 decimals in tables; full
precision in JSON. n = 240 actors unless stated otherwise.

## Master results table

| Task | Quantity | Value | 95 % CI | n |
|---|---|---|---|---|
| T1 | Δ clean (sanity) | 0.190 | [0.181, 0.199] | 240 |
| T1 | Δ mild_morphology | 0.163 | [0.152, 0.173] | 240 |
| T1 | Δ moderate_morphology | 0.118 | [0.106, 0.131] | 240 |
| T1 | Δ partial_occlusion | 0.189 | [0.179, 0.200] | 240 |
| T1 | Δ mask_corruption | 0.189 | [0.180, 0.198] | 240 |
| T2 | Generic-nofit (NEW cell, mean IoU) | 0.180 | — | 240 |
| T2 | Graph effect at no-fit | 0.248 | [0.234, 0.261] | 240 |
| T2 | Fitting effect, generic graph | 0.187 | [0.182, 0.193] | 240 |
| T2 | Fitting effect, SPPA graph | 0.130 | [0.117, 0.143] | 240 |
| T2 | Interaction (fitting × graph) | −0.058 | — | 240 |
| T3a | Chamfer SPPA clean (others in JSON) | 0.008 | — | 240 |
| T3a | Chamfer Δ Generic − SPPA (clean) | +0.008 | [0.008, 0.009] | 240 |
| T3a | Chamfer Δ VisualHull − SPPA (clean) | +0.001 | [0.001, 0.001] | 240 |
| T3b | F-score@1.5 vox SPPA / VisualHull / text-only / Generic | 0.831 / 0.799 / 0.706 / 0.560 | — | 240/method |
| T3b | F-score Δ Generic − SPPA | −0.271 | [−0.280, −0.262] | 240 |
| T4a | Failures (IoU < 0.25), SPPA clean | 5/240, all lattice_tower csg_id | — | 240 |
| T4c | Last-sweep improvement rate SPPA / Generic | 88.7 % / 92.1 % | — | 240/method |
| T4c | θ-at-bound rate SPPA / Generic | 0.0 % / 57.9 % | — | 240/method |
| T4c | Init already best SPPA / Generic | 0.4 % / 0.0 % | — | 240/method |
| T5 | Δ all families (sanity) | 0.190 | [0.181, 0.199] | 240 |
| T5 | Δ drop rider_cycle (weakest) | 0.152 | [0.143, 0.162] | 200 |
| T5 | Δ drop compact_vehicle (strongest) | 0.214 | [0.203, 0.224] | 200 |

## Sanity checks vs sealed/expected values — all PASS, no discrepancies

- T1 clean Δ = 0.190046 → matches sealed confirmatory 0.19004632845046177 exactly.
- T1 means SPPA clean 0.5574, Generic clean 0.3674, SPPA text-only 0.427 (T2) → match.
- T2 per-stratum totals CSG-ID 0.209 / Implicit-OOD 0.172 → match sealed
  `confirmatory_summary.json` (0.208513 / 0.171580).
- T4 failures: 5/40 lattice_tower, worst 0.147/0.148 → matches pre-verified expectation.
- T5 drop rider_cycle 0.1523 → matches pre-verified ≈ 0.152.

## Surprises / notable observations (exploratory)

1. **Morphology vs evidence corruption asymmetry (T1):** Δ stays at the clean
   level under partial_occlusion (0.189) and mask_corruption (0.189) but drops
   to 0.118 under moderate_morphology. Missing evidence barely hurts the fit;
   evidence that contradicts the graph prior does.
2. **Baseline surface collapse under moderate morphology (T3a):** volume IoU
   of extent-based baselines degrades gracefully (bbox even rises 0.248 →
   0.264), but their Chamfer explodes ~10× (≈ 0.11–0.12 of the world diagonal)
   while SPPA-MVFit stays at 0.012–0.014. Graph-constrained fitting preserves
   surface alignment where single-primitive extent fitting does not.
3. **Visual hull is the real runner-up (T3):** on surface metrics it nearly
   ties SPPA (Chamfer gap 0.001, F-score gap 0.032), much closer than the
   volume-IoU gap (0.036) suggests — but it carries no semantics.
4. **Generic-MVFit pins θ at the frozen bounds in 57.9 % of cases (T4c)** vs
   0 % for SPPA — the generic prior systematically demands excursions the
   bounds do not allow; part of the headline gap is a constrained-fit effect.
5. **lattice_tower failures are resolution-limited, not prior misses (T4b):**
   legs/plates are 1–2 voxels thick at 64³; all 8 methods score ≤ 0.24 (visual
   hull ≤ 0.43) on the 5 failing actors.

## Task status

| Task | Status | Outputs |
|---|---|---|
| T1 robustness conditions | DONE | `t1_robustness/` (.py, .json, 2 .tex, README) |
| T2 2×2 graph × fitting | DONE | `t2_graph_x_fitting/` (.py, .json, 2 .tex, README) |
| T3 Chamfer + F-score | DONE | `t3_surface/` (.py, .json, 2 .tex, README) |
| T4 failures + convergence | DONE | `t4_failures/` (.py, 2 .json, failure_analysis.md, worst_cases_table.tex, README) |
| T5 drop-one-family | DONE | `t5_drop_one_family/` (.py, .json, .tex, README) |

Nothing left undone. No confirmatory-seal file was modified; no git commit;
no paper `.tex` touched.

## Reproduction

```bat
set PYTHONUTF8=1
set PY=C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe
cd /d D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\benchmarks\mvfit_posthoc_analysis\<subfolder>
%PY% <script>.py
```

Scripts: `t1_robustness_table.py`, `t2_graph_x_fitting_2x2.py`,
`t3_surface_metrics.py`, `t4_failure_convergence.py`, `t5_drop_one_family.py`
(shared helpers in `../common.py`).
