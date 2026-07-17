# SPPA Agnostic Mirror-Equivariance Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Mirrored image dir: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_agnostic_shape_fitting\20260704_mirror_equivariance\mirrored_inputs`
- Rows checked: 4
- Failures: 0
- Audit warnings: 25

| Case | Status | Scope -> mirror | Strong pairs -> mirror | All pairs -> mirror | Lines -> mirror | PCA mirror delta deg |
|---|---|---|---:|---:|---:|---:|
| biker | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 3 -> 3 | 16 -> 16 | 0.033 |
| tower | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0 -> 1 | 16 -> 16 | 0.008 |
| tractor | pass | round_part_pair_candidate -> round_part_pair_candidate | 3 -> 3 | 3 -> 3 | 16 -> 16 | 0.001 |
| tractor_trailer | pass | multi_line_structure_candidate -> multi_line_structure_candidate | 0 -> 0 | 0 -> 1 | 16 -> 16 | 0.041 |

## Interpretation

This verifier mirrors each real image and mirrors its bbox and unlabeled detector polygons together, then reruns the same agnostic fitter. It checks that normalized geometry is equivariant to this image-space transformation: scopes should stay stable, mask mass and PCA should mirror, round-pair counts should remain stable, and line evidence should remain close within deterministic computer-vision tolerances. A pass guards against left/right orientation shortcuts; it is not a proof of universal primitive correctness.

## Audit Warnings

- biker: line orientation_order: 0.5866 vs 0.8053 exceeds tolerance 0.08
- biker: dominant line angle not mirror-equivariant: expected 124.138, got 135.826 delta 11.688
- biker: pair[0].mirror_center_match_cost 21.660 exceeds tolerance 10.0
- biker: pair[0].distance_px: 51.352 vs 63.071 exceeds tolerance 4.0
- biker: pair[0].vertical_pair_fraction: 0.8646 vs 0.7706 exceeds tolerance 0.06
- biker: pair[1].mirror_center_match_cost 35.898 exceeds tolerance 10.0
- biker: pair[1].distance_px: 47.098 vs 73.308 exceeds tolerance 4.0
- biker: pair[1].radius_ratio: 1.4751 vs 1.0307 exceeds tolerance 0.08
- biker: pair[1].vertical_pair_fraction: 0.3567 vs 0.622 exceeds tolerance 0.06
- biker: pair[2].mirror_center_match_cost 54.447 exceeds tolerance 10.0
- biker: pair[2].radius_ratio: 1.0223 vs 1.357 exceeds tolerance 0.08
- biker: pair[2].vertical_pair_fraction: 0.9831 vs 0.8976 exceeds tolerance 0.06
- tower: weak/audit round pair count changed: 0 vs 1
- tower: unmatched weak/audit round pairs after mirror matching: 1
- tractor: dominant line angle not mirror-equivariant: expected 58.588, got 42.37 delta 16.218
- tractor: pair[0].radius_ratio: 1.0 vs 1.155 exceeds tolerance 0.08
- tractor: pair[1].distance_px: 29.259 vs 33.347 exceeds tolerance 4.0
- tractor: pair[1].radius_ratio: 1.5957 vs 1.0079 exceeds tolerance 0.08
- tractor: pair[2].mirror_center_match_cost 16.768 exceeds tolerance 10.0
- tractor: pair[2].distance_px: 30.464 vs 21.23 exceeds tolerance 4.0
- tractor: pair[2].radius_ratio: 1.0761 vs 1.1904 exceeds tolerance 0.08
- tractor: pair[2].vertical_pair_fraction: 0.8469 vs 0.6783 exceeds tolerance 0.06
- tractor_trailer: line orientation_order: 0.5842 vs 0.8233 exceeds tolerance 0.08
- tractor_trailer: weak/audit round pair count changed: 0 vs 1
- tractor_trailer: unmatched weak/audit round pairs after mirror matching: 1
