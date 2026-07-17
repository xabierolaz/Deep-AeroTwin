# SPPA Packaged Render Benchmark - 2026-07-02

This note records the first clean packaged Unreal render benchmark for the SPPA backend.

## Scope

Measured:

- Packaged `AirTraffic.exe` running a cooked benchmark map: `/Game/SPPABenchmark`.
- Internal synthetic obstacle replay through `UPorceTelemetryComponent::ApplyObstacleBatchJson`.
- Three interchangeable backends using the same obstacle payload shape: `no_render`, `unreal_assets`, and `semantic_proxy`.
- Rendered-frame tick delta, p50/p95/p99 frame time, actor count, static mesh component count, estimated triangles, and estimated draw calls.
- Create, pose-update, and shape-update payload application time.

Not measured:

- Live HTTP/network telemetry.
- Live YOLO detector output.
- VR headset runtime.
- Phase-aligned GPU profiler counters from Unreal CSV profiler.
- Real curated project assets for the asset backend; this packaged benchmark uses a simple placeholder asset actor.
- Operator readability, NASA-TLX, SAGAT, or false-confidence behavior.

## Implementation Notes

The benchmark is opt-in only. The normal Unreal pipeline is unchanged unless the executable is launched with:

```powershell
-PorceSPPAPackagedBenchmark
```

The runner is spawned by `PorceTelemetry` only when the benchmark flag is present. It uses a dedicated empty map, `/Game/SPPABenchmark`, to avoid unrelated runtime systems such as `BP_OpenSkyManager` polling `api/state/latest`.

The wrapper script is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1
```

## Primary Clean Run

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -SkipPackage `
  -PackageDir "experiments\sppa_packaged_render\20260702T122702Z_packaged_render\package" `
  -Counts "10,50,100" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -TimeoutSeconds 1200 `
  -NoCsvProfile
