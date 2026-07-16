# SPPA protocol amendment 04 — post-seal analysis hygiene

Amendment date: 2026-07-16

Prospective documentation of executed analysis details and secondary-inference
hygiene after tribunal review. **Does not re-seal predictions or change H1
estimand, n, margin, or seeds.**

## D1. Fit projection resolution

Amendment 01 A6 text mentioned a 48-cubed candidate render grid. The frozen
executed package and `protocol_config.json` use **fit/observation resolution
96** for both `sppa_mvfit` and `generic_mvfit`. Both arms are identical, so H1
is not differentially biased. This amendment declares the executed resolution
as 96.

## D2. Secondary p-values and Holm

The original `draws_two_sided_p` field (`mean(|draw| >= |observed|)`) is not a
valid test of mean difference zero. Confirmatory analysis v2 replaces it with
**null-centered stratified bootstrap two-sided p-values** and recomputes Holm
adjustment for the six secondary comparators. H1 decision remains the
prespecified CI lower-bound vs +0.030 rule and does not depend on p-values.

## D3. Timing claim scope

Single-call wall times recorded during sealed evaluation are descriptive local
CPU costs. They are **not** the protocol H4 warm multi-call timing design and
are not Unreal frame times.

## D4. Protocol release independence

Amendment 03 local triple-role PASS remains an internal protocol-release gate
after external worker infrastructure failure. It is not external peer review.
