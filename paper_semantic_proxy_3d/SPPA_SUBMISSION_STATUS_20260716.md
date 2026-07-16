# SPPA submission status — 2026-07-16

## Verdict

**Local scientific package is submission-ready for a narrow synthetic
family-conditioned MVFit claim**, with main paper + short supplement.

Not done by this package (human/institutional): author list, UPNA APC email
confirmation, journal portal upload, anonymous PDF finalization, DOI archive of
large binaries.

## Primary result (sealed, one-shot)

| Item | Value |
|---|---|
| H1 | **PASS** |
| Mean Δ IoU (SPPA-MVFit − Generic-MVFit) | 0.190 |
| 95% CI | [0.181, 0.199] |
| Margin | +0.030 |
| n actors | 240 |
| CSG-ID / OOD stratum Δ | 0.209 / 0.172 |
| Median / p95 SPPA-MVFit ms | 9.4 / 10.6 |
| Resolution sensitivity | PASS |

## Deliverables

| Artifact | Status |
|---|---|
| `semantic_proxy_3d_paper.tex` / `.pdf` | Tribunal-focused rewrite around H1; **15 pages** |
| `semantic_proxy_3d_submission_supplement.tex` / `.pdf` | 2 pages; formal companion |
| Long technical supplement (38p) | **Do not submit** |
| `reproducibility/sppa_mvfit/` | Method, source, sealed test, hashes |
| Amendment 03 + triple-role PASS | Present |
| `tools/reproduce_sppa_mvfit_paper.py --strict` | 0 blockers |
| `COVER_LETTER_DRAFT.md` | Draft for JGSA |
| Tables | `benchmarks/results/sppa_mvfit_*.tex` |

## Recommended target

Provisional: **Journal of Geovisualization and Spatial Analysis** (spatial proxy
+ synthetic occupancy evidence). AEI only if authors strengthen KR framing and
accept synthetic-only engineering knowledge claim.

## Release commits (local, not pushed)

| Commit | Message |
|---|---|
| `a0f5887` | Seal SPPA-MVFit confirmatory package and submission-ready paper |
| `37f0c19` | Add remaining secondary paper table inputs for clean PDF build |

Gates after release commits:

- `check_clean_clone_gate.py` → **pass: true**
- `reproduce_sppa_mvfit_paper.py --strict` → **0 blockers**

## Simulated journal tribunal (2026-07-16)

| Round | Overall |
|---|---|
| ROUND_01 | MAJOR (Editor) + MINOR (Stats/Repro/Lit) |
| ROUND_02 (after fixes) | **CLEAR ACCEPT** (all four roles ACCEPT) |

Artifacts: `editorial_audits/20260716/TRIBUNAL_ROUND_01.md`, `TRIBUNAL_ROUND_02.md`.

## Honesty residual / human-only remainder

- Synthetic developer-held-out evidence only (by design).
- Real images remain qualitative without 3D GT.
- Simulated tribunal ≠ publisher decision.
- **Not automated:** authors/CRediT, UPNA APC confirmation, journal portal upload, remote `git push` / public DOI.
- Optional historical docs (`SPPA_WORK_MEMORY.md`, long technical supplement, full `supporting_artifacts/`) remain untracked on purpose.