```

Artifacts:

- Package smoke: `experiments/sppa_packaged_render/20260702T122702Z_packaged_render`
- Primary clean run: `experiments/sppa_packaged_render/20260702T122743Z_packaged_render`
- Manifest: `run_manifest.json`
- Frame rows: `packaged_frame_stats.csv`
- Action rows: `packaged_action_rows.csv`
- Summary: `packaged_render_summary.json`
- Compact frame table: `packaged_frame_summary.csv`

Manifest facts:

- Engine: Unreal Engine `5.7.4-51494982+++UE5+Release-5.7`
- Map: `/Game/SPPABenchmark`
- Counts: `10, 50, 100`
- Repetitions: `3`
- Warmup frames per phase: `30`
- Measured frames per phase: `120`
- Backends: `no_render`, `unreal_assets`, `semantic_proxy`
- Failure CSV: header only, no benchmark failures
- Log: benchmark start/runner/OK markers present; no `api/state/latest`, `Ensure`, or fatal runtime errors in the benchmark section

## Frame-Time Summary

Aggregated measured-frame p50/p95 in milliseconds:

| Backend | Count | Create p50/p95 | Pose p50/p95 | Shape p50/p95 | Components | Est. triangles | Est. draw calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_render | 10 | 3.184 / 4.176 | 3.319 / 4.312 | 3.529 / 4.600 | 0 | 0 | 0 |
| no_render | 50 | 3.353 / 4.290 | 3.432 / 4.319 | 3.285 / 3.986 | 0 | 0 | 0 |
| no_render | 100 | 3.363 / 4.072 | 3.274 / 4.140 | 3.331 / 4.176 | 0 | 0 | 0 |
| unreal_assets | 10 | 3.453 / 4.154 | 3.494 / 4.323 | 3.472 / 4.295 | 10 | 480 | 10 |
| unreal_assets | 50 | 4.242 / 5.268 | 3.957 / 5.043 | 3.705 / 5.162 | 50 | 2400 | 50 |
| unreal_assets | 100 | 3.564 / 4.414 | 3.546 / 5.227 | 3.501 / 4.810 | 100 | 4800 | 100 |
| semantic_proxy | 10 | 3.781 / 4.674 | 3.673 / 4.378 | 3.794 / 4.747 | 44 | 23760 | 44 |
| semantic_proxy | 50 | 4.045 / 5.133 | 4.101 / 9.270 | 4.131 / 9.882 | 216 | 104432 | 216 |
| semantic_proxy | 100 | 4.066 / 4.817 | 4.142 / 17.814 | 4.246 / 19.256 | 432 | 208864 | 432 |

All measured configurations stayed below 33.3 ms p95 in this run. The 100-object semantic-proxy update streams exceeded a 60 FPS p95 budget: pose p95 was 17.814 ms and shape p95 was 19.256 ms.

## Payload Application Summary

Payload application p50/p95 in milliseconds:

| Backend | Count | Create p50/p95 | Pose update p50/p95 | Shape update p50/p95 |
|---|---:|---:|---:|---:|
| no_render | 10 | 0.118 / 0.119 | 0.110 / 0.128 | 0.116 / 0.129 |
| no_render | 50 | 0.357 / 0.468 | 0.476 / 0.646 | 0.437 / 0.486 |
| no_render | 100 | 0.974 / 1.168 | 0.912 / 1.182 | 0.886 / 1.139 |
| unreal_assets | 10 | 0.931 / 0.964 | 0.314 / 0.381 | 0.262 / 0.361 |
| unreal_assets | 50 | 3.671 / 3.803 | 1.178 / 1.372 | 0.922 / 1.182 |
| unreal_assets | 100 | 5.952 / 8.276 | 2.224 / 3.579 | 1.788 / 2.004 |
| semantic_proxy | 10 | 5.719 / 6.004 | 0.945 / 1.027 | 0.992 / 1.215 |
| semantic_proxy | 50 | 22.474 / 23.492 | 4.253 / 4.688 | 4.663 / 5.243 |
| semantic_proxy | 100 | 46.067 / 53.175 | 8.507 / 9.178 | 9.289 / 10.446 |

## Interpretation

Allowed claim:

- In a packaged Unreal 5.7 executable on the tested desktop, SPPA semantic proxies rendered 100 synthetic obstacles with 432 static mesh components and about 208,864 estimated triangles while staying below 33.3 ms p95 frame time for create, pose-stream, and shape-stream phases. The 100-object SPPA update phases did not stay below 16.7 ms p95.

Forbidden claims:

- Do not present this as VR validation, live flight validation, real network validation, curated-asset comparison, phase-aligned GPU-profiler evidence, or pilot readability evidence.
- Do not claim SPPA is faster than the placeholder asset backend. In this run, the semantic-proxy backend is visually richer but has more components, more triangles, and higher payload application cost.

## CSV Profiler Note

The initial small packaged `csvprofile` smoke produced a zero-byte profiler CSV,
so it was not used as evidence. A later packaged run left two non-empty Unreal
CSV profiler files under the shared package directory:

- `Profile(20260703_051155).csv`: 76 rows, 279 columns.
- `Profile(20260703_051248).csv`: 1,222 rows, 271 columns.

`tools/summarize_unreal_csv_profile.py` parses these files into
`unreal_csv_profile_summary.json` and `unreal_csv_profile_summary.csv`. The
larger profile reports global process counters such as `FrameTime` p50/p95
4.662/6.318 ms, `GPUTime` p50/p95 1.455/1.672 ms, `RHI/DrawCalls` p50 106, and
`GPUMem/LocalUsedMB` p50 3,181 MB. This is useful as a profiler smoke, but not
as phase- or backend-aligned evidence because the CSV has no SPPA phase/backend
events beyond generic PSO events. The validated comparative evidence remains
the benchmark runner's own phase-labeled CSV/JSON artifacts.

## Project-Asset Baseline Extension

The benchmark runner now supports an opt-in `project_assets` backend. This is
separate from the original `unreal_assets` backend:

- `unreal_assets`: lightweight placeholder benchmark actor.
- `project_assets`: reviewed project static meshes for labels that exist in
  this repository.

Current reviewed project-asset labels:

- `cow` -> `/Game/cow_mesh`
- `tower` -> `/Game/tower_mesh`

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10,50" `
  -Backends "no_render,project_assets,semantic_proxy" `
  -Labels "cow,tower" `
  -Repetitions 2 `
  -WarmupFrames 20 `
  -MeasureFrames 60 `
  -UpdateEveryFrames 15 `
  -TimeoutSeconds 1200 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T193225Z_packaged_render`
- Manifest: `run_manifest.json`
- Summary: `packaged_render_summary.json`
- Frame table: `packaged_frame_summary.csv`

Frame-time summary, P95 milliseconds:

| Backend | Count | Create | Pose | Shape | Components | Est. triangles |
|---|---:|---:|---:|---:|---:|---:|
| project_assets | 10 | 7.051 | 7.029 | 6.958 | 10 | 33,460 |
| semantic_proxy | 10 | 6.434 | 7.341 | 7.507 | 40 | 22,640 |
| project_assets | 50 | 7.296 | 7.664 | 6.789 | 50 | 167,300 |
| semantic_proxy | 50 | 8.779 | 10.022 | 22.445 | 200 | 113,200 |

Payload application p50/p95 milliseconds:

| Backend | Count | Create | Pose update | Shape update |
|---|---:|---:|---:|---:|
| project_assets | 10 | 2.487 / 4.058 | 0.340 / 0.513 | 0.326 / 0.428 |
| semantic_proxy | 10 | 4.855 / 4.885 | 0.989 / 1.113 | 2.409 / 3.146 |
| project_assets | 50 | 3.445 / 3.445 | 1.384 / 1.642 | 1.060 / 1.189 |
| semantic_proxy | 50 | 22.873 / 23.746 | 4.115 / 4.464 | 10.679 / 12.190 |

Interpretation:

- When a reviewed project asset exists, the asset backend is the better runtime
  choice in this run: fewer components and lower update cost.
- SPPA is not justified as a replacement for available curated assets.
- The defensible SPPA gap remains sparse or long-tail semantic telemetry where
  no suitable asset exists, or where a bounded fallback with explicit uncertainty
  is preferable to hallucinating a mesh.
- This run is still not VR validation, phase-aligned GPU-profiler validation, live telemetry,
  or a user study.

## HISM Batch Diagnostic Extension

The benchmark runner and the live component now support an opt-in
`semantic_proxy_instanced` / `SEMANTIC_PROXY_INSTANCED` backend. It consumes the
same obstacle payload and SPPA descriptor JSON as the actor-level
`semantic_proxy` backend, but groups primitive parts into
`UHierarchicalInstancedStaticMeshComponent` batches by primitive/material/
evidence/uncertainty signature.

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "50,100" `
  -Backends "semantic_proxy,semantic_proxy_instanced" `
  -Repetitions 1 `
  -WarmupFrames 10 `
  -MeasureFrames 30 `
  -UpdateEveryFrames 10 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T215340Z_packaged_render`
- Backend verification:
  `pipeline/logs/sppa_backend_verify_latest.json`
- Summary:
  `experiments/sppa_packaged_render/20260702T215340Z_packaged_render/packaged_render_summary.json`

Selected 100-object results:

| Backend | Components / est. draw calls | Est. triangles | Create action P95 | Shape-update action P95 | Shape-stream frame P95 |
|---|---:|---:|---:|---:|---:|
| `semantic_proxy` | 432 / 432 | 208,864 | 49.760 ms | 20.736 ms | 42.903 ms |
| `semantic_proxy_instanced` | 11 / 11 | 208,864 | 12.584 ms | 13.270 ms | 33.626 ms |

Interpretation:

- HISM batching sharply reduces component and estimated draw-call pressure for
  the same synthetic SPPA part set.
- HISM also reduces creation and shape-update payload application cost in this
  diagnostic run.
- The 100-object shape-stream case still misses both a 30 FPS and 60 FPS P95
  frame budget (`33.626 ms`).
- The 50-object HISM shape-stream case measured `18.057 ms` P95, below a 30 FPS
  budget but above a 60 FPS budget.
- This is the correct engineering direction for dense scenes, but it is not yet
  publishable evidence of dense VR readiness. Remaining gaps include
  per-instance color heterogeneity without extra HISM groups, operational
  collision semantics, headset/runtime profiling, and phase-aligned GPU profiler validation.

2026-07-03 update: the HISM batch path was later changed to defer render-state
dirty marking during batch instance updates and flush once per touched group.
See `docs/sppa_hism_deferred_dirty_benchmark_20260703.md`. Under comparable
100-object conditions, HISM shape-stream frame P95 improved from `33.626 ms` to
`29.718 ms`; a longer HISM-only run reported shape-stream frame P95
`29.715 ms` with 6/360 shape frames above 33 ms. This was later downgraded by
the dense scaling and isolated no-CSV-profiler reruns in
`docs/sppa_hism_dense_scaling_benchmark_20260703.md`, where the 100-object
shape-stream P95 was `38.657 ms` and `37.126 ms`. The revised allowed claim is
narrower: HISM keeps draw-group pressure low, but stable packaged desktop 30 FPS
P95 shape-update performance is not demonstrated. This is still not 60 FPS,
headset, live-network, phase-aligned GPU-profiler, real-UAV, or operator
evidence.

2026-07-03 partial-update update: the HISM batch path now supports explicit
`partial_obstacle_update=true` payloads that retain unmentioned entities and
remove stale parts for mentioned entities. See
`docs/sppa_hism_partial_update_benchmark_20260703.md`. A changed-track packaged
desktop run with `PoseUpdateFraction=0.10` and `ShapeUpdateFraction=0.10`
reported frame P95 through 500 objects of 16.528 ms for pose stream and
29.787 ms for shape stream, with 11 active draw groups and no measured hitches
above 33 ms. This does not rescue dense all-object updates: a new dense
100-object run still reported 46.151 ms shape-stream P95, and a sparse-shape but
dense-pose run still failed at 250 and 500 objects. The allowed claim is
therefore a changed-track scheduler claim, not dense-scene VR readiness.

## HISM Live-Route Regression

After the diagnostic benchmark, the live `UPorceTelemetryComponent` route was
extended with a third selectable backend:

- `UNREAL_ASSETS`
- `SEMANTIC_PROXY`
- `SEMANTIC_PROXY_INSTANCED`

Verification artifact:

- `pipeline/logs/sppa_backend_verify_latest.json`

Verified behavior:

| Check | Result |
|---|---:|
| Enum exposes `SEMANTIC_PROXY_INSTANCED` | pass |
| UI/backend toggle cycles assets -> actor proxy -> HISM proxy -> assets | pass |
| Component live route accepts normal obstacle payload | pass |
| Live HISM route spawns batch actors | 1 |
| Per-entity actors in live HISM route | 0 |
| Live HISM instances for the smoke descriptor | 3 |
| Switch back to assets destroys live HISM actor | pass |
| Reduced descriptor compacts HISM instances | 4 -> 2 |
| Material/evidence group change leaves exact live instance count | 2 |
| Matching `pose_update` packet preserves live instance count | pass, 2 remain |
| Mismatched `descriptor_id` update is rejected without deleting instances | pass, 2 remain |
| `shape_param_update` without replacement parts is rejected | pass, 2 remain |
| Matching `shape_param_update` with parts is accepted | pass, 2 remain |
| HISM groups use dynamic material instances | pass |
| HISM semantic material color tags are present | pass |
| Observed descriptor color creates observed-color HISM group | pass, `032_160_220` |
| HISM confidence bucket is part of the group signature | pass |
| Opt-in confirmed obstacle collision | pass, active HISM groups `QUERY_ONLY` |
| Tentative obstacle collision | pass, active HISM groups `NO_COLLISION` |
| Explicit `{"obstacles":[]}` clears live handles | 0 remain |

An updated packaged smoke run also rebuilt the executable with the live HISM
changes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10" `
  -Backends "semantic_proxy_instanced" `
  -Repetitions 1 `
  -WarmupFrames 5 `
  -MeasureFrames 10 `
  -UpdateEveryFrames 5 `
  -TimeoutSeconds 900 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T210611Z_packaged_render`

