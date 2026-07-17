# SPPA HISM Partial-Update Benchmark - 2026-07-03

## Purpose

This note records the first packaged Unreal 5.7 benchmark after adding explicit
partial obstacle updates to the opt-in `semantic_proxy_instanced` HISM backend.
The goal is to distinguish three cases that must not be conflated:

- Dense updates: every object receives a pose and shape packet.
- Sparse shape updates: every object receives pose packets, but only 10% receive
  shape packets.
- Changed-track updates: only 10% of objects receive pose packets and only 10%
  receive shape packets.

This is packaged desktop evidence only. It is not VR/headset evidence, not live
network evidence, not real UAV evidence, and not phase-aligned GPU-profiler
evidence.

## Implementation Contract

The HISM batch actor now accepts a root payload flag:

```json
{"partial_obstacle_update": true, "obstacles": [...]}
```

When the flag is true, unmentioned entities are retained. For mentioned
entities, the previous instance keys for that entity are removed before the new
parts are upserted. This prevents stale parts when a touched entity changes
topology or part count.

The backend verifier covers the contract:

| Check | Result |
|---|---:|
| Two-entity setup live instances | 8 / 8 expected |
| Partial shape update accepted | true |
| Post-update live instances | 6 / 6 expected |
| Post-update HISM instances | 6 / 6 expected |

Verifier artifact:

`pipeline/logs/sppa_backend_verify_latest.json`

## Runs

New package:

`experiments/sppa_packaged_render/20260703T040154Z_packaged_render/package`

### Dense 100-Object Rerun

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -Backends "semantic_proxy_instanced" `
  -Counts "100" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -NoCsvProfile `
  -TimeoutSeconds 1200
```

Output:

`experiments/sppa_packaged_render/20260703T040154Z_packaged_render`

| Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | create steady | 7.707 ms | 8.945 ms | 9.736 ms | 0 | 0 | 11 |
| 100 | pose stream | 7.996 ms | 21.315 ms | 23.933 ms | 0 | 0 | 11 |
| 100 | shape stream | 8.087 ms | 46.151 ms | 50.124 ms | 24 | 4 | 11 |

Dense shape updates still fail a 30 FPS P95 frame budget at 100 objects.

### Sparse Shape, Dense Pose

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -SkipPackage `
  -PackageDir "experiments\sppa_packaged_render\20260703T040154Z_packaged_render\package" `
  -Backends "semantic_proxy_instanced" `
  -Counts "100,250,500" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -NoCsvProfile `
  -PoseUpdateFraction 1.0 `
  -ShapeUpdateFraction 0.10 `
  -TimeoutSeconds 1200
```

Output:

`experiments/sppa_packaged_render/20260703T040406Z_packaged_render`

| Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | pose stream | 8.337 ms | 22.521 ms | 23.565 ms | 0 | 0 | 11 |
| 100 | shape stream | 8.549 ms | 9.559 ms | 10.820 ms | 0 | 0 | 11 |
| 250 | pose stream | 8.298 ms | 52.474 ms | 55.540 ms | 24 | 22 | 11 |
| 250 | shape stream | 8.411 ms | 15.477 ms | 16.489 ms | 0 | 0 | 11 |
| 500 | pose stream | 8.133 ms | 104.502 ms | 109.628 ms | 24 | 24 | 11 |
| 500 | shape stream | 7.888 ms | 29.305 ms | 30.982 ms | 0 | 0 | 11 |

Sparse shape updates solve the shape stream under this synthetic schedule, but
dense pose updates remain the bottleneck at 250 and 500 objects.

Selected action timings:

| Count | Action | P50 | P95 | Payload P50 |
|---:|---|---:|---:|---:|
| 100 | pose update | 9.307 ms | 9.771 ms | 129,808 bytes |
| 100 | shape update | 2.410 ms | 2.727 ms | 35,599 bytes |
| 250 | pose update | 22.426 ms | 23.833 ms | 324,352 bytes |
| 250 | shape update | 6.034 ms | 6.522 ms | 86,970 bytes |
| 500 | pose update | 45.830 ms | 47.967 ms | 648,944 bytes |
| 500 | shape update | 12.843 ms | 14.208 ms | 174,592 bytes |

