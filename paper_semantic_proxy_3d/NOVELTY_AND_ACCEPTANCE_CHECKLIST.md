# Novelty & journal acceptance checklist

## One-sentence novelty (use everywhere)

> Under an input-matched, equal-budget multiview fit, a frozen semantic-family part graph improves 3D occupancy over a nonsemantic eight-part graph; the optimizer is simple so the knowledge representation is what is tested.

## What we claim / do not claim

| Claim | Status |
|---|---|
| Family graph is a measurable occupancy prior (H1) | **Yes — sealed PASS** |
| Shared text-only / silhouette generator | Yes |
| Runtime descriptor/Unreal optional path | Secondary only |
| Photoreal image-to-3D SOTA | **No** |
| Measured flight / operator benefit | **No** |
| Open-set universal word-to-3D | **No** |

## Why a Q1 spatial journal can accept

1. **Clear spatial estimand:** twin-frame object occupancy (voxel IoU).  
2. **Falsifiable design:** H1 fails if family graph does not help (+0.030 margin).  
3. **Robust protocol:** preregistration, NIST seeds, sealed predictions, all 12 strata reported.  
4. **Honest boundaries:** synthetic developer-held-out stated in abstract/conclusion.  
5. **Deployment is demoted:** cannot be misread as the scientific endpoint.  
6. **Reproducibility package:** hashes + short supplement + gates.

## Package files for submission

- [ ] `semantic_proxy_3d_paper.pdf` (main)
- [ ] `semantic_proxy_3d_submission_supplement.pdf` (short only)
- [ ] `HIGHLIGHTS.md` / paste into journal highlights if required
- [ ] `COVER_LETTER_DRAFT.md` → personalize authors
- [ ] `reproducibility/sppa_mvfit/` (or archive DOI)
- [ ] Do **not** attach 38-page technical diary as formal supplement

## Pre-submit commands

```powershell
cd D:\Deep-AeroTwin-UE57-Test
python paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/check_clean_clone_gate.py
python tools/sppa_sota_benchmark/run_sppa_use_case_sota_benchmark.py
```

## Residual acceptance risks (honest)

- External real UAV GT still absent → keep synthetic framing tight.  
- Family tokens are given (not discovered) → already stated.  
- Simulated tribunal ACCEPT ≠ editorial decision.