Smoke result:

| Backend | Count | Create P95 | Pose P95 | Shape P95 | Components / draw calls | Est. triangles |
|---|---:|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 10 | 8.481 ms | 6.883 ms | 7.590 ms | 11 / 11 | 23,760 |

This smoke run proves the packaged runner still works after the live-route
change. It is not a replacement for the 50/100-object diagnostic above and is
not VR validation.

After adding the HISM `descriptor_id`/action contract checks, the packaged smoke
was rerun:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10" `
  -Backends "semantic_proxy_instanced" `
  -Repetitions 1 `
  -WarmupFrames 5 `
  -MeasureFrames 10 `
  -UpdateEveryFrames 5 `
  -TimeoutSeconds 900 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T212958Z_packaged_render`

Post-contract smoke result:

| Backend | Count | Create frame P95 | Pose frame P95 | Shape frame P95 | Create action P95 | Pose action P95 | Shape action P95 | Components / draw calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 10 | 10.958 ms | 6.439 ms | 5.862 ms | 3.934 ms | 0.789 ms | 1.563 ms | 11 / 11 |

This proves the packaged HISM path still launches and measures after the
contract checks. It remains a smoke test only.

After adding HISM group-level dynamic material/color parity, the packaged smoke
was rerun:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10" `
  -Backends "semantic_proxy_instanced" `
  -Repetitions 1 `
  -WarmupFrames 5 `
  -MeasureFrames 10 `
  -UpdateEveryFrames 5 `
  -TimeoutSeconds 900 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T213941Z_packaged_render`