### Changed-Track Scheduler

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 `
  -SkipPackage `
  -PackageDir "experiments\sppa_packaged_render\20260703T040154Z_packaged_render\package" `
  -Backends "semantic_proxy_instanced" `
  -Counts "100,250,500" `
  -Repetitions 3 `
  -WarmupFrames 30 `
  -MeasureFrames 120 `
  -UpdateEveryFrames 15 `
  -NoCsvProfile `
  -PoseUpdateFraction 0.10 `
  -ShapeUpdateFraction 0.10 `
  -TimeoutSeconds 1200
```

Output:

`experiments/sppa_packaged_render/20260703T040602Z_packaged_render`

| Count | Phase | Frame P50 | Frame P95 | Frame P99 | Hitches >33 ms | Hitches >50 ms | Draw groups |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | create steady | 8.359 ms | 9.761 ms | 10.584 ms | 0 | 0 | 11 |
| 100 | pose stream | 8.501 ms | 10.058 ms | 10.963 ms | 0 | 0 | 11 |
| 100 | shape stream | 8.504 ms | 9.629 ms | 10.286 ms | 0 | 0 | 11 |
| 250 | create steady | 8.087 ms | 9.539 ms | 10.037 ms | 0 | 0 | 11 |
| 250 | pose stream | 8.283 ms | 10.010 ms | 10.817 ms | 0 | 0 | 11 |
| 250 | shape stream | 8.100 ms | 15.454 ms | 16.369 ms | 0 | 0 | 11 |
| 500 | create steady | 8.342 ms | 9.960 ms | 10.491 ms | 0 | 0 | 11 |
| 500 | pose stream | 8.814 ms | 16.528 ms | 17.602 ms | 0 | 0 | 11 |
| 500 | shape stream | 8.368 ms | 29.787 ms | 30.735 ms | 0 | 0 | 11 |

Selected action timings:

| Count | Action | P50 | P95 | Payload P50 |
|---:|---|---:|---:|---:|
| 100 | pose update | 1.471 ms | 1.757 ms | 13,268 bytes |
| 100 | shape update | 2.373 ms | 2.757 ms | 35,599 bytes |
| 250 | pose update | 3.832 ms | 4.085 ms | 32,751 bytes |
| 250 | shape update | 6.141 ms | 6.468 ms | 86,970 bytes |
| 500 | pose update | 8.790 ms | 9.660 ms | 65,198 bytes |
| 500 | shape update | 13.194 ms | 13.713 ms | 174,592 bytes |

## Interpretation

Allowed claim:

- The opt-in HISM backend now has a tested partial-update contract that preserves
  unmentioned entities and removes stale parts for mentioned entities.
- Under a synthetic changed-track schedule where 10% of objects receive pose
  updates and 10% receive shape updates, packaged desktop frame P95 stayed below
  33.3 ms through 500 objects, with 11 active draw groups and no measured
  hitches above 33 ms.
- Sparse shape updates alone are not enough if pose updates are still dense: at
  250 and 500 objects, dense pose updates exceeded 33.3 ms P95.

Forbidden claim:

- Do not claim dense all-object update performance. Dense 100-object shape
  updates still reported 46.151 ms P95 in the new package.
- Do not claim VR/headset readiness, live telemetry performance, or GPU-bound
  performance. The benchmark is packaged desktop Tick timing without
  phase-aligned GPU profiler events.
- Do not claim that 10% is a universal mission frequency. It is a tested
  scheduler stress point that must be justified by recorded track-change rates in
  future flight or simulated mission logs.

Next evidence target:

- Measure real or simulated mission track-change distributions: create rate,
  pose-change rate, shape-change rate, and class-change rate per active track.
- Re-run the same partial-update benchmark with rates derived from those logs.
- Add phase-aligned Unreal CSV/stat events for apply time, GameThread,
  RenderThread, GPU time, draw calls, and memory.
