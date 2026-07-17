# SPPA Visual-Metric Yaw Consistency Audit

This audit compares two independent orientation cues on real image probes: image-space visual orientation inferred from generic SPPA part/line evidence, and axial ground-footprint orientation from UAV camera projection using declared replay telemetry. It does not claim measured flight ground truth or absolute world yaw. Divergence is allowed only when explicitly declared and routed through the conservative policy.

- Status: passed
- Aligned: 1
- Weakly aligned: 0
- Divergent but declared: 3
- Projected-axis aligned: 2
- Projected-axis weakly aligned: 2
- Projected-axis divergent but declared: 0
- Descriptor-recorded rows: 4
- Max descriptor bytes: 32595
- Failures: none
- Audit warnings: ['biker:visual_metric_yaw_divergent:58.23_deg', 'tower:visual_metric_yaw_divergent:88.08_deg', 'tractor:visual_metric_yaw_divergent:50.26_deg']

| Case | Projected visual-axis yaw | Footprint yaw | Delta | Agreement | Descriptor | Policy |
|---|---:|---:|---:|---|---:|---|
| biker | 4.84 | 1.612 | 3.228 | aligned | true | projected_footprint_yaw_gate |
| tower | 13.254 | 8.622 | 4.632 | aligned | true | projected_footprint_yaw_gate |
| tractor | 108.333 | 80.077 | 28.256 | weakly_aligned | true | projected_footprint_yaw_gate |
| tractor_trailer | 49.286 | 77.377 | 28.091 | weakly_aligned | true | projected_footprint_yaw_gate |
