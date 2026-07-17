# SPPA Runtime Budget

SPPA runtime budget regression for the real-input single-proxy run. It guards lightweight proxy generation cost; it does not measure detector latency or Unreal frame time.

- Status: passed
- Run: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_sota_benchmark\runs\20260704_real_all_sppa_unified`
- Rows: 4
- Total wall time: 13.238 ms
- Max wall time: 3.844 ms
- Max triangles: 2012
- Max OBJ bytes: 48555
- Max descriptor bytes: 32253

## Budgets

- `max_wall_ms_per_proxy`: 10.0
- `max_build_ms_per_proxy`: 5.0
- `max_export_ms_per_proxy`: 8.0
- `max_total_wall_ms`: 50.0
- `max_triangles_per_proxy`: 2500
- `max_vertices_per_proxy`: 1500
- `max_mesh_bytes_per_proxy`: 65536
- `max_descriptor_bytes_per_proxy`: 32768

## Rows

| Model | Label | Wall ms | Build ms | Export ms | Triangles | Vertices | OBJ bytes | Descriptor bytes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sppa | biker | 3.844 | 1.344 | 2.500 | 1056 | 588 | 25559 | 31622 |
| sppa | tower | 2.649 | 0.326 | 2.323 | 436 | 256 | 10682 | 30863 |
| sppa | tractor | 3.524 | 0.924 | 2.601 | 1096 | 584 | 26439 | 32202 |
| sppa | tractor_trailer | 3.221 | 0.941 | 2.280 | 2012 | 1060 | 48555 | 32253 |

## Failures

- None
