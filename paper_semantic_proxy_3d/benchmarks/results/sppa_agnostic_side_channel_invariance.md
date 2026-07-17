# SPPA Agnostic Side-Channel Invariance Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Neutral image dir: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_agnostic_shape_fitting\20260704_side_channel_invariance\neutral_inputs`
- Rows checked: 4
- Failures: 0

| Original case | Mutated case | Mutated image | Geometry changed | Baseline hash | Mutated hash | Status |
|---|---|---|---:|---|---|---|
| biker | anonymous_detected_object_000 | `experiments/sppa_agnostic_shape_fitting/20260704_side_channel_invariance/neutral_inputs/object_crop_000.png` | false | `490dcf3be26d` | `490dcf3be26d` | pass |
| tower | anonymous_detected_object_001 | `experiments/sppa_agnostic_shape_fitting/20260704_side_channel_invariance/neutral_inputs/object_crop_001.png` | false | `fe418fda12df` | `fe418fda12df` | pass |
| tractor | anonymous_detected_object_002 | `experiments/sppa_agnostic_shape_fitting/20260704_side_channel_invariance/neutral_inputs/object_crop_002.png` | false | `40067244b1e2` | `40067244b1e2` | pass |
| tractor_trailer | anonymous_detected_object_003 | `experiments/sppa_agnostic_shape_fitting/20260704_side_channel_invariance/neutral_inputs/object_crop_003.png` | false | `c96269de9b5f` | `c96269de9b5f` | pass |

## Interpretation

This verifier combines the side-channel mutations that would most easily hide object-specific shortcuts: neutral case IDs, neutral image paths, adversarial labels/tags/model strings, adversarial nested detector class fields, reversed and duplicated detector masks, and removal of a redundant native mask. A pass means the normalized agnostic primitive report is stable under this combined non-geometric mutation for every frozen real replay row. It does not prove primitive correctness or universal 3D reconstruction.
