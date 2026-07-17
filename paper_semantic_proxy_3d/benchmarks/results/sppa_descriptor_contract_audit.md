# SPPA Descriptor Contract Audit

This validates SPPA-DESC-0.2 required fields plus conditional descriptor-contract fields. When visual_metric_yaw_consistency is declared as an evidence source, the descriptor must record the projected visual-axis gate and select projected_footprint_yaw_gate as an ambiguous axial yaw in the declared replay frame.

- Status: passed
- Rows: 4
- Failed rows: 0
- Visual-metric contract rows: 4
- Max descriptor bytes: 32253
- Failures: none

| Case | Schema errors | Visual-metric gate | Pose yaw source | Frame | Bytes |
|---|---:|---|---|---|---:|
| biker | 0 | aligned | projected_footprint_yaw_gate | declared_assumed_flight_replay_local_ned | 31622 |
| tower | 0 | aligned | projected_footprint_yaw_gate | declared_assumed_flight_replay_local_ned | 30863 |
| tractor | 0 | weakly_aligned | projected_footprint_yaw_gate | declared_assumed_flight_replay_local_ned | 32202 |
| tractor_trailer | 0 | weakly_aligned | projected_footprint_yaw_gate | declared_assumed_flight_replay_local_ned | 32253 |
