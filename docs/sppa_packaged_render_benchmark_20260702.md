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
- GPU profiler counters from Unreal CSV profiler.
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

- Do not present this as VR validation, live flight validation, real network validation, curated-asset comparison, GPU-profiler evidence, or pilot readability evidence.
- Do not claim SPPA is faster than the placeholder asset backend. In this run, the semantic-proxy backend is visually richer but has more components, more triangles, and higher payload application cost.

## CSV Profiler Note

A small packaged run with Unreal `csvprofile` enabled completed, but the generated profiler CSV under the packaged build was zero bytes when the process exited. Those profiler files are not used as evidence. The current validated evidence is the benchmark runner's own CSV/JSON artifacts.
