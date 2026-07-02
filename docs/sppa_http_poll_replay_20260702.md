# SPPA HTTP Poll Replay Evidence - 2026-07-02

## Scope

This note documents the valid local-loopback HTTP polling replay for the SPPA
Unreal backend. It exercises `UPorceTelemetryComponent` through the Unreal HTTP
module using the same `/api/ui/data` obstacle payload shape used by the current
AeroTwin telemetry path.

Claim supported by this artifact:

- The same HTTP-polled obstacle payload shape can drive both `UnrealAssets` and
  `SemanticProxy` spawn backends inside Unreal Editor-Cmd.
- Descriptor-driven SPPA actors can be spawned and updated through the Unreal
  telemetry component without request/parsing failures in this local replay.
- A debug `NoRender` baseline can exercise HTTP parsing and entity-state
  lifecycle without actor spawning, giving a lower-bound component-path cost.
- Paired incremental-delta artifacts can separate common HTTP/JSON/entity-state
  cost from the extra cost of placeholder asset spawning and SPPA component
  generation.

Claims not supported by this artifact:

- Packaged-build runtime behavior.
- Render-thread, GPU, draw-call, memory, or VR FPS behavior.
- Live flight-server behavior, real network jitter, or camera/georeferencing
  behavior.
- Superiority over curated Unreal assets.
- Operator readability, workload, situational awareness, or safety.

