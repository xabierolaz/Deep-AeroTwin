# SPPA Detector Observation Refinement Audit

This verifies the detector-plus-observation SPPA route on the frozen real probes. It proves that weak detector labels can be refined to conservative proxy families under runtime budgets; it does not prove exact class recognition or ground-truth 3D reconstruction.

- Status: passed
- Total wall time: 10.340 ms
- Max triangles: 1848
- Max descriptor bytes: 29904
- Max mesh bytes: 43958
- Failures: none

| Case | Detector+obs semantic | Rule | Dims LxWxH | Wall ms | Tris |
|---|---|---|---:|---:|---:|
| biker | `biker` -> `biker` | `composed_person_plus_two_wheel` | 1.85 x 0.73 x 1.85 | 3.528 | 1036 |
| tower | `vertical_structure` -> `vertical_structure` | `specific_power_infrastructure_label` | 5.60 x 2.89 x 28.00 | 1.372 | 270 |
| tractor | `farm_vehicle` -> `farm_vehicle` | `farm_vehicle_label` | 4.52 x 2.38 x 2.60 | 2.477 | 936 |
| tractor_trailer | `articulated_vehicle` -> `articulated_vehicle` | `metric_long_footprint_articulated_proxy` | 13.98 x 3.54 x 3.40 | 2.963 | 1848 |
