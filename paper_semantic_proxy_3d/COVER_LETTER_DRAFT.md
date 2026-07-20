# Cover letter — Journal of Geovisualization and Spatial Analysis (JGSA)

**To the Editors**

Please consider our manuscript for *Journal of Geovisualization and Spatial Analysis*:

**Instant Semantic Proxy Reconstruction for UAV Digital Twins under Degraded Sensing (SPPA-MVFit)**

## Why JGSA

We study **semantic part structure as a spatial occupancy prior** for lightweight
3D proxy actors in UAV digital twins—an identification question in geovisualization
/ spatial analysis, not a photoreal reconstruction leaderboard. The manuscript
anchors this scope explicitly in its Introduction (dynamic-object geovisualization
in 3D spatial twins).

## Novelty (one sentence)

Under an **input-matched, equal-budget** multiview fit, a **frozen semantic-family part graph** improves 3D occupancy over a **nonsemantic eight-part graph**; the optimizer is deliberately simple so the **knowledge representation** is tested.

## Primary result

Mean paired voxel-IoU gain **0.190** (95% CI **[0.181, 0.199]**), *n*=240, margin +0.030 → **H1 PASS**. All 12 family×stratum cells positive; OOD stratum +0.172. Synthetic developer-held-out only. Two exploratory post-hoc twin studies (E11 cross-view fidelity, E14 camera-less simulated LiDAR) support the mission reading and are labeled exploratory/simulated, with positions locked to ground truth.

## Package

- Full main paper (23 pages, 15 figures, 7 tables) + formal supplement (10 pages: post-hoc analyses, real-stream case study, real-image probes, deployment/Unreal evidence, protocol details)  
- Sealed reproducibility under `reproducibility/sppa_mvfit/`  
- Highlights in `HIGHLIGHTS.md`  
- **Not** submitted: 38-page engineering diary  

## Corresponding author / APC eligibility

[Name], Universidad Pública de Navarra (UPNA) institutional email  
Affiliation string per UPNA OA instructions  
APC via Springer CRUE agreement subject to library approval  

Sincerely,  
[Name]
