# Lightweight Baseline Benchmark

Measured data. This is not a user study and not an Unreal frame-time benchmark.

| Method | n classes | median build ms | p95 build ms | triangle range | mean dimension error |
|---|---:|---:|---:|---:|---:|
| billboard | 6 | 0.0007 | 0.0011 | 2-2 | 0.3333 |
| box | 6 | 0.0046 | 0.0058 | 12-12 | 0.0000 |
| capsule_proxy | 6 | 0.0585 | 0.0685 | 212-212 | 0.0081 |
| ellipsoid | 6 | 0.0372 | 0.0447 | 144-144 | 0.0000 |
| sppa_fixed | 6 | 0.2924 | 0.3563 | 488-1668 | 0.2852 |
| sppa_global_scaled | 6 | 0.4575 | 0.4963 | 488-1668 | 0.0000 |
| sppa_parametric | 6 | 0.2902 | 0.3285 | 488-1692 | 0.1589 |
