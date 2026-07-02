# SPPA Unreal Actor Microbenchmark - 2026-07-02

This note records the first native Unreal actor-level benchmark after the SPPA descriptor/update ingestion path was connected to `APorceSemanticProxyActor`.

## Scope

Measured:

- Direct Unreal Editor-Cmd actor creation/destruction through Unreal Python.
- Direct native descriptor ingestion through `ConfigureProxyFromDescriptorJson`.
- Direct native update-packet ingestion through `ApplyProxyUpdatePacketJson`.
- Pose updates, shape updates, no-op updates, component counts, and failure counters.

Not measured:

- `/api/ui/data` replay through `UPorceTelemetryComponent`.
- Packaged build performance.
- Render-thread, GPU, draw-call, FPS, or VR headset frame-time.
- Operator readability, NASA-TLX, SAGAT, or safety/false-confidence behavior.

## Commands

Build after C++ changes:

```powershell
& "D:\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" AirTrafficEditor Win64 Development -Project="D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject" -WaitMutex -FromMsBuild
```

Smoke test:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1
```

Benchmark:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_unreal_backend.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5 -SkipBuild
```

## Artifacts

- Smoke report: `pipeline/logs/sppa_backend_verify_latest.json`
- Benchmark directory: `experiments/sppa_unreal_backend/20260702T084924Z_editor_actor_microbenchmark`
- Manifest: `run_manifest.json`
- Input descriptors: `input_descriptors.jsonl`
- Per-run rows: `unreal_actor_microbenchmark_rows.csv`
- Per-action trace: `unreal_actor_microbenchmark_action_trace.csv`
- Component trace: `actor_component_trace.jsonl`
- Summary: `unreal_actor_microbenchmark_summary.json`

Manifest facts:

- Engine: Unreal Engine `5.7.4-51494982+++UE5+Release-5.7`
- Counts: `10, 50, 100, 250, 500`
- Repetitions: `10`
- Updates per actor: `5`
- Descriptor count loaded: `52`
- Failures: `[]`
- Row failure totals: all zero

## Smoke Result

The latest backend smoke verifies:

- Default backend remains `UNREAL_ASSETS`.
- Runtime switch reaches `UNREAL_ASSETS` and `SEMANTIC_PROXY`.
- Invalid descriptor JSON does not mutate the existing proxy.
- Mismatched `descriptor_id` update packets are rejected.
- Full descriptor ingestion creates the expected part count.
- `shape_param_update` no longer applies actor root scale. Packets that only provide a new global `scale.dims_m` are rejected.
- Accepted `shape_param_update` packets must provide replacement part parameters so vehicle cab/wheel/body roles are updated independently.

## Benchmark Summary

Per-object p50/p95 timings in milliseconds:

| Method | Components at 500 | Create p50 | Create p95 | Pose update p50 | Pose update p95 | Shape update p50 | Shape update p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_render | 0 | 0.0029 | 0.0034 | 0.00009 | 0.00012 | 0.00000 | 0.00002 |
| billboard_label | 0 | 0.2915 | 0.4184 | 0.0087 | 0.0102 | 0.00012 | 0.00026 |
| box_proxy | 500 | 0.3619 | 0.4619 | 0.0120 | 0.0128 | 0.0091 | 0.0102 |
| ellipsoid_proxy | 500 | 0.3456 | 0.4518 | 0.0087 | 0.0094 | 0.0054 | 0.0065 |
| legacy_semantic_proxy | 2180 | 0.6110 | 0.8250 | 0.0149 | 0.0195 | 0.0135 | 0.0216 |
| sppa_desc | 2680 | 0.9689 | 3.9896 | 0.0287 | 0.0503 | 0.0316 | 0.0502 |

All baselines reported component-count reuse and component-name reuse during pose and shape updates in all rows. The SPPA create-time p95 is much higher than its median in this run, so these numbers should be treated as preliminary Editor-Cmd timings, not latency guarantees.

## Interpretation

SPPA is not faster than trivial geometric baselines. Boxes and ellipsoids are faster and create fewer components. The defensible contribution is narrower: SPPA provides a richer semantic part actor at bounded local actor-level cost, and updates pose/shape without rebuilding components in this microbenchmark.

Allowed claim:

- In this Editor-Cmd actor microbenchmark, descriptor-driven SPPA created richer part proxies at about 0.97 ms per object p50 and applied pose/shape updates at about 0.03 ms per object p50 without component reconstruction. The p95 create time was about 3.99 ms and must not be hidden.

Forbidden claims:

- Do not claim VR FPS, GPU frame-time, draw-call scalability, packaged performance, `/api/ui/data` replay performance, pilot readability, safety, or bandwidth advantage from this benchmark.
