# SPPA Scale Variant Benchmark

Synthetic dimension variants. `sppa_global_scaled` is the trivial baseline that scales every part. `sppa_parametric` uses evidence-calibrated part layout for supported vehicle archetypes. This is not silhouette or user-recognition evidence.

## All Archetypes

| Method | n variants | median dim error | median build ms | triangle range |
|---|---:|---:|---:|---:|
| sppa_fixed | 12 | 0.3350 | 0.2941 | 488-1668 |
| sppa_global_scaled | 12 | 0.0000 | 0.4619 | 488-1668 |
| sppa_parametric | 12 | 0.2170 | 0.2928 | 488-1692 |
| box | 12 | 0.0000 | 0.0045 | 12-12 |

## Supported Vehicle Archetypes Only

| Method | n variants | median dim error | median build ms | triangle range |
|---|---:|---:|---:|---:|
| sppa_fixed | 4 | 0.3926 | 0.4201 | 864-1668 |
| sppa_global_scaled | 4 | 0.0000 | 0.6401 | 864-1668 |
| sppa_parametric | 4 | 0.0223 | 0.3448 | 864-1692 |
| box | 4 | 0.0000 | 0.0045 | 12-12 |
