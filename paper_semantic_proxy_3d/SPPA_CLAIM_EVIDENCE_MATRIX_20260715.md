# SPPA claim-to-evidence matrix

Updated after sealed confirmatory run: 2026-07-16

| Candidate claim | Required evidence | Current status | Manuscript policy |
|---|---|---|---|
| Text-only and text+silhouette use one generator | Contract test, code path, actor hash under default parameters | **PASS** (pytest contract) | Allowed |
| MVFit improves 3D occupancy over equal-budget generic graph | Preregistered held-out paired voxel-IoU result and bootstrap CI | **PASS** H1: mean 0.190, CI [0.181, 0.199], n=240 | Central claim |
| MVFit improves over text-only / lightweight baselines | Same test cases, secondary bootstrap intervals | **PASS** (secondary CIs; all positive lower bounds in sealed report) | Report as secondary |
| MVFit has bounded local CPU cost | Raw timings, warm policy | **PASS** median 9.4 ms, p95 10.6 ms on clean calls | Local benchmark wording only |
| Geometry generalizes to real UAV imagery | Independent real metric 3D GT and detector-derived observations | Absent | Prohibited |
| SPPA is universally correct text/image-to-3D | Broad independent open-set evaluation | Absent and outside scope | Prohibited |
| YOLOE supplies approximate open-vocabulary evidence | Checkpoint/hash, official paper, local detector output | Partial; qualitative probes only | Approximate only; not central |
| Replay uses measured flight telemetry | Flight log, sensor/calibration provenance | Absent; declared assumptions | Prohibited; use `declared replay` |
| Operators benefit or safety improves | Approved human study | Absent | Prohibited |
| A visual grid ranks SOTA | Shared GT, metrics, contracts | Absent | Prohibited; visual failure audit only |
| Package reproduces primary tables from sealed artifacts | Hashes + export tables + contract tests | **PASS** local `reproduce_sppa_mvfit_paper.py` after git-root fix | Required for submission package |
| Bibliography identities are correct | Primary-source verification | Internally cleaned (Round 04); external lit worker failed | Machine-checked; not external peer review |
| Journal target and APC route are current | Submission-day publisher/UPNA verification | Provisional JGSA / AEI shortlist only | No guarantee |

## Sealed confirmatory artifacts

- `reproducibility/sppa_mvfit/results/test/confirmatory_summary.json`
- H1 pass: true
- Strata: CSG-ID 0.209, implicit-OOD 0.172 (both positive)
- Protocol: Amendments 01–03; NIST-bound seeds; predictions sealed before private GT
