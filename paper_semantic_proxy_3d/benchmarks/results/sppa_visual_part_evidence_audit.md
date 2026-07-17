# SPPA Visual Part Evidence Audit

Visual part evidence is role-conditioned support from generic image-space cues. It can annotate existing SPPA roles in the descriptor and add low-cost conditioning primitives to those existing roles, but it cannot introduce new classes, replace the semantic normalizer, or claim ground-truth part segmentation. The associated geometry profile is image-space only and is recorded once per descriptor to avoid descriptor bloat.

- Status: passed
- Failures: none

| Case | Scope | Roles | Geometry profile | Visual shape | Visual yaw | Wall ms | Tris | Descriptor bytes |
|---|---|---|---|---|---|---:|---:|---:|
| biker | round_part_pair_candidate | bike_frame, vehicle_metal_or_hub, vehicle_tire | line_structure, round_pair | +20 tris | projected_footprint_yaw_gate @ 1.612 deg | 3.573 | 1056 | 31964 |
| tower | multi_line_structure_candidate | vertical_structure_metal | line_structure | +40 tris | projected_footprint_yaw_gate @ 8.622 deg | 1.270 | 436 | 31203 |
| tractor | round_part_pair_candidate | vehicle_attachment, vehicle_metal_or_hub, vehicle_tire | line_structure, round_pair | +40 tris | projected_footprint_yaw_gate @ 80.077 deg | 2.190 | 1096 | 31799 |
| tractor_trailer | multi_line_structure_candidate | container_detail, vehicle_attachment | line_structure | +24 tris | projected_footprint_yaw_gate @ 77.377 deg | 3.296 | 2012 | 32595 |
