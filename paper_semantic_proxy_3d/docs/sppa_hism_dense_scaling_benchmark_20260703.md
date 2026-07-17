# SPPA HISM Dense Scaling Benchmark - 2026-07-03

## Purpose

This note records the post-optimization dense scaling check for the opt-in
HISM SPPA backend. It tests whether the deferred-dirty HISM path scales from
100 to 250 and 500 synthetic objects in a packaged Unreal 5.7 executable.

This is still not VR, headset, live-network, real-UAV, user-study, or
phase-aligned GPU-profiler evidence.

## Dense Sweep

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -SkipPackage `
  -PackageDir "experiments\sppa_packaged_render\20260703T031115Z_packaged_render\package" `
  -Backends "semantic_proxy_instanced" `
  -Counts "100,250,500" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -NoCsvProfile `
  -TimeoutSeconds 1200
```

Output:

`experiments/sppa_packaged_render/20260703T033655Z_packaged_render`

Frame summary:

| Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | create steady | 6.556 ms | 9.883 ms | 11.807 ms | 0 | 0 | 11 |
| 100 | pose stream | 6.600 ms | 18.921 ms | 21.872 ms | 0 | 0 | 11 |
| 100 | shape stream | 6.655 ms | 38.657 ms | 44.562 ms | 22 | 1 | 11 |
| 250 | create steady | 5.448 ms | 8.250 ms | 9.508 ms | 0 | 0 | 11 |
| 250 | pose stream | 5.920 ms | 41.609 ms | 48.708 ms | 23 | 4 | 11 |
| 250 | shape stream | 5.778 ms | 94.018 ms | 108.777 ms | 24 | 24 | 11 |
| 500 | create steady | 5.544 ms | 7.920 ms | 8.899 ms | 0 | 0 | 11 |
| 500 | pose stream | 5.565 ms | 78.933 ms | 91.509 ms | 24 | 24 | 11 |
| 500 | shape stream | 5.912 ms | 186.113 ms | 213.999 ms | 24 | 24 | 11 |

Action timing:

| Count | Action | P50 | P95 | Max |
|---:|---|---:|---:|---:|
| 100 | create | 17.252 ms | 17.982 ms | 18.064 ms |
| 100 | pose update | 7.890 ms | 8.902 ms | 10.019 ms |
| 100 | shape update | 14.797 ms | 17.193 ms | 19.378 ms |
| 250 | create | 37.635 ms | 39.741 ms | 39.974 ms |
| 250 | pose update | 18.343 ms | 21.401 ms | 24.980 ms |
| 250 | shape update | 37.488 ms | 40.411 ms | 42.187 ms |
| 500 | create | 81.388 ms | 81.428 ms | 81.432 ms |
| 500 | pose update | 35.350 ms | 41.874 ms | 44.730 ms |
| 500 | shape update | 71.744 ms | 83.066 ms | 94.885 ms |

## Isolated 100-Object Rerun

Because an earlier 100-object HISM run reported shape-stream P95 below 33 ms,
we reran the 100-object case alone under the same no-CSV-profiler condition:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -SkipPackage `
  -PackageDir "experiments\sppa_packaged_render\20260703T031115Z_packaged_render\package" `
  -Backends "semantic_proxy_instanced" `
  -Counts "100" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -NoCsvProfile `
  -TimeoutSeconds 900
```

Output:

`experiments/sppa_packaged_render/20260703T033840Z_packaged_render`

| Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | create steady | 5.677 ms | 7.688 ms | 8.517 ms | 0 | 0 | 11 |
| 100 | pose stream | 5.782 ms | 16.624 ms | 20.021 ms | 0 | 0 | 11 |
| 100 | shape stream | 5.604 ms | 37.126 ms | 44.931 ms | 22 | 1 | 11 |

Action timing:

| Count | Action | P50 | P95 | Max |
|---:|---|---:|---:|---:|
| 100 | create | 13.481 ms | 17.610 ms | 18.068 ms |
| 100 | pose update | 6.906 ms | 8.435 ms | 8.758 ms |
| 100 | shape update | 14.736 ms | 16.906 ms | 20.522 ms |

## Interpretation

HISM batching solves the component/draw-group explosion, but it does not yet
solve the dense update problem.

Allowed claim:

- The HISM backend keeps the synthetic proxy scene at 11 active draw groups
  across 100, 250, and 500 objects.
- Create-steady frames are below 16.7 ms P95 even at 500 synthetic objects in
  this packaged desktop run.
- Pose updates are acceptable at 100 objects in the isolated run, but not at
  250 or 500 objects.

Forbidden claim:

- Do not claim stable 30 FPS P95 shape-update performance at 100 objects.
  The earlier 100-object HISM run reported 29.715 ms shape P95, but two
  subsequent no-CSV-profiler runs reported 37.126 ms and 38.657 ms.
- Do not claim dense-scene VR readiness. At 250 and 500 objects, pose and shape
  update streams miss both 30 FPS and 60 FPS P95 budgets.

Next engineering target:

- Implemented next step: the HISM backend now supports explicit partial obstacle
  updates and the benchmark runner can limit pose/shape update fractions. See
  `docs/sppa_hism_partial_update_benchmark_20260703.md`.
- The new evidence is narrow: under a 10% changed-track schedule, packaged
  desktop frame P95 stayed below 33.3 ms through 500 objects; dense all-object
  updates still fail.
- Add phase/backend events to Unreal CSV profiling if GPU/RT claims are needed.
