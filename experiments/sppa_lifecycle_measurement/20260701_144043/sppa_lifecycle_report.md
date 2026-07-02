# SPPA Track Lifecycle Measurement

This report separates measured CPU costs from policy-derived track events.
It is not an Unreal frame-time benchmark and it is not a native SPPA runtime trace.

## Cost Summary

| Metric | n | P50 | P95 | P99 | Max | Unit |
|---|---:|---:|---:|---:|---:|---|
| In-memory proxy creation | 60000 | 175.100 | 349.400 | 514.400 | 4181.100 | microseconds/object |
| Pose/state update decision | 7 | 0.700 | 2.100 | 2.100 | 2.100 | microseconds/track observation |

Debug OBJ/MTL export is deliberately reported separately because the intended runtime backend should keep proxies resident rather than exporting files per frame.

## Regeneration Policy Results

- Observations: 7
- Tracks: 4
- Creates: 4
- Updates: 3
- Regenerations: 0

| Source | Duration s | Tracks | Observations | Creates | Updates | Regenerations | Regen/track | Regen/min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260701_144043\real_twin\brain\events.jsonl` | 1.076 | 3 | 6 | 3 | 3 | 0 | 0.000 | 0.000 |
| `D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260701_144043\simulation\brain\events.jsonl` | 0.000 | 1 | 1 | 1 | 0 | 0 | 0.000 | 0.000 |

## Honest Interpretation

- Creation cost is measured for the current Python procedural template builder, in memory.
- Update cost is measured for policy/state update only; Unreal actor transform and render-thread cost remain pending.
- Regeneration frequency is derived from recorded `obstacle_ingest` track observations using the declared policy: first observation creates; stable class/shape observations update; class or large shape change regenerates.
- The available logs do not contain native SPPA create/update/regenerate events, so this must be described as policy-implied regeneration, not directly observed runtime regeneration.
- If a paper needs a final operational number, the next required artifact is an Unreal trace that logs semantic proxy actor create/update/reconfigure/despawn events with frame timestamps.
