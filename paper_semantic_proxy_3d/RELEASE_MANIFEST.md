# SPPA-MVFit release manifest

Release snapshot date: 2026-07-16  
Primary claim: family-conditioned SPPA-MVFit H1 on synthetic held-out occupancy.

**Update 2026-07-21:** the JGSA submission is **main paper + reproducibility
package only**. The short submission supplement was eliminated from the
submission on 2026-07-20 (its own header records the decision; its content
was absorbed into the main text or RP) and is kept in the repo as archived
historical material only — it is not a submission artifact and its compiled
PDF is no longer tracked.

## Submission shape

| Include | Path |
|---|---|
| Main paper TeX/PDF | `semantic_proxy_3d_paper.tex`, `semantic_proxy_3d_paper.pdf` |
| Bibliography | `semantic_proxy_3d_references.bib` |
| Cover letter draft | `COVER_LETTER_DRAFT.md` |
| Status | `SPPA_SUBMISSION_STATUS_20260716.md` |
| **Exclude** | `semantic_proxy_3d_submission_supplement.*` (archived 2026-07-20, not submitted) |
| **Exclude** | `semantic_proxy_3d_technical_supplement.*` (38-page diary) |

## Primary tables → source

| Paper table | Generated from | Command |
|---|---|---|
| `tab:mvfit-h1` | `reproducibility/sppa_mvfit/results/test/confirmatory_summary.json` + resolution sensitivity | `python .../export_paper_tables.py` |
| `tab:mvfit-means` | `results/test/raw_metrics.csv` (clean rows) | same |
| `tab:mvfit-secondary` | `confirmatory_summary.json` secondary bootstrap | same |

LaTeX inputs:

- `benchmarks/results/sppa_mvfit_h1_summary.tex`
- `benchmarks/results/sppa_mvfit_method_means.tex`
- `benchmarks/results/sppa_mvfit_secondary_deltas.tex`

## Sealed confirmatory hashes

| Artifact | SHA-256 |
|---|---|
| pretest_freeze.json | `8E2ADBF32F299B24CD2A5AB87C74D142E707696F79D18DF0C3332209C3B46CA3` |
| PROTOCOL_AUDIT_PASS.json | `2348946BDDB04B8E5CA7D2C845C5F5C45F1AE06F8907E99218ED5E9A379FA74F` |
| sealed_predictions.bin | `F870C57D9CC6FF4868EFB25FD2926FA7D19858EAF8CD0E9781F38990D7D145FD` |
| raw_metrics.csv | `57A82D234F55013D76BEF2E36CF2B3F7C5617DD4FA6EF811C2A8447A04C0AD63` |

## Gate commands (from git repo root)

```powershell
python paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/check_clean_clone_gate.py
python -m pytest paper_semantic_proxy_3d/reproducibility/sppa_mvfit/tests/test_contract.py -q
```

## Main conceptual figure

| Figure | Path | Notes |
|---|---|---|
| Fig. language→parts→3D | `figures/sppa_language_to_parts_to_3d_v17.png` | Locked truck figure decision |

Secondary systems figures remain under `figures/` for qualitative probes only.

## Protocol documents

- `SPPA_PREREGISTRATION_20260715.md`
- `SPPA_PROTOCOL_AMENDMENT_01_20260715.md`
- `SPPA_PROTOCOL_AMENDMENT_02_20260715.md`
- `SPPA_PROTOCOL_AMENDMENT_03_20260716.md`
- `editorial_audits/20260716/ROLE_*.md`
- `editorial_audits/20260715/PROTOCOL_AUDIT_PASS.json`

## Human steps remaining (not automated)

1. Author names / affiliations / CRediT
2. UPNA transformative agreement / APC confirmation for chosen journal
3. Journal portal submission
4. Optional public DOI archive for LFS binaries if required by journal data policy
