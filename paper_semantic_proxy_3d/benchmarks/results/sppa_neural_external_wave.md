# SPPA external neural wave (Amendment 05) - measured results

Generated: 2026-07-17T12:22:37+00:00 UTC. Secondary descriptive analysis; sealed H1 unchanged.

Subset: 60 sealed held-out cases (6 families x 2 strata x 5, lexicographic).
Alignment: frozen frame convention (48-candidate signed-permutation search on 12 disjoint calibration cases, coarse 32-cubed + fine 64-cubed passes), uniform scale to GT bbox, GT bbox center, GT yaw frame.
Metrics: voxel IoU at 64-cubed (sealed voxelizer/grid), triangles, warm generation ms (model load excluded), peak CUDA VRAM, payload bytes.

| Method | Input | IoU mean | dIoU vs SPPA | Triangles | Gen ms | VRAM MB | Payload B |
|---|---|---:|---:|---:|---:|---:|---:|
| SPPA-MVFit (ours) | top+side 96x96 telemetry masks | 0.561 | 0.000 | 536 | 9.2 | -- | 1,450 |
| Generic-MVFit (context) | same masks | 0.364 | -0.197 | 1,280 | 11.4 | -- | 1,433 |
| Visual hull (context) | same masks | 0.516 | -0.045 | 51,432 | 0.2 | -- | 32,768 |
| TripoSR (a) | clean-crop shaded render | 0.128 | -0.433 | 28,145 | 384.1 | 1,869 | 1,468,998 |
| TripoSR (b) | 96x96 top mask | 0.231 | -0.331 | 46,053 | 379.4 | 1,870 | 2,454,199 |
| Hunyuan3D-2mini-turbo (a) | clean-crop shaded render | 0.157 | -0.403 | 686,733 | 1350.9 | 4,591 | 10,513,018 |
| Hunyuan3D-2mini-turbo (b) | 96x96 top mask | 0.171 | -0.390 | 3,089,274 | 1915.5 | 4,747 | 46,494,183 |

## Hard-crash exclusions (reported, not silently dropped)

- hunyuan3d_2mini_turbo/oblique: test-csg_id-quadruped-004 - RuntimeError: pipeline returned no mesh
- hunyuan3d_2mini_turbo/oblique: test-implicit_ood-quadruped-003 - RuntimeError: pipeline returned no mesh

## Method-level exclusions (environment)

- SF3D (Stable Fast 3D): install failed on Python 3.12 / torch 2.10 / CUDA 12.9 (gpytoolbox, texture_baker build); documented in runs/20260701_195624/sf3d_timeout_note.md
- SPAR3D: gated model weights; access not granted; documented in runs/20260701_195624/spar3d_access_note.md
- TRELLIS.2: no working Windows environment in this repo (setup.sh is Linux-only); not installed

## Stratum breakdown (mean IoU)

| Method/condition | CSG-ID | implicit-OOD |
|---|---:|---:|
| hunyuan3d_2mini_turbo/mask | 0.164 | 0.178 |
| hunyuan3d_2mini_turbo/oblique | 0.145 | 0.169 |
| triposr/mask | 0.218 | 0.243 |
| triposr/oblique | 0.126 | 0.131 |

## Honesty boundaries (Amendment 05 E7)

- Condition (a) gives neural generators richer input (clean shaded RGB) than the telemetry
  masks SPPA consumes; condition (b) gives them input they were not trained for.
  Neither is a leaderboard; the table measures an operating point (IoU vs triangles / ms / VRAM / payload).
- Photoreal asset quality remains neural territory and is not claimed.
- A visual beauty ranking against SOTA generators remains prohibited by the claim-evidence matrix.
- SPPA-MVFit rows are the existing sealed clean-condition results on the same 60 cases (read-only).
