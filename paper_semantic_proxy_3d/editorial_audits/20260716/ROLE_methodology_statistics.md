# Role audit: methodology_statistics

Date: 2026-07-16  
Scope: read-only pre-test protocol and package review under Amendment 03.  
No held-out seeds, private actors, sealed predictions, or confirmatory aggregates were inspected.

## Verdict

**PASS**

## Checks performed

1. **Primary endpoint.** `protocol_config.json` and Amendment 01 fix H1 as clean
   64-cubed voxel IoU of `sppa_mvfit` minus `generic_mvfit`, with superiority
   margin +0.030 and stratified actor-level bootstrap (seed 77157, 10,000
   resamples). `analyze_test.py` implements the lower-bound rule
   `ci95_low > 0.030`.
2. **Equal-budget comparator.** Both methods share five parameters, bounds,
   31-candidate budget, objective, and shared actor builder; only the graph
   name differs (`family` vs `generic`). All family graphs and `generic` have
   exactly eight slots.
3. **Independence of source and method.** Static text check: no
   `method`/`source` cross-imports. Source strata include `csg_id` and
   `implicit_ood`.
4. **Anti-leakage.** No `test_seed_manifest.json`, no `data/test`, no
   `results/test` present at audit time. Development results are explicitly
   non-confirmatory.
5. **Sealing order.** `run_test_methods.py` writes packed predictions and
   hashes before `evaluate_test.py` opens private GT. Authorization requires
   PASS audit + freeze + 240 seeds.
6. **Terminology.** Contribution is family-conditioned, not class-agnostic
   open-set universal fitting.

## Residual non-P0 notes

- Development Δ IoU is large and optimistic; it must not be treated as H1.
- Synthetic developer-held-out data cannot support real-UAV generalization claims.
- Visual hull remains a high-complexity geometry reference, not a lightweight actor.

## P0 findings

None that block a one-shot confirmatory run under the frozen rules.
