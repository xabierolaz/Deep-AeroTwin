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
| `semantic_proxy_3d_paper.tex` / `.pdf` | Rewritten around H1; ~34 pages |
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

## Honesty residual

- Synthetic developer-held-out evidence only.
- Real images remain qualitative without 3D GT.
- External peer literature review still not obtained (Round 04 infrastructure).
- Clean *git* release commit of the full package is still recommended before
  public archive (worktree was dirty at freeze time).
