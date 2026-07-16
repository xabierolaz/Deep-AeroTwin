# Cover letter draft (provisional target: JGSA)

**To the Editors of the Journal of Geovisualization and Spatial Analysis**

Please consider our manuscript:

**Family-Conditioned Multiview Occupancy Fitting for Semantic Proxy Actors in a Synthetic UAV Digital-Twin Setting (SPPA-MVFit)**

## Why this journal

Object-level UAV telemetry must become spatial objects in a digital twin. The paper treats **semantic part structure as a spatial occupancy prior** for lightweight proxy actors—an identification question suitable for geovisualization / spatial analysis, not a photoreal reconstruction leaderboard.

## Clear novelty (one sentence)

Under an **input-matched, equal-budget** multiview fit, a **frozen semantic-family part graph** improves 3D occupancy over a **nonsemantic eight-part graph**; the optimizer is deliberately simple so the **knowledge representation** is what is tested.

## Why acceptance risk is controlled

| Risk | How we address it |
|---|---|
| Dual claims (systems diary vs science) | Single primary endpoint H1; Unreal/runtime is secondary deployment context only |
| Overclaim | Synthetic developer-held-out only; no flight GT / operator / image-to-3D SOTA claims |
| Weak protocol | Preregistration + amendments; NIST seeds; predictions sealed before GT; bootstrap CI rule |
| Missing heterogeneity | All 12 family×stratum Δ reported; OOD stratum positive |
| Reproducibility | Sealed package + short supplement + hash gates |

## Primary result

Mean paired voxel-IoU gain **0.190** (95% CI **[0.181, 0.199]**), n=240, margin **+0.030** → **H1 PASS**.

## Submission package

- Main PDF (~16 pages) + **short** formal supplement (not the 38-page engineering diary)
- `reproducibility/sppa_mvfit/` sealed confirmatory package
- Highlights in `HIGHLIGHTS.md`

## Conflicts / authors

[Corresponding author, UPNA email and affiliation — to complete]  
[Conflicts — to complete]

Sincerely,  
[Name]