Post-material smoke result:

| Backend | Count | Create frame P95 | Pose frame P95 | Shape frame P95 | Create action P95 | Pose action P95 | Shape action P95 | Components / draw calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 10 | 10.054 ms | 4.761 ms | 4.669 ms | 1.837 ms | 0.563 ms | 1.157 ms | 11 / 11 |

The HISM material parity is group-level. Observed colors or confidence buckets
that differ across objects create separate HISM groups; this is deterministic
and correct for the current contract, but not as scalable as true per-instance
custom material data would be.

## HISM Per-Instance Color/Confidence Custom Data

The HISM backend now exposes `bUsePerInstanceColorAndConfidenceData`. When this
is enabled, resolved RGBA, confidence, evidence-source scalar, uncertainty
scalar, and observed-color flag are written into eight Unreal
`PerInstanceSMCustomData` floats. The grouping key no longer splits by color or
confidence bucket. The default mode remains group-level color/material so the
current packaged visuals are preserved unless the opt-in mode is selected.

Material/verification artifacts:

- `pipeline/logs/sppa_backend_verify_latest.json`
- `pipeline/logs/sppa_per_instance_material_latest.json`
- Material asset: `Unreal/Content/SPPA/M_SPPA_PerInstanceVisual.uasset`

Verified behavior:

