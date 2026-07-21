# SPPA Submission Precheck

Updated: 2026-07-16 after sealed SPPA-MVFit confirmatory run and manuscript rewrite.

**Update 2026-07-21:** the short supplement was eliminated from the JGSA
submission on 2026-07-20 (recorded in its own header). Submission = main
paper + reproducibility package only; the supplement file remains in the
repo as archived material, not as a submission artifact, and its compiled
PDF is no longer tracked.

## Verdict

| Gate | Status |
|---|---|
| Main PDF builds | **True** (~34 pages) |
| Short submission supplement | **Excluded** — archived 2026-07-20, not submitted |
| Long technical supplement formal-ready | **False** — do not submit (artifact diary) |
| Primary H1 sealed confirmatory result | **PASS** (mean Δ 0.190, CI [0.181, 0.199]) |
| Protocol audit PASS (Amendment 03 triple-role) | **True** |
| `reproduce_sppa_mvfit_paper.py --strict` | **0 blockers** |
| Full experimental paper (real UAV 3D GT / operators) | **False** — out of scope |
| Human journal portal / APC / authors | **Pending human** |

**Recommended submission shape:** main paper + reproducibility package (no supplement).  
**Provisional target:** Journal of Geovisualization and Spatial Analysis.

## Primary evidence

- Package: `reproducibility/sppa_mvfit/`
- Summary: `results/test/confirmatory_summary.json`
- Tables: `benchmarks/results/sppa_mvfit_*.tex`
- Manifest: `RELEASE_MANIFEST.md`
- Status: `SPPA_SUBMISSION_STATUS_20260716.md`

## Claim boundary

Supported: family-conditioned multiview fitting occupancy gain on developer-held-out synthetic geometry under equal-budget comparison to Generic-MVFit.

Not supported: measured flight, real-UAV 3D reconstruction accuracy, operator benefit, universal open-set geometry, image-to-3D SOTA ranking.

## Commands

```powershell
# from Deep-AeroTwin-UE57-Test root
python paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/check_clean_clone_gate.py
python -m pytest paper_semantic_proxy_3d/reproducibility/sppa_mvfit/tests/test_contract.py -q
```