## Command

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_http_poll_replay.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5 -SkipBuild -Seed 20260702
```

The run used an already rebuilt Unreal target with the reflected
`PollNowBlockingForTest()` debug helper available.

## Valid Artifact

Directory:

```text
experiments/sppa_unreal_http_poll_replay/20260702T101020Z_http_poll_replay
```

Manifest summary:

- Mode: HTTP poll replay via `PollNowBlockingForTest`.
- Engine: Unreal 5.7.4.
- Descriptor fixtures loaded: 52.
- Descriptor input hash: `459d477d66f5b9af`.
- Counts: 10, 50, 100, 250, 500 actors.
- Repetitions: 10 per count.
- Pose updates: 5 batches per actor row.
- HTTP requests: 1050 total.
- Schedule seed: `20260702`.
- Schedule design: seeded count/repetition groups with counterbalanced
  rotated/reversed backend order. Create/pose/shape remain track-lifecycle
  ordered inside each condition.
- Benchmark garbage collection is requested before each condition; cold and
  warm cache behavior are still not separated.
- Failures: none reported by the manifest.
- Git state: dirty, because the benchmark and paper edits were still in
  progress.

Artifacts:

- `run_manifest.json`
- `input_descriptors.jsonl`
- `http_poll_replay_schedule.jsonl`
- `http_poll_replay_order_trace.csv`
- `http_poll_replay_rows.csv`
- `http_poll_replay_pose_poll_rows.csv`
- `component_identity_trace.jsonl`
- `sppa_runtime_update_trace.csv`
- `sppa_runtime_update_trace.jsonl`
- `sppa_runtime_update_summary.json`
- `http_poll_replay_summary.json`
- `http_poll_replay_summary_by_count.json`
- `http_poll_replay_batch_summary_by_count.csv`
- `http_poll_replay_batch_summary_by_count.json`
- `http_poll_replay_incremental_deltas_by_count.csv`
- `http_poll_replay_incremental_deltas_by_count.json`

## Global Timing Summary

Times are per object in milliseconds across 50 rows per backend. These are
descriptive preliminary tails, not operational tail-latency guarantees.

| Backend | Create P50 | Create P95 | Pose P50 | Pose P95 | Shape P50 | Shape P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `NoRender` debug | 0.6577 | 1.3239 | 0.2209 | 0.6223 | 0.1425 | 0.5688 |
| `UnrealAssets` placeholder | 0.7129 | 1.3484 | 0.2681 | 0.6947 | 0.1477 | 0.6172 |
| `SemanticProxy/SPPA-DESC` | 1.4897 | 2.4012 | 0.4068 | 0.8706 | 0.2250 | 0.6963 |

At 500 actors:

| Backend | Actors after shape | Components after shape | HTTP requests per row |
| --- | ---: | ---: | ---: |
| `NoRender` debug | 0 | 0 | 7 |
| `UnrealAssets` placeholder | 500 | 500 | 7 |
| `SemanticProxy/SPPA-DESC` | 500 | 2680 | 7 |

## Batch-Level Timing

Create and shape are one HTTP poll each. Pose is reported from the raw
pose-poll artifact, with five pose polls per repetition. Values are p50/p95
milliseconds. Create/shape have `n=10` per size/backend; pose has `n=50` per
size/backend. With these sample sizes, p95 is descriptive rather than a robust
tail-latency estimate.

| Backend | Actors | Create poll | Pose poll | Shape poll |
| --- | ---: | ---: | ---: | ---: |
| `NoRender` | 10 | 11.8/13.5 | 5.7/6.8 | 5.6/7.5 |
| `NoRender` | 50 | 32.9/36.2 | 12.3/14.3 | 8.9/10.4 |
| `NoRender` | 100 | 63.5/67.1 | 20.4/23.2 | 14.2/15.9 |
| `NoRender` | 250 | 159.2/163.0 | 45.5/48.6 | 29.9/32.0 |
| `NoRender` | 500 | 329.8/367.0 | 87.9/104.1 | 55.8/65.1 |
| `UnrealAssets` | 10 | 12.1/14.6 | 6.1/7.2 | 5.9/6.4 |
| `UnrealAssets` | 50 | 34.1/39.1 | 12.2/14.7 | 9.9/11.7 |
| `UnrealAssets` | 100 | 69.5/72.7 | 21.5/23.7 | 14.8/16.9 |
| `UnrealAssets` | 250 | 172.4/187.2 | 47.1/50.6 | 31.4/33.7 |
| `UnrealAssets` | 500 | 357.4/371.6 | 91.5/96.8 | 58.5/66.4 |
| `SemanticProxy/SPPA-DESC` | 10 | 22.7/24.7 | 6.8/8.3 | 6.8/7.6 |
| `SemanticProxy/SPPA-DESC` | 50 | 74.2/77.3 | 17.4/19.0 | 13.5/14.1 |
| `SemanticProxy/SPPA-DESC` | 100 | 146.2/150.7 | 29.4/31.8 | 22.1/30.1 |
| `SemanticProxy/SPPA-DESC` | 250 | 367.4/391.7 | 68.0/72.3 | 49.0/52.4 |
| `SemanticProxy/SPPA-DESC` | 500 | 738.6/839.3 | 134.0/142.3 | 95.4/112.5 |

## Paired Incremental Deltas

The latest run also emits paired deltas by scene size and action. The 500-actor
rows below report p50 delta and mean delta with bootstrap 95% confidence
interval in milliseconds. They are not stage timings; they are paired
component-path differences from the same replay.

| Comparison | Create delta | Pose delta | Shape delta | Component delta |
| --- | ---: | ---: | ---: | ---: |
| `UnrealAssets-NoRender` | 24.5 [28.7; 9.3, 45.5] | 1.1 [2.1; -1.0, 4.7] | 0.9 [2.9; 0.4, 5.8] | 500 |
| `SPPA-NoRender` | 413.9 [424.8; 401.1, 452.2] | 45.5 [44.8; 42.2, 47.7] | 40.1 [40.8; 37.0, 44.5] | 2680 |
| `SPPA-UnrealAssets` | 387.8 [396.1; 371.7, 419.8] | 40.8 [42.7; 40.3, 45.0] | 37.9 [37.8; 35.2, 40.5] | 2180 |

## Runtime Update Trace

The valid run also records entity-level SPPA update traces with resolver,
uncertainty, source, descriptor, and component-reuse fields. This is
instrumentation of actor/component state, not render-thread or GPU timing.

| Phase | Rows | Components created | Components reused | Components destroyed | Fallback actor tags | Yaw-ambiguous actor tags | Scale sources |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Create | 2,950 | 24,740 | 0 | 0 | 550 | 2,950 | 690 metric / 2,260 prior |
| Pose update | 45,500 | 0 | 246,700 | 0 | 2,750 | 45,500 | 34,200 metric / 11,300 prior |
| Shape update | 9,100 | 0 | 49,340 | 0 | 550 | 9,100 | 6,840 metric / 2,260 prior |

The semantic-proxy backend is not faster than the placeholder asset backend in
this replay. Its measured value is narrower: the current descriptor path stays
in a low-millisecond creation range and supports pose/shape update routing
through the same HTTP-polled component path. The no-render baseline shows that
payload parsing and entity-state bookkeeping are already substantial at 500
actors. The trace shows that pose and shape updates reuse resident components
and do not reconstruct topology in this replay. At scene level, the 500-actor
SPPA create poll is 738.6/839.3 ms p50/p95, while pose and shape polls are
134.0/142.3 ms and 95.4/112.5 ms before rendering is measured. This artifact
must not be used as a frame-budget claim.

## Interpretation

This run partially addresses the earlier reviewer objection that the component
replay bypassed HTTP. It does not address the stronger runtime objection:
actual flight telemetry, network behavior, packaged Unreal execution, rendering,
GPU work, and VR presentation are still unmeasured.

The most important remaining benchmark is a packaged dense-scene replay that
records GameThread, RenderThread, GPU time, draw calls, memory, hitch rate, FPS,
actor count, component count, and backend choice for the same recorded telemetry
sequence.

## Discarded Artifact

Directory:

```text
experiments/sppa_unreal_http_poll_replay/20260702T091041Z_http_poll_replay
```

This run is invalid for paper evidence because a descriptor-loading fallback bug
loaded only one descriptor fixture. The bug was fixed before the valid run above
and the discarded run must not be cited.