| Check | Result |
|---|---:|
| Material asset exists and reports `HasPerInstanceCustomData=True` | pass |
| Material path used by HISM custom-data batch | `/Game/SPPA/M_SPPA_PerInstanceVisual.M_SPPA_PerInstanceVisual` |
| API exposes `bUsePerInstanceColorAndConfidenceData` | pass |
| Two differently colored/confident instances batch into one active HISM group | pass |
| Active instances in that group | 2 |
| Custom floats per instance | 8 |
| Custom data preserves red/confidence and cyan/confidence values | pass |
| HISM component carries `SPPA_PER_INSTANCE_VISUAL_MATERIAL` tag | pass |

Observed-color stress benchmark:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "100" `
  -Backends "semantic_proxy_instanced,semantic_proxy_instanced_customdata" `
  -Repetitions 1 `
  -WarmupFrames 10 `
  -MeasureFrames 30 `
  -UpdateEveryFrames 10 `
  -TimeoutSeconds 1200 `
  -NoCsvProfile `
  -ObservedColorStress
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T220529Z_packaged_render`

Selected 100-object observed-color stress results:

| Backend | Components / est. draw calls | Create action P95 | Pose action P95 | Shape action P95 | Shape-stream frame P95 |
|---|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 188 / 188 | 27.792 ms | 9.669 ms | 18.303 ms | 37.725 ms |
| `semantic_proxy_instanced_customdata` | 11 / 11 | 18.608 ms | 7.050 ms | 15.351 ms | 38.136 ms |

Interpretation:

- Per-instance custom data removes the group explosion caused by heterogeneous
  observed colors/confidence buckets in this stress case.
- Action costs improved in this run, but frame P95 did not improve for the
  shape stream. Treat this as structural scalability evidence, not FPS proof.
- The custom-data material now reads Unreal `PerInstanceCustomData` and is
  applied in the opt-in HISM path. This closes the earlier material-read gap,
  but not the dense VR/phase-aligned GPU-profiler validation gap.

Packaged material cook smoke:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10" `
  -Backends "semantic_proxy_instanced_customdata" `
  -Repetitions 1 `
  -WarmupFrames 5 `
  -MeasureFrames 20 `
  -UpdateEveryFrames 10 `
  -TimeoutSeconds 900 `
  -NoCsvProfile `
  -ObservedColorStress
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T223153Z_packaged_render`

