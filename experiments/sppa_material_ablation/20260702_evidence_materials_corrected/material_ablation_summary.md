# SPPA Material Ablation Benchmark

Measured data. This benchmark isolates debug-path proxy construction/export and material-manifest overhead. It is not a user study, not a perceptual-discriminability test, and not a dense Unreal frame-time benchmark.
All build, export, and manifest timings are repeated per class/method; the table reports medians across the six class-level medians, with P95 shown the same way.

| Method | n classes | reps/class | build p50 ms | build p95 ms | export p50 ms | export p95 ms | manifest p50 ms | manifest p95 ms | materials | triangles |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sppa_flat | 6 | 50 | 0.3562 | 0.4139 | 0.8047 | 0.9000 | 0.0007 | 0.0009 | 1-1 | 488-1668 |
| sppa_class_color | 6 | 50 | 0.3569 | 0.3784 | 0.8019 | 0.8864 | 0.0006 | 0.0008 | 1-1 | 488-1668 |
| sppa_part_material | 6 | 50 | 0.3566 | 0.4167 | 0.8073 | 0.8760 | 0.2311 | 0.2749 | 3-5 | 488-1668 |
| sppa_part_material_metadata_low_conf | 6 | 50 | 0.3568 | 0.4155 | 0.8071 | 0.8810 | 0.2284 | 0.2631 | 3-5 | 488-1668 |

Not measured: Unreal frame time, draw calls, material-instance cost, dense-scene scaling, and user recognition/workload.
