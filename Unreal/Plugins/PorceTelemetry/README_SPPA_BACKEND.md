# PORCE Twin SPPA Backend

`UPorceTelemetryComponent` now supports two interchangeable spawn backends that consume the same `/api/ui/data` obstacle input:

- `UnrealAssets`: current behavior. The component spawns `BikerActorClass`, `CowActorClass`, `TowerActorClass`, or `DefaultObstacleActorClass`.
- `SemanticProxy`: SPPA-style generated 3D proxies using runtime primitive components. The default class is `APorceSemanticProxyActor`, or a custom Blueprint can be assigned to `SemanticProxyActorClass`. If the obstacle includes an optional `SPPA-DESC-0.2` descriptor, the proxy actor builds its primitive parts from the descriptor `parts[]`; otherwise it falls back to the legacy class/confidence template path.

The default backend is `UnrealAssets`, so existing scenes keep their current behavior unless changed.

## Runtime Switch

If `bShowSpawnBackendSwitchUI` is enabled on the `UPorceTelemetryComponent`, Play/PIE shows a viewport button:

```text
PORCE Twin: Unreal Assets
PORCE Twin: SPPA Proxy
```

Clicking it calls `ToggleSpawnBackend()`. Only actors managed by this telemetry component are destroyed and respawned. Existing placed actors, maps, Cesium setup, and configured asset classes are not modified.

If an existing `entity_id` changes canonical class, the asset backend respawns the managed actor with the matching configured class. The SPPA backend keeps the same proxy actor and reconfigures its generated primitive parts.

## Blueprint / Details API

Useful properties and functions:

- `SpawnBackend`: `UnrealAssets` or `SemanticProxy`.
- `SemanticProxyActorClass`: optional custom proxy actor class.
- `bShowSpawnBackendSwitchUI`: enables the viewport button.
- `SetSpawnBackend(NewBackend)`: explicit backend selection.
- `ToggleSpawnBackend()`: switch between both modes.
- `GetSpawnBackend()`: inspect current mode.
- `IsUsingSemanticProxyBackend()`: convenience boolean for UI.
- `ApplyObstacleBatchJson(PayloadJson)`: debug/test entry point that applies a JSON object with the same `obstacles[]` shape used by `/api/ui/data` without running HTTP polling.
- `PollNowBlockingForTest(TimeoutS)`: debug/test entry point that starts one HTTP poll and blocks the calling test script until the Unreal HTTP module reports completion or timeout. Normal runtime polling remains asynchronous.
- `bBenchmarkDisableActorSpawning`: debug/test flag used by benchmarks to parse HTTP payloads and update entity state without spawning actors. It is not an operational spawn backend and should remain disabled in normal use.

## Environment Override

The backend can be selected before Play with:

```powershell
$env:PORCE_UNREAL_TWIN_SPAWN_BACKEND = "sppa"
```

Accepted SPPA values: `sppa`, `semantic_proxy`, `semantic-proxy`, `proxy`, `generated`.
Any other non-empty value selects `UnrealAssets`.

Optional custom proxy actor class:

```powershell
$env:PORCE_UNREAL_TWIN_SPPA_ACTOR_CLASS = "/Game/Path/BP_MyProxy.BP_MyProxy_C"
```

## Shared Input Contract

Both backends consume the existing obstacle fields already used by the Unreal telemetry consumer:

- Identity: `entity_id`, `object_id`, or numeric `id`.
- Class: `object_type` or `type`.
- Position: `world_m.{north,east,up}`, flat `world_north_m/world_east_m/world_up_m`, or `lat/lon`.
- Confidence: `confidence`.
- Optional heading: `yaw_deg`, `heading_deg`, `azimuth_deg`, `yaw_rad`, or `heading_rad`.

SPPA does not introduce a new endpoint. It is a rendering/backend layer behind the current AeroTwin telemetry path.

Optional SPPA fields on each obstacle:

