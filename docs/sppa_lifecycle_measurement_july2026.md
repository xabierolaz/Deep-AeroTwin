# SPPA Lifecycle Measurement, July 2026

This note records the objective measurements currently available for the SPPA
track-persistent runtime argument.

Artifacts:

- Report: `experiments/sppa_lifecycle_measurement/multi_sequence_20260701/sppa_lifecycle_report.md`
- JSON: `experiments/sppa_lifecycle_measurement/multi_sequence_20260701/sppa_lifecycle_report.json`
- Lifecycle events: `experiments/sppa_lifecycle_measurement/multi_sequence_20260701/policy_lifecycle_events.csv`
- Source-log audit: `experiments/sppa_lifecycle_measurement/multi_sequence_20260701/source_logs.csv`
- Script: `tools/sppa_sota_benchmark/measure_sppa_lifecycle.py`

## What Was Measured

Measured directly:

- In-memory SPPA procedural template construction in Python.
- Debug OBJ/MTL export from the current file-based prototype path.
- Offline policy/state update cost while replaying recorded obstacle-track
  samples.

Derived from logs:

- First recorded observation of a track -> `create`.
- Stable class/archetype observation -> `pose_update`.
- Bounding-box shape change >= 20% -> `shape_param_update`.
- Class/archetype change -> `regenerate_topology`.

Not measured yet:

- Native Unreal actor spawn cost.
- Native Unreal actor transform/update cost per frame.
- Render-thread/GPU frame-time impact.
- Native SPPA runtime create/update/reconfigure/despawn events.

## Current Results

| Metric | n | P50 | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|
| In-memory proxy creation | 60,000 | 177.2 us | 403.7 us | 663.5 us | 5,250.7 us |
| Debug OBJ/MTL export path | 600 | 1,076.3 us | 1,521.8 us | 1,745.4 us | 2,619.1 us |
| Policy/state update per track observation | 436,652 | 0.4 us | 0.8 us | 1.3 us | 122.9 us |

Lifecycle replay over seven available controller logs:

| Event type | Count |
|---|---:|
| Creates | 5,546 |
| Pose/confidence updates | 410,766 |
| Shape/scale parameter updates | 20,340 |
| Topology regenerations | 0 |

The zero topology-regeneration count is not a universal claim. It means no
class/archetype changes were observed in the recorded samples under this policy.
If the current file-export path had to rebuild geometry on every >=20% bbox
shape change, 20,340 would be the conservative full-rebuild upper bound.

## Honesty Constraints For The Paper

- Do not call this a final real-flight validation.
- Do not call the update number an Unreal frame-time number.
- Do not hide that several logs have truncated obstacle samples.
- Do not hide that three logs are explicitly marked `SIMULATION/AUTONOMOUS`,
  while several older logs lack workflow metadata.
- Do not hide that `tower` is implemented in the Unreal SPPA backend but missing
  from the current Python OBJ template builder used for creation timing.

The defensible claim is: current artifacts support a preliminary lifecycle
measurement showing that SPPA can amortize proxy construction over track
lifetime under a track-persistent policy. The final publication artifact still
needs native Unreal instrumentation.
