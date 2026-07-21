# Real-Image Assumed-Flight SPPA Replay

This artifact upgrades the paper evidence without mislabeling telemetry.

## Claim Boundary

Real user images and real YOLOE detector outputs are used. Flight pose, AGL, and camera mount geometry plus family height priors are declared replay assumptions, not measured telemetry. Metric SPPA pose/scale is therefore scenario-relative and must not be described as real measured flight localization.

## Summary

- Cases: 2
- Passed: 2
- Failed: 0
- Images are real: yes
- Detector evidence is real YOLOE inference: yes
- Flight telemetry is measured: no
- Height priors are measured: no
- Metric output is scenario-relative: yes

## Cases

| Case | Detector label | SPPA tag | Evidence source | Silhouette q | Dims m | World m | Status |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tower` | `electric pylon` | `power_tower` | `real_mask_ground_projected_oriented_footprint` | 0.778 | L=5.60, W=5.60, H=28.00 | N=6.63, E=-14.16 | `passed` |
| `tractor` | `two-wheeled vehicle` | `generic_vehicle` | `real_mask_ground_projected_oriented_footprint` | 0.928 | L=4.75, W=2.50, H=2.60 | N=5.49, E=-3.77 | `passed` |

## Paper Wording

We evaluate SPPA on real user-supplied UAV-style images using YOLOE detector evidence. For the metric-proxy path, we run a declared assumed-flight telemetry replay: camera pose, AGL, mount geometry, and family height priors are scenario parameters rather than measured flight logs. The silhouette column is an image-derived proxy inside the detector/reviewed bbox, not a ground-truth mask. This evaluates the SPPA projection and proxy-construction pipeline while keeping measured-flight claims separate.