- `sppa_descriptor`: embedded `SPPA-DESC-0.2` JSON object.
- `sppa_descriptor_json`: string-serialized `SPPA-DESC-0.2` object.
- `sppa_update_packet`: embedded `SPPA-UPD-0.2` JSON object.
- `sppa_update_packet_json`: string-serialized `SPPA-UPD-0.2` object.

The asset backend ignores these fields. The semantic-proxy backend attempts a newly arrived update packet first, then descriptor ingestion, then falls back to `ConfigureProxy(ClassName, Confidence, bConfirmed)`. Descriptor positions and dimensions are interpreted in meters and converted to Unreal centimeters inside `APorceSemanticProxyActor`. Descriptor primitives supported natively are `box`, `sphere`, `cylinder`, and `cone`; `torus` is rendered as a low-cost cylinder/disc approximation to preserve part count and runtime simplicity.

Current implementation status:

- Implemented: optional descriptor-driven actor construction from `parts[]`, material/evidence/uncertainty component tags, invalid-descriptor rejection without mutating the current proxy in direct actor calls, descriptor reconfiguration, `ApplyProxyUpdatePacketJson` acceptance for pose-update/no-op/shape-update packets on an existing descriptor proxy, descriptor-id mismatch rejection for pose-update packets, and shape scaling from explicit `scale.dims_m` or reference dimensions inferred from generated parts.
- Implemented: descriptor resolver/source/uncertainty tags on the semantic proxy actor, including resolver match type, resolver source, scale source, material source, fallback/unknown, yaw ambiguity, and low-confidence shape tags.
- Implemented as preliminary evidence only: direct component payload replay, local-loopback HTTP polling replay using the `/api/ui/data` obstacle payload shape, and an opt-in packaged internal render benchmark using a dedicated `/Game/SPPABenchmark` map.
- Pending: live telemetry server replay, packaged VR/headset benchmark, native per-part pooling/reuse, real curated-asset comparison, GPU-profiler counters, and operator readability validation.

## Verification

Run the Unreal reflection/generation smoke after C++ changes to this plugin:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1
```

The check verifies that the `UPorceTelemetryComponent` backend API, default asset-backed mode, `/api/ui/data` endpoint default, the SPPA actor, and the backend enum are exposed to Unreal reflection/Python. It creates a transient telemetry component and checks `SetSpawnBackend()` / `ToggleSpawnBackend()` state transitions. It also spawns `APorceSemanticProxyActor`, calls `ConfigureProxy()` for bike/cow/tower/unknown classes, calls `ConfigureProxyFromDescriptorJson()` with a real `SPPA-DESC-0.2` fixture, and checks generated primitive component counts, tags, invalid-descriptor rejection, descriptor reconfiguration, and collision state.

If Unreal 5.7 is not installed under the usual Epic Games paths, set:

```powershell
$env:PORCE_UNREAL_ENGINE_ROOT = "D:\Path\To\UE_5.7"
```

The full zero-trust audit also runs this smoke by default:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\audit_zero_trust_e2e.ps1
```

## Actor Microbenchmark

Run the preliminary Unreal Editor-Cmd actor benchmark with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_unreal_backend.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5
```

The benchmark compares `no_render`, `billboard_label`, `box_proxy`, `ellipsoid_proxy`, `legacy_semantic_proxy`, and descriptor-driven `sppa_desc`. The 2026-07-02 run is stored under `experiments/sppa_unreal_backend/20260702T084924Z_editor_actor_microbenchmark`.

Important limitation: this benchmark measures direct transient actor operations in Unreal Editor-Cmd. It is not a packaged build benchmark, not a `/api/ui/data` replay, not render-thread or GPU timing, and not VR FPS evidence.

## Component Payload Replay

Run the preliminary component lifecycle replay with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_component_replay.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5
```

The 2026-07-02 run is stored under `experiments/sppa_unreal_component_replay/20260702T085905Z_component_payload_replay`.

