# SPPA-MVFit development summary

Synthetic development split only. This is not the held-out confirmatory result.

| Method | n | Mean voxel IoU | Median voxel IoU | Mean BEV IoU | Median single call ms |
|---|---:|---:|---:|---:|---:|
| sppa_mvfit | 144 | 0.5498 | 0.5700 | 0.7442 | 10.436 |
| generic_mvfit | 144 | 0.3428 | 0.3839 | 0.6461 | 12.111 |
| sppa_text_only | 144 | 0.4121 | 0.4496 | 0.6993 | 0.967 |
| bbox | 144 | 0.2198 | 0.1950 | 0.5333 | 0.302 |
| ellipsoid | 144 | 0.3015 | 0.3078 | 0.6164 | 0.615 |
| capsule | 144 | 0.2828 | 0.2680 | 0.5753 | 1.086 |
| billboard | 144 | 0.1649 | 0.1432 | 0.7505 | 0.320 |
| nonsemantic_visual_hull | 144 | 0.4844 | 0.5150 | 0.7535 | 0.334 |

Development paired SPPA-MVFit minus generic-MVFit clean voxel IoU:
mean 0.2070, percentile 95% CI [0.1920, 0.2226], n=144.

This interval must not be reported as H1 evidence. No test seed, test GT, or test result exists in this package snapshot.
