# SPPA Descriptor/Update Contract Cycle - 2026-07-02

## What changed

- Added `SPPA-DESC-0.2` to `XYT-xabi-yolo-telemetry/xyt_generate_3d.py`.
- Added `SPPA-UPD-0.2` compact runtime update packets.
- Descriptor fields now include label/archetype resolution, bbox/mask/world-pose evidence, yaw source/modulo/ambiguity, scale source, primitive parts, mesh counts, cost fields, and scheduler thresholds.
- Added deterministic scheduler actions: `create`, `pose_update`, `shape_param_update`, `regenerate_topology`, `drop_low_confidence`, and `no_op`.
- Updated `tools/sppa_sota_benchmark/run_sppa_batch.py` to emit descriptors beside OBJ/MTL/material manifests.
- Added `tools/sppa_sota_benchmark/run_descriptor_update_benchmark.py`.
- Added JSON contract checks through `sppa_descriptor_schema_v02.json`, `sppa_update_packet_schema_v02.json`, and `validate_sppa_contract.py`.
- Added optional Unreal ingestion through `APorceSemanticProxyActor::ConfigureProxyFromDescriptorJson`.
- Extended the `/api/ui/data` obstacle path with optional `sppa_descriptor`, `sppa_descriptor_json`, `sppa_update_packet`, and `sppa_update_packet_json` fields. The `UnrealAssets` backend ignores them; the `SemanticProxy` backend applies a newly arrived update packet first, then consumes a descriptor when present, and falls back to the class/confidence template path otherwise.

## Unreal smoke command

```powershell
rtk proxy powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1
```

## Unreal smoke result

- `AirTrafficEditor Win64 Development` built successfully with Unreal Engine 5.7.
- The reflection smoke passed and wrote `pipeline/logs/sppa_backend_verify_latest.json`.
- A real `SPPA-DESC-0.2` fixture, `sppa-8d4e38132a285493`, was ingested by Unreal.
- Expected descriptor parts: 12; generated Unreal static-mesh components: 12.
- Component tags included material role, evidence source, and uncertainty style tags.
- Invalid JSON was rejected without changing the current proxy part count.
- Descriptor reconfiguration changed the proxy to one part when given a one-part descriptor.
- `ApplyProxyUpdatePacketJson` accepted a matching `pose_update` packet for an existing descriptor proxy without changing topology.
- A mismatched `pose_update` packet with the wrong `descriptor_id` was rejected without changing topology.

## Benchmark command

```powershell
rtk proxy python tools\sppa_sota_benchmark\run_descriptor_update_benchmark.py --out-dir experiments\sppa_descriptor_update\20260702_descriptor_v04_atomic --max-replay-observations-per-log 3000 --events pipeline\logs\zero_trust\20260219_212154\brain\events.jsonl pipeline\logs\zero_trust\20260618_124757\brain\events.jsonl pipeline\logs\zero_trust\20260220_035901\brain\events.jsonl pipeline\logs\zero_trust\20260219_091623\brain\events.jsonl pipeline\logs\zero_trust\20260618_131747\brain\events.jsonl pipeline\logs\zero_trust\20260218_234222\brain\events.jsonl pipeline\logs\zero_trust\20260620_071403\brain\events.jsonl
```

## Key results

- Smoke coverage: 6 known labels, 3 keyword/open labels, 3 unsupported labels; unsupported labels produced explicit unknown fallback descriptors.
- Atomic output directory includes `run_manifest.json`, CSV rows, descriptor samples, update-packet samples, validation outputs, and Markdown/JSON summaries.
- Contract validation: 453 sampled descriptors/packets passed, 0 failed in the benchmark's built-in validation.
- Replay sampling: 20,392 base observations from seven logs, capped at 3,000 per log except the smallest log with 2,392 observations; 81,568 threshold-expanded rows.
- Synthetic descriptor build with parts: P50 221.1 us, P95 478.4 us.
- Synthetic scheduler decision: P50 4.0 us, P95 10.1 us.
- Synthetic update-packet build: P50 9.7 us, P95 56.6 us.
- Replay descriptor build with parts: P50 316.1 us, P95 395.0 us.
- Replay scheduler decision: P50 6.1 us, P95 9.9 us.
- Replay update-packet build: P50 14.9 us, P95 21.1 us.
- Replay pose/no-op update without mesh rebuild: P50 21.2 us, P95 27.8 us.
- Full descriptor JSON size: roughly 6.3-8.2 kB in synthetic rows.
- Replay update packet size: P50 1,045 B, P95 1,395 B.

## Honest limits

- This is a Python contract/scheduler benchmark, not Unreal frame-time evidence.
- Unreal descriptor/update ingestion is now smoke-tested, but not benchmarked in packaged or dense-scene runtime.
- The replay is policy-derived from controller logs; it is not native SPPA actor instrumentation.
- Metric scale is only used when explicit `dims_m` is supplied.
- Mask/PCA yaw remains axial modulo pi and ambiguous unless explicit yaw, heading, or velocity exists.
- This does not prove bandwidth savings; it only measures serialized JSON descriptor/update sizes.
- GPU state is recorded in the manifest but the benchmark is CPU/Python contract work; it is not treated as a GPU performance measurement.
