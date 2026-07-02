# SPPA Track Lifecycle Measurement

This report separates measured CPU costs from policy-derived track events.
It is not an Unreal frame-time benchmark and it is not a native SPPA runtime trace.

## Cost Summary

| Metric | n | P50 | P95 | P99 | Max | Unit |
|---|---:|---:|---:|---:|---:|---|
| In-memory proxy creation | 60000 | 177.200 | 403.700 | 663.500 | 5250.700 | microseconds/object |
| Pose/state update decision | 436652 | 0.400 | 0.800 | 1.300 | 122.900 | microseconds/track observation |

Debug OBJ/MTL export is deliberately reported separately because the intended runtime backend should keep proxies resident rather than exporting files per frame.

## Regeneration Policy Results

- Observations: 436652
- Tracks: 5546
- Creates: 5546
- Pose/confidence updates: 410766
- Shape/scale parameter updates: 20340
- Topology regenerations: 0
- Conservative full-rebuild upper bound if the proxy were not parametric: 20340

| Source | Duration s | Tracks | Observations | Creates | Pose updates | Shape updates | Topology regens | Topology regen/track | Topology regen/min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pipeline\logs\zero_trust\20260218_234222\brain\events.jsonl` | 259.808 | 93 | 46860 | 93 | 45977 | 790 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260219_091623\brain\events.jsonl` | 1462.013 | 117 | 76417 | 117 | 75279 | 1021 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260219_212154\brain\events.jsonl` | 717.570 | 303 | 83344 | 303 | 82849 | 192 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260220_035901\brain\events.jsonl` | 550.516 | 1803 | 78869 | 1803 | 76119 | 947 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260618_124757\brain\events.jsonl` | 578.416 | 1534 | 80002 | 1534 | 69377 | 9091 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260618_131747\brain\events.jsonl` | 452.066 | 1654 | 68768 | 1654 | 58873 | 8241 | 0 | 0.000 | 0.000 |
| `pipeline\logs\zero_trust\20260620_071403\brain\events.jsonl` | 254.798 | 42 | 2392 | 42 | 2292 | 58 | 0 | 0.000 | 0.000 |

## Honest Interpretation

- Creation cost is measured for the current Python procedural template builder, in memory.
- Update cost is measured for policy/state update only; Unreal actor transform and render-thread cost remain pending.
- Regeneration frequency is derived from recorded `obstacle_ingest` track observations using the declared policy: first observation creates; stable observations update; bbox-scale changes are counted as parametric shape updates; class changes are counted as topology regeneration.
- The available logs do not contain native SPPA create/update/regenerate events, so this must be described as policy-implied regeneration, not directly observed runtime regeneration.
- Some source logs report truncated obstacle samples; lifecycle counts are therefore based on recorded samples, while `source_logs.csv` records active-count sums where available.
- If a paper needs a final operational number, the next required artifact is an Unreal trace that logs semantic proxy actor create/update/reconfigure/despawn events with frame timestamps.
