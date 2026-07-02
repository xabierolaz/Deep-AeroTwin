# SPPA Evidence-Aware Descriptor and Update Benchmark

This benchmark measures the Python SPPA-DESC/SPPA-UPD contract and deterministic scheduler.
It is not an Unreal render-thread, VR FPS, or human-subject validation benchmark.

## Environment

- GPU snapshot: `{"driver": "610.62", "memory_total_mb": 32607, "memory_used_mb": 25187, "name": "NVIDIA GeForce RTX 5090", "utilization_gpu_pct": 10}`
- Descriptor schema: `SPPA-DESC-0.2`
- Update packet schema: `SPPA-UPD-0.2`

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
| synthetic | descriptor_build_us (us) | 160 | 189.200 | 304.000 | 312.800 | 315.300 |
| synthetic | schedule_us (us) | 160 | 3.500 | 4.400 | 5.700 | 8.600 |
| synthetic | effective_create_us (us) | 20 | 241.600 | 496.600 | 498.800 | 498.800 |
| synthetic | descriptor_bytes (bytes) | 160 | 6161.000 | 8099.000 | 8100.000 | 8100.000 |
| synthetic | packet_bytes (bytes) | 160 | 924.000 | 4659.000 | 6565.000 | 6566.000 |
| replay | descriptor_build_us (us) | 80000 | 197.900 | 400.100 | 429.000 | 187969.800 |
| replay | schedule_us (us) | 80000 | 6.500 | 10.400 | 12.900 | 391.100 |
| replay | effective_create_us (us) | 232 | 434.000 | 587.900 | 762.200 | 1208.000 |
| replay | descriptor_bytes (bytes) | 80000 | 6151.000 | 6374.000 | 6378.000 | 6385.000 |
| replay | packet_bytes (bytes) | 80000 | 1026.000 | 1037.000 | 1379.000 | 5206.000 |

## Replay Scheduler Counts

| Shape threshold | Create | Pose update | Shape update | Topology regenerate | No-op |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 58 | 417 | 1786 | 0 | 17739 |
| 0.10 | 58 | 1174 | 1113 | 0 | 17655 |
| 0.20 | 58 | 2370 | 528 | 0 | 17044 |
| 0.30 | 58 | 3771 | 268 | 0 | 15903 |

## Interpretation Boundaries

- Full descriptor bytes are create/regenerate contract bytes; per-frame updates should use SPPA-UPD packet bytes.
- Metric scale is used only when explicit `dims_m` is supplied; bbox/mask-only rows remain image-space evidence.
- Mask/PCA yaw is axial modulo pi and remains ambiguous unless explicit yaw, heading, or velocity evidence exists.
- Replay rows are policy-derived from available logs, not native Unreal actor instrumentation.
- The next required artifact for operational claims is a native Unreal trace of spawn/reconfigure/transform/despawn plus frame timings.
