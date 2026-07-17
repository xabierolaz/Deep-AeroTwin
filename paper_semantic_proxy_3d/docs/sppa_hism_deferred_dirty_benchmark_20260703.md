# SPPA HISM Deferred-Dirty Benchmark - 2026-07-03

## Purpose

This note records the post-change benchmark for the instanced SPPA backend after
batch updates were changed to defer render-state dirty marking and flush once per
touched HISM group.

The purpose is narrow: measure whether the optimized HISM path improves the
100-object packaged synthetic shape-update stream. This is not a live telemetry,
headset, GPU-profiler, or operator-validation result.

## Implementation Change

Changed:

- `APorceSemanticProxyInstancedBatchActor::ApplyObstacleBatchJson`
- `APorceSemanticProxyInstancedBatchActor::UpsertPartInstance`

The previous path called `UpdateInstanceTransform(..., bMarkRenderStateDirty=true)`
and marked custom-data changes dirty for each individual instance. The new path
defers render-state dirty marking for batch updates and calls
`MarkRenderStateDirty()` once per touched HISM group.

The default asset backend and actor-proxy backend are unchanged.

## Verification

Backend regression smoke:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1
```

Result: passed.

## Comparable Short Run

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Backends "semantic_proxy,semantic_proxy_instanced" `
  -Counts "100" `
  -Repetitions 1 `
  -WarmupFrames 10 `
  -MeasureFrames 30 `
  -UpdateEveryFrames 10 `
  -TimeoutSeconds 1200
```

Output:

`experiments/sppa_packaged_render/20260703T031115Z_packaged_render`

Key comparison against `20260702T215340Z_packaged_render`:

| Backend | Phase | Old frame P95 | New frame P95 | Old action P95 | New action P95 |
|---|---:|---:|---:|---:|---:|
| `semantic_proxy` | shape stream | 42.903 ms | 41.473 ms | 20.736 ms | 21.819 ms |
| `semantic_proxy_instanced` | shape stream | 33.626 ms | 29.718 ms | 13.270 ms | 12.115 ms |

Interpretation: the actor-proxy baseline is essentially unchanged; the HISM
shape stream improves enough to cross the 30 FPS P95 threshold in this short
run, but remains above the 60 FPS threshold.

## Longer HISM-Only Run

Command:

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
  -TimeoutSeconds 900
```

Output:

`experiments/sppa_packaged_render/20260703T031246Z_packaged_render`

Results:

| Backend | Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `semantic_proxy_instanced` | 100 | create steady | 4.510 ms | 5.553 ms | 5.921 ms | 0 | 0 | 11 |
| `semantic_proxy_instanced` | 100 | pose stream | 4.677 ms | 13.884 ms | 15.766 ms | 0 | 0 | 11 |
| `semantic_proxy_instanced` | 100 | shape stream | 4.752 ms | 29.715 ms | 35.021 ms | 6 | 0 | 11 |

Action timing:

| Action | n | P50 | P95 | Max |
|---|---:|---:|---:|---:|
| create | 3 | 11.255 ms | 16.126 ms | 16.667 ms |
| pose update | 30 | 5.645 ms | 7.226 ms | 8.324 ms |
| shape update | 30 | 10.835 ms | 13.527 ms | 13.906 ms |

## Allowed Claim

The optimized HISM path showed a promising 100-object packaged-desktop result in
this run: the HISM route met a 30 FPS P95 frame budget in the measured shape
stream.

This claim was later downgraded by the dense scaling and isolated no-CSV-profiler
reruns in `docs/sppa_hism_dense_scaling_benchmark_20260703.md`. Those reruns
reported 100-object shape-stream P95 values of 38.657 ms and 37.126 ms. The
current defensible statement is therefore that HISM batching substantially
reduces draw-group pressure, but stable 30 FPS P95 shape-update performance at
100 objects is not yet demonstrated.

It does not support a 60 FPS claim, a headset/VR claim, live telemetry timing,
GPU-profiler timing, real UAV imagery, or operator interpretation. The shape
stream still had 6 frames above 33 ms in 360 measured frames.
