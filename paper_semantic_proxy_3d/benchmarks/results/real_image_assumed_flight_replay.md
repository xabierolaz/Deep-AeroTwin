# Real-Image Assumed-Flight SPPA Replay

This artifact upgrades the paper evidence without mislabeling telemetry.

## Claim Boundary

Real user images and real YOLOE detector outputs are used. Flight pose, AGL, and camera mount geometry plus family height priors are declared replay assumptions, not measured telemetry. Metric SPPA pose/scale is therefore scenario-relative and must not be described as real measured flight localization.

## Summary

- Cases: 4
- Passed: 4
- Failed: 0
- Images are real: yes
- Detector evidence is real YOLOE inference: yes
- Flight telemetry is measured: no
- Height priors are measured: no
- Metric output is scenario-relative: yes

## Cases

| Case | Detector label | SPPA tag | Evidence source | Silhouette q | Dims m | World m | Status |
|---|---:|---:|---:|---:|---:|---:|---:|
| `biker` | `person + motorcycle` | `two_wheeled_rider` | `real_mask_ground_projected_oriented_footprint` | 0.908 | L=3.59, W=1.77, H=1.85 | N=-3.67, E=-1.75 | `passed` |
| `tower` | `electric pylon` | `power_tower` | `real_mask_ground_projected_oriented_footprint` | 0.902 | L=12.77, W=2.89, H=28.00 | N=-1.72, E=0.56 | `passed` |
| `tractor` | `agricultural vehicle` | `farm_vehicle` | `real_mask_ground_projected_oriented_footprint` | 0.938 | L=4.95, W=4.32, H=2.60 | N=-8.45, E=-10.96 | `passed` |
| `tractor_trailer` | `vehicle` | `generic_vehicle` | `real_mask_ground_projected_oriented_footprint` | 0.748 | L=16.85, W=6.21, H=3.40 | N=-2.38, E=-7.61 | `passed` |

## Paper Wording

We evaluate SPPA on real user-supplied UAV-style images using YOLOE detector evidence. For the metric-proxy path, we run a declared assumed-flight telemetry replay: camera pose, AGL, mount geometry, and family height priors are scenario parameters rather than measured flight logs. The silhouette column is an image-derived proxy inside the detector/reviewed bbox, not a ground-truth mask. This evaluates the SPPA projection and proxy-construction pipeline while keeping measured-flight claims separate.
