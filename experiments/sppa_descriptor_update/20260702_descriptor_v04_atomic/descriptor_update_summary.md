# SPPA Evidence-Aware Descriptor and Update Benchmark

This benchmark measures the Python SPPA-DESC/SPPA-UPD contract and deterministic scheduler.
It is not an Unreal render-thread, VR FPS, or human-subject validation benchmark.

## Environment

- GPU snapshot: `{"driver": "610.62", "memory_total_mb": 32607, "memory_used_mb": 1590, "name": "NVIDIA GeForce RTX 5090", "utilization_gpu_pct": 16}`
- Descriptor schema: `SPPA-DESC-0.2`
- Update packet schema: `SPPA-UPD-0.2`
- Replay base observations: 20392
- Replay threshold-expanded rows: 81568
- Shape thresholds: [0.05, 0.1, 0.2, 0.3]
- Validation: 453 passed, 0 failed

## Smoke Coverage

| Kind | n | Unknown/fallback |
|---|---:|---:|
| known | 6 | 0 |
| open_keyword | 3 | 0 |
| unknown_fallback | 3 | 3 |

## Synthetic Scheduler Sensitivity

| Shape threshold | Create | Pose update | Shape update | Topology regenerate | No-op |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 4 | 21 | 5 | 1 | 9 |
| 0.10 | 4 | 23 | 3 | 1 | 9 |
| 0.20 | 4 | 25 | 1 | 1 | 9 |
| 0.30 | 4 | 25 | 1 | 1 | 9 |

## Timing Summary

| Source | Metric | n | P50 us | P95 us | P99 us | Max us |
|---|---|---:|---:|---:|---:|---:|
| synthetic | descriptor_build_with_parts_us (us) | 160 | 221.100 | 478.400 | 570.900 | 593.300 |
| synthetic | scheduler_decision_us (us) | 160 | 4.000 | 10.100 | 12.500 | 19.100 |
| synthetic | update_packet_build_us (us) | 160 | 9.700 | 56.600 | 80.300 | 94.700 |
| synthetic | create_total_python_us (us) | 20 | 513.400 | 1503.900 | 1552.900 | 1552.900 |
| synthetic | pose_update_no_mesh_us (us) | 140 | 13.700 | 28.300 | 37.300 | 90.900 |
| synthetic | descriptor_bytes (bytes) | 160 | 6262.000 | 8200.000 | 8201.000 | 8201.000 |
| synthetic | packet_bytes (bytes) | 160 | 943.000 | 4659.000 | 6584.000 | 6585.000 |
| replay | descriptor_build_with_parts_us (us) | 81568 | 316.100 | 395.000 | 433.000 | 5359.900 |
| replay | scheduler_decision_us (us) | 81568 | 6.100 | 9.900 | 12.100 | 133.100 |
| replay | update_packet_build_us (us) | 81568 | 14.900 | 21.100 | 73.500 | 139.500 |
| replay | create_total_python_us (us) | 1412 | 855.200 | 1077.100 | 1173.600 | 243353.000 |
| replay | pose_update_no_mesh_us (us) | 80156 | 21.200 | 27.800 | 32.100 | 163.800 |
| replay | descriptor_bytes (bytes) | 81568 | 6241.000 | 6477.000 | 6481.000 | 6487.000 |
| replay | packet_bytes (bytes) | 81568 | 1045.000 | 1395.000 | 4966.000 | 5210.000 |

## Replay Source Distribution

| Source log | Selected observations |
|---|---:|
| `pipeline\logs\zero_trust\20260218_234222\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260219_091623\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260219_212154\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260220_035901\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260618_124757\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260618_131747\brain\events.jsonl` | 3000 |
| `pipeline\logs\zero_trust\20260620_071403\brain\events.jsonl` | 2392 |

## Replay Scheduler Counts

| Shape threshold | Create | Pose update | Shape update | Topology regenerate | No-op |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 353 | 430 | 2106 | 0 | 17503 |
| 0.10 | 353 | 1212 | 1576 | 0 | 17251 |
| 0.20 | 353 | 2144 | 1023 | 0 | 16872 |
| 0.30 | 353 | 2993 | 738 | 0 | 16308 |

## Interpretation Boundaries

- Full descriptor bytes are create/regenerate contract bytes; per-frame updates should use SPPA-UPD packet bytes.
- Metric scale is used only when explicit `dims_m` is supplied; bbox/mask-only rows remain image-space evidence.
- Mask/PCA yaw is axial modulo pi and remains ambiguous unless explicit yaw, heading, or velocity evidence exists.
- Replay rows are policy-derived from available logs, not native Unreal actor instrumentation.
- `descriptor_build_with_parts_us` includes Python mesh/part descriptor assembly per observation; it is not a pure runtime transform update.
- `pose_update_no_mesh_us` includes scheduler decision plus update-packet construction only; Unreal transform and render-thread cost remain unmeasured.
- The next required artifact for operational claims is a native Unreal trace of spawn/reconfigure/transform/despawn plus frame timings.
