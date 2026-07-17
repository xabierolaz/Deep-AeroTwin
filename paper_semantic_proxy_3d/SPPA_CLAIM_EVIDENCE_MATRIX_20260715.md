# SPPA claim-to-evidence matrix

Updated after sealed confirmatory run: 2026-07-16; updated after Amendment 05 measured wave: 2026-07-17

| Candidate claim | Required evidence | Current status | Manuscript policy |
|---|---|---|---|
| Text-only and text+silhouette use one generator | Contract test, code path, actor hash under default parameters | **PASS** (pytest contract) | Allowed |
| MVFit improves 3D occupancy over equal-budget generic graph | Preregistered held-out paired voxel-IoU result and bootstrap CI | **PASS** H1: mean 0.190, CI [0.181, 0.199], n=240 | Central claim |
| MVFit improves over text-only / lightweight baselines | Same test cases, secondary bootstrap intervals | **PASS** (secondary CIs; all positive lower bounds in sealed report) | Report as secondary |
| MVFit has bounded local CPU cost | Raw timings, warm policy | **PASS** median 9.4 ms, p95 10.6 ms on clean calls | Local benchmark wording only |
| External neural generators measured on the same sealed cases | Amendment 05 protocol: 60-case manifest, two prespecified input conditions, frozen alignment, IoU/triangles/ms/VRAM/payload | **PASS** (measured 2026-07-17; SPPA-MVFit 0.561 vs TripoSR 0.128/0.231, Hunyuan3D-2mini 0.157/0.171; `benchmarks/results/sppa_neural_external_wave.{json,md,tex}`) | Report as secondary operating point; not a leaderboard |
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
- Protocol: Amendments 01–05; NIST-bound seeds; predictions sealed before private GT

## Secondary measured artifacts (Amendment 05)

- `benchmarks/neural_external_wave/subset_manifest.json` (60-case manifest + input hashes)
- `benchmarks/neural_external_wave/wave_calibration.json` (frozen alignment convention)
- `benchmarks/results/sppa_neural_external_wave.{json,md,tex}` (per-case rows + aggregates)
- Environment-level exclusions: SF3D (install failure), SPAR3D (gated weights), TRELLIS.2 (no Windows env); 2/240 hard crashes reported (Hunyuan3D oblique)
