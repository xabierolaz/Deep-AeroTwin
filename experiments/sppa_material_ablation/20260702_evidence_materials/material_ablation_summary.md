# SPPA Material Ablation Benchmark

Measured data. This benchmark isolates debug-path proxy construction/export and material-manifest overhead. It is not a user study and not a dense Unreal frame-time benchmark.

| Method | n classes | median build ms | median export ms | median manifest ms | material count range | triangle range |
|---|---:|---:|---:|---:|---:|---:|
| sppa_flat | 6 | 0.4198 | 1.5197 | 0.0016 | 1-1 | 488-1668 |
| sppa_class_color | 6 | 0.3882 | 1.6377 | 0.0016 | 1-1 | 488-1668 |
| sppa_part_material | 6 | 0.4831 | 1.6662 | 0.6670 | 3-5 | 488-1668 |
| sppa_part_material_low_conf | 6 | 0.3903 | 1.8165 | 0.5902 | 3-5 | 488-1668 |