Important limitation: this replay uses the same `obstacles[]` payload shape as `/api/ui/data`, but it bypasses HTTP and uses `StaticMeshActor` placeholders for the asset backend. It is not a final curated-asset, packaged-build, render-thread, GPU, draw-call, or VR benchmark. The run uses ten repetitions per scene size, does not separate cold/warm cache behavior, and reports descriptive p50/p95 values rather than operational latency guarantees.

## HTTP Poll Replay

Run the preliminary HTTP polling replay with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_http_poll_replay.ps1 -Counts "10,50,100,250,500" -Repetitions 10 -UpdatesPerActor 5 -Seed 20260702
```

The 2026-07-02 valid run with generated batch-summary, paired-delta, schedule, order-trace, runtime update trace, and the `NoRender` debug baseline is stored under `experiments/sppa_unreal_http_poll_replay/20260702T101020Z_http_poll_replay`.

This replay starts a local loopback HTTP server inside the Unreal Python script, points `UPorceTelemetryComponent` at `/api/ui/data`, and uses `PollNowBlockingForTest()` to wait for each Unreal HTTP-module response. It loaded 52 descriptor fixtures, issued 1050 HTTP GET requests across `NoRender`, `UnrealAssets`, and `SemanticProxy`, and reported no request/parsing failures. The run used seed `20260702` with counterbalanced backend order within each count/repetition group; the exact planned and executed orders are stored in `http_poll_replay_schedule.jsonl` and `http_poll_replay_order_trace.csv`. Runtime update instrumentation is stored in `sppa_runtime_update_trace.csv`, `sppa_runtime_update_trace.jsonl`, and `sppa_runtime_update_summary.json`. At 500 actors, the debug no-render baseline held 0 actors/components, the placeholder asset backend held 500 components, and the semantic-proxy backend held 2680 generated components.

Important limitation: this is still an Editor-Cmd local-loopback test. It is not a live flight-server test, not a packaged-build benchmark, not a real-network benchmark, not render-thread/GPU/draw-call timing, and not VR FPS evidence. The asset backend still uses placeholders rather than the curated project asset library.

Do not read the per-object timing summary as a frame-budget result. In the valid run, the 500-actor semantic-proxy case measured batch-level p50/p95 of 738.6/839.3 ms for the create poll, 134.0/142.3 ms for one pose-update poll, and 95.4/112.5 ms for the shape poll before render-thread or GPU work. The 500-actor no-render baseline was also nontrivial at 329.8/367.0 ms create, 87.9/104.1 ms pose poll, and 55.8/65.1 ms shape poll, so large payload parse/upsert cost is visible even without actor spawning. The paired 500-actor delta artifacts estimate the additional SPPA cost over the placeholder asset backend as 387.8 ms median create, 40.8 ms median pose poll, and 37.9 ms median shape poll, with 2180 additional components. The runtime update trace shows zero component creation and zero component destruction during SPPA pose and shape updates in this replay; it does not measure rendering cost.

## Packaged Render Benchmark

Run the packaged internal render benchmark with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\benchmark_sppa_packaged_render.ps1 -Counts "10,50,100" -Repetitions 3 -WarmupFrames 30 -MeasureFrames 120 -UpdateEveryFrames 15 -NoCsvProfile
```

The 2026-07-02 clean run is stored under `experiments/sppa_packaged_render/20260702T122743Z_packaged_render`, using the dedicated empty benchmark map `/Game/SPPABenchmark`. The run compared `no_render`, placeholder `unreal_assets`, and `semantic_proxy` backends inside a packaged `AirTraffic.exe`, with no benchmark failures and no `api/state/latest` polling in the benchmark log.

Important limitation: this is an internal synthetic replay in a packaged executable. It is not live HTTP/network telemetry, not YOLO detector output, not VR/headset validation, not a curated-asset comparison, and not GPU-profiler evidence. The runner reports Tick delta frame time plus estimated triangles/draw calls from static mesh components. Unreal CSV profiler was smoke-tested but produced a zero-byte profiler CSV on immediate process exit, so those profiler files are not used as evidence.
