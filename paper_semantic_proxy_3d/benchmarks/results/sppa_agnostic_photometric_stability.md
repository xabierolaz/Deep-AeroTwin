# SPPA Agnostic Photometric Stability Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Variant image dir: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_agnostic_shape_fitting\20260704_photometric_stability\variant_inputs`
- Rows checked: 4
- Variants checked: 16
- Failures: 0
- Audit warnings: 15

| Case | Variant | Status | Scope -> variant | Strong pairs -> variant | Edge density -> variant | Lines -> variant | Warnings |
|---|---|---|---|---:|---:|---:|---:|
| biker | dark_low_contrast | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 0.11424 -> 0.09435 | 16 -> 16 | 0 |
| biker | bright_high_contrast | pass | round_part_pair_candidate -> weak_round_pair_candidate | 3 -> 0 | 0.11424 -> 0.1222 | 16 -> 16 | 3 |
| biker | soft_blur | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 0.11424 -> 0.08871 | 16 -> 16 | 0 |
| biker | mild_sensor_noise | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 0.11424 -> 0.13596 | 16 -> 16 | 1 |
| tower | dark_low_contrast | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.23511 -> 0.19645 | 16 -> 16 | 1 |
| tower | bright_high_contrast | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.23511 -> 0.27638 | 16 -> 16 | 0 |
| tower | soft_blur | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.23511 -> 0.08403 | 16 -> 16 | 1 |
| tower | mild_sensor_noise | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.23511 -> 0.24444 | 16 -> 16 | 0 |
| tractor | dark_low_contrast | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 2 | 0.28921 -> 0.2732 | 16 -> 16 | 2 |
| tractor | bright_high_contrast | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 2 | 0.28921 -> 0.29392 | 16 -> 16 | 2 |
| tractor | soft_blur | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 0.28921 -> 0.2487 | 16 -> 16 | 0 |
| tractor | mild_sensor_noise | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 0.28921 -> 0.28545 | 16 -> 16 | 0 |
| tractor_trailer | dark_low_contrast | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.21675 -> 0.18139 | 16 -> 16 | 1 |
| tractor_trailer | bright_high_contrast | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.21675 -> 0.22851 | 16 -> 16 | 1 |
| tractor_trailer | soft_blur | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.21675 -> 0.11677 | 16 -> 16 | 2 |
| tractor_trailer | mild_sensor_noise | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0.21675 -> 0.23744 | 16 -> 16 | 1 |

## Interpretation

This verifier applies deterministic photometric perturbations to each real input image while keeping bbox and unlabeled detector masks unchanged. A pass means the primary agnostic primitive decision is stable under brightness, contrast, blur, and mild sensor-noise changes for the frozen replay. Audit warnings record secondary edge, line, or weak-pair drift; this is not a real-world illumination benchmark.

## Audit Warnings

- biker: bright_high_contrast: image cue confidence changed round_part_pair_candidate -> weak_round_pair_candidate
- biker: bright_high_contrast: strong round pair count changed 3 -> 0
- biker: bright_high_contrast: all round-pair count changed 3 -> 2
- biker: mild_sensor_noise: all round-pair count changed 3 -> 4
- tower: dark_low_contrast: all round-pair count changed 0 -> 1
- tower: soft_blur: edge density changed 0.23511 -> 0.08403
- tractor: dark_low_contrast: strong round pair count changed 3 -> 2
- tractor: dark_low_contrast: all round-pair count changed 3 -> 2
- tractor: bright_high_contrast: strong round pair count changed 3 -> 2
- tractor: bright_high_contrast: all round-pair count changed 3 -> 2
- tractor_trailer: dark_low_contrast: all round-pair count changed 0 -> 2
- tractor_trailer: bright_high_contrast: all round-pair count changed 0 -> 1
- tractor_trailer: soft_blur: edge density changed 0.21675 -> 0.11677
- tractor_trailer: soft_blur: all round-pair count changed 0 -> 2
- tractor_trailer: mild_sensor_noise: all round-pair count changed 0 -> 2