Selected 10-object cooked-material smoke results:

| Backend | Components / est. draw calls | Create action | Pose action P95 | Shape action P95 | Shape-stream frame P95 |
|---|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced_customdata` | 11 / 11 | 1.940 ms | 0.713 ms | 1.364 ms | 5.341 ms |

Cook/package evidence:

- `Unreal/Saved/Cooked/Windows/AirTraffic/Content/SPPA/M_SPPA_PerInstanceVisual.uasset`
- `Unreal/Saved/Cooked/Windows/AirTraffic/Content/SPPA/M_SPPA_PerInstanceVisual.uexp`
- AutomationTool `FinalCopyWin64_UFSFiles.txt` includes both files.
- Cook log compiled shadermaps for `M_SPPA_PerInstanceVisual` in SM6 and SM5.

After adding the HISM collision-policy regression, the packaged smoke was rerun:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Counts "10" `
  -Backends "semantic_proxy_instanced" `
  -Repetitions 1 `
  -WarmupFrames 5 `
  -MeasureFrames 10 `
  -UpdateEveryFrames 5 `
  -TimeoutSeconds 900 `
  -NoCsvProfile
```

Artifacts:

- Run directory:
  `experiments/sppa_packaged_render/20260702T214918Z_packaged_render`

Post-collision smoke result:

| Backend | Count | Create frame P95 | Pose frame P95 | Shape frame P95 | Create action P95 | Pose action P95 | Shape action P95 | Components / draw calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 10 | 8.290 ms | 4.991 ms | 4.815 ms | 2.122 ms | 0.609 ms | 1.342 ms | 11 / 11 |

The HISM collision policy is intentionally narrow. Collision is disabled by
default and becomes `QUERY_ONLY` only when `bEnableCollisionForConfirmed` is
enabled and the obstacle payload marks the object as confirmed. Tentative
objects remain `NO_COLLISION`. This verifies implementation policy, not
operational safety, physics behavior, or headset interaction semantics.
