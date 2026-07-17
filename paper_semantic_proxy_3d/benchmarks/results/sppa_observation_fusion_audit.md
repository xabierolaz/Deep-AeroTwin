# SPPA Observation Fusion Audit

Real-input SPPA observation-fusion audit. It verifies deterministic constraint fusion over detector-derived replay dimensions; it does not prove ground-truth 3D reconstruction or detector mask correctness.

- Status: passed
- Run: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_sota_benchmark\runs\20260704_real_all_sppa_unified`
- Failures: none

| Case | Raw dims LxWxH | SPPA dims LxWxH | Raw aspect | SPPA aspect | Gate | Pose used | Wall ms | Tris |
|---|---:|---:|---:|---:|---|---|---:|---:|
| biker | 3.59 x 1.77 x 1.85 | 1.85 x 0.73 x 1.85 | 2.020 | 2.547 | soft low-conf fusion | no | 3.390 | 1036 |
| tower | 12.77 x 2.89 x 28.00 | 5.60 x 2.89 x 28.00 | 4.421 | 1.939 | height-only fusion | no | 1.151 | 270 |
| tractor | 4.95 x 4.32 x 2.60 | 4.52 x 2.38 x 2.60 | 1.144 | 1.900 | soft aspect fusion | no | 1.784 | 880 |
| tractor_trailer | 16.85 x 6.21 x 3.40 | 12.11 x 3.76 x 3.40 | 2.714 | 3.224 | soft low-conf fusion | no | 2.902 | 1904 |
