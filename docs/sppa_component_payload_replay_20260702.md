# SPPA Component Payload Replay - 2026-07-02

This note records a preliminary `UPorceTelemetryComponent` lifecycle replay using the same obstacle payload shape expected from `/api/ui/data`, but bypassing HTTP.

## Scope

Measured:

- `UPorceTelemetryComponent.ApplyObstacleBatchJson`.
- Payload parsing for `{"obstacles":[...]}`.
- Entity upsert and managed actor lifecycle.
- Backend switch between `UnrealAssets` and `SemanticProxy`.
- Descriptor routing through `sppa_descriptor`.
- Update-packet routing through `sppa_update_packet`.
- Pose and shape update batches.

Not measured:

- Actual HTTP polling.
- Packaged build.
- Real curated Unreal asset classes.
- Render-thread, GPU, FPS, draw calls, VR frame-time, or headset behavior.
- Operator readability or safety.

The `UnrealAssets` backend in this benchmark uses `StaticMeshActor` placeholders. It is a component lifecycle baseline, not the final curated-asset comparison.

## Commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_component_replay.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5 -SkipBuild
```

## Artifacts

- Benchmark directory: `experiments/sppa_unreal_component_replay/20260702T085905Z_component_payload_replay`
- Manifest: `run_manifest.json`
- Input descriptors: `input_descriptors.jsonl`
- Per-run rows: `component_replay_rows.csv`
- Summary: `component_replay_summary.json`
- Per-count summary: `component_replay_summary_by_count.json`
- Component identity trace: `component_identity_trace.jsonl`

Manifest facts:

- Engine: Unreal Engine `5.7.4-51494982+++UE5+Release-5.7`
- Git head: `e7ec1ff80b96f4335599221e243d70f3e62dd716`
- Git dirty: `true`
- Counts: `10, 50, 100, 250, 500`
- Repetitions: `10`
- Updates per actor: `5`
- Descriptor count loaded: `52`
- Failures: `[]`

Methodological caveats:

- The run was executed in Unreal Editor-Cmd, not a packaged build.
- The benchmark bypassed HTTP by calling `ApplyObstacleBatchJson` directly.
- The asset backend used `StaticMeshActor` placeholders, not curated project assets.
- The run did not separate cold/warm cache behavior or randomize backend/count order.
- With ten repetitions per count, p95 values are descriptive preliminary tails, not operational tail-latency guarantees.
- At 500 actors, SPPA used 2680 components versus 500 for the placeholder asset baseline; render-thread and draw-call consequences remain unmeasured.
- Because `git_dirty=true`, submission-grade reproduction should rerun from a clean commit or archive the exact patch state.

## Summary

Per-object p50/p95 timings in milliseconds:

| Backend | Components at 500 | Create p50 | Create p95 | Pose update p50 | Pose update p95 | Shape update p50 | Shape update p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| UnrealAssets placeholder | 500 | 0.5116 | 0.9882 | 0.0226 | 0.0447 | 0.0323 | 0.0703 |
| SemanticProxy / SPPA-DESC | 2680 | 1.2892 | 1.6423 | 0.0426 | 0.0531 | 0.0683 | 0.0829 |

## Interpretation

This benchmark addresses one reviewer concern: SPPA is no longer only measured through direct actor calls. The component can consume the same obstacle payload shape for both backends, route SPPA descriptors/update packets, and keep the existing `UnrealAssets` path separate.

Allowed claim:

- In an Editor-Cmd component replay that bypasses HTTP, the same `obstacles[]` payload shape drove both the placeholder asset backend and SPPA backend; SPPA creation remained low-millisecond per actor, while pose and shape updates stayed below 0.1 ms per actor at p95 in this run.

Forbidden claims:

- Do not claim packaged performance, HTTP polling performance, real curated asset comparison, render-thread/GPU performance, VR FPS, pilot readability, safety, or flight validation.
