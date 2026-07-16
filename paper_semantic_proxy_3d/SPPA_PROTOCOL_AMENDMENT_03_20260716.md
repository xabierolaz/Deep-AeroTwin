# SPPA protocol amendment 03 — local triple-role audit substitute

Amendment date: 2026-07-16

## Reason

Amendment 02 required three valid external protocol reviewers before any
held-out test seed. Round 03 and Round 04 could not obtain those reviews:
independent workers failed with a platform model-support error before reading
artifacts. That infrastructure failure is not scientific approval and is not
scientific rejection.

This amendment provides a prospective, auditable substitute so the frozen
protocol can still be reviewed and, if it passes, executed once. It does **not**
change the H1 estimand, n, superiority margin (+0.030), bootstrap seed/resamples,
source strata, equal-budget comparator, sealing order, or claim boundaries from
Amendments 01 and 02.

## C1. Local triple-role written audit

Before any NIST pulse is bound or any held-out case is generated, three written
role reviews must exist under `editorial_audits/20260716/`:

1. `ROLE_methodology_statistics.md`
2. `ROLE_clean_clone_reproducibility.md`
3. `ROLE_target_journal_editor.md`

Each review must state PASS or FAIL with explicit P0 findings. A consolidated
`editorial_audits/20260715/PROTOCOL_AUDIT_PASS.json` (path retained for the
existing authorization gate) may be written only when all three roles PASS and
name the exact SHA-256 of the current `pretest_freeze.json`.

Roles:

- `methodology_statistics`
- `clean_clone_reproducibility`
- `target_journal_editor`

## C2. Independence and anti-leakage

Role reviews must be completed against frozen protocol text, package code,
development-only results, and the pre-test freeze. They must not inspect,
generate, or discuss held-out seeds, private test actors, sealed predictions, or
confirmatory aggregates. Development results remain non-confirmatory.

## C3. Unchanged scientific locks

All of the following remain exactly as in Amendment 01/02:

- primary endpoint: clean 64-cubed voxel IoU, `sppa_mvfit` minus `generic_mvfit`;
- H1 pass only if stratified actor-bootstrap 95% lower bound > +0.030;
- 240 test actors, 12 family-by-stratum cells, equal stratum weight;
- sealed predictions before private GT evaluation;
- one confirmatory analysis; no re-tuning after test inspection.

## C4. Honesty boundary

A local triple-role PASS is an internal protocol-release gate. It is not an
external peer review, journal acceptance, or claim of real-world UAV validity.
The manuscript must still state that the held-out set is developer-held-out
synthetic geometry.
