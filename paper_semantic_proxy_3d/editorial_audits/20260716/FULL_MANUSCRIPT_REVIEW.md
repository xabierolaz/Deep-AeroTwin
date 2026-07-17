# Full manuscript review (2026-07-16)

Scope: main paper + short supplement + figures + tables + references + number consistency.

## Overall verdict

**READY FOR SUBMISSION** after the consistency fixes applied in this pass  
(stale triangle counts, conflicting archetype counts, figure-1 role clarified, CI rounding).

Primary science (H1) is coherent, sealed, and correctly bounded. Deployment is secondary. Residual risk is venue fit (synthetic data), not internal contradiction.

---

## Structure (current)

| Section | Role | Assessment |
|---|---|---|
| Abstract | Novelty / Method / Evidence / Boundary | **Strong** for desk screening |
| Introduction | Problem + scientific question | **Good**; question now explicitly primary |
| Contribution + falsifiable novelty | Identification design | **Strong** |
| Fig. flow (truck recipe) | Deployment illustration | **OK** after caption fix (not H1) |
| LM path | Disclaim runtime LLM | **OK** (short) |
| Representation policy table | Deployment | Acceptable secondary |
| Related Work | Positioning | **OK**; still long laundry list of neural methods (P1 polish) |
| SPPA Contract / Implementation | Systems context | Dense but hedged; numbers cleaned |
| MVFit method + protocol | Core science | **Strong** |
| Primary results + family table + H1 figure | Confirmatory | **Strong** |
| Deployment / use-case table | Secondary ops metrics | **OK** with boundary captions |
| Discussion / Threats / Boundaries / Conclusion | Honest limits | **Strong** |

---

## References

| Check | Result |
|---|---|
| Citations missing from `.bib` | **None** |
| Bib entries unused in main tex | 1: `pytorch2026memoryfraction` (harmless) |
| Critical novelty cites present | Laurentini, PartNet, Tulsiani, Trager — **yes** |
| Double-key risk (sf3d) | Two SF3D-related keys exist; both cited in laundry list — OK if intentional |
| Metadata | Prior internal audit (ROUND_04) clean; no re-run of full Crossref today |

**Action taken:** none required for missing keys.

---

## Figures

| Figure | File | Exists | Assessment |
|---|---|---|---|
| Fig. sppa-flow | `figures/sppa_language_to_parts_to_3d_v17.png` | Yes | Deployment illustration; caption rewritten so it cannot steal H1 |
| Fig. mvfit-h1 | `figures/sppa_mvfit_h1_occupancy_examples.png` | Yes | Primary scientific visual; illustrative only (tables decide H1) |

**Not in main body (correct):** real YOLOE grids, neural SOTA contact sheets (secondary/artifact).

**Optional later:** regenerate dual-input real grid with current mesh LOD if submitting a systems appendix—not required for H1 claim.

---

## Tables / numbers

| Quantity | Sealed / generated | Paper text | Status |
|---|---|---|---|
| H1 mean Δ | 0.190046… | 0.190 | OK |
| H1 CI | [0.18086, 0.19913] | [0.181, 0.199] | OK (3 d.p.) |
| Margin / n | +0.030 / 240 | same | OK |
| CSG / OOD | 0.209 / 0.172 | same | OK |
| vs text-only CI low | 0.11649… | **0.116** (was 0.117) | **Fixed** |
| Animal tris | 580–812 balanced | was 836–1180 | **Fixed** to ~580–810 |
| Archetype counts 15 vs 23 | inconsistent | **Softened** (no hard counts) |
| Use-case mean tris | 685 | 685 | OK |
| Use-case build / score | ~0.22 ms / 0.83 | same | OK |
| Labels/refs | — | no undefined `\ref` | OK |

---

## Introduction

**Strengths:** clear problem (telemetry ≠ mesh); neural methods correctly de-scoped; scientific question explicit.

**Fix applied:** wording that H1 is the *only* confirmatory claim; runtime virtues are secondary.

**Residual P1:** still introduces full SPPA story before MVFit; acceptable if Contribution immediately pivots (it does).

---

## Method

**Strengths:** equal-budget identification; shared builder; forbidden inputs; sealing; strata; Amendment 03/04 honesty.

**Residual P1:** production SPPA contract sections remain long relative to MVFit core—already secondary in abstract.

---

## Conclusions

**Strengths:** restates novelty + H1 numbers + boundaries + next steps.

**Aligned** with abstract and claim boundaries.

---

## Claim / novelty risks (post-fix)

| Risk | Status |
|---|---|
| Dual novelty (Unreal vs MVFit) | Controlled |
| Overclaim real flight | Controlled |
| Fig.1 read as main science | Caption fixed |
| Stale system metrics | Fixed animal tris + archetype counts |
| Synthetic-only | Explicit (acceptance risk remains external) |

---

## Recommended submission shape

1. Main PDF (current build ~16 pages)  
2. Short submission supplement only  
3. Highlights + cover letter  
4. Sealed `reproducibility/sppa_mvfit/`  
5. **Exclude** 38-page technical diary  

## Pre-submit commands

```text
python tools/reproduce_sppa_mvfit_paper.py --strict
python reproducibility/sppa_mvfit/benchmark/check_clean_clone_gate.py
python tools/sppa_sota_benchmark/run_sppa_use_case_sota_benchmark.py
```
