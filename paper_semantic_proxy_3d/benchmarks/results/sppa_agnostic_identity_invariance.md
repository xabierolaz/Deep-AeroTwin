# SPPA Agnostic Identity-Invariance Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Rows checked: 4
- Failures: 0

| Original case | Mutated case | Geometry changed | Baseline hash | Mutated hash | Status |
|---|---|---:|---|---|---|
| biker | unseen_object_crop_000 | false | `490dcf3be26d` | `490dcf3be26d` | pass |
| tower | unseen_object_crop_001 | false | `fe418fda12df` | `fe418fda12df` | pass |
| tractor | unseen_object_crop_002 | false | `40067244b1e2` | `40067244b1e2` | pass |
| tractor_trailer | unseen_object_crop_003 | false | `c96269de9b5f` | `c96269de9b5f` | pass |

## Interpretation

This verifier renames each frozen real-image replay row to an unseen neutral object ID and reruns the agnostic image-space fitter. A pass means the normalized geometric primitive report is invariant to the example identity after removing identity-only audit fields. It does not prove that the visible primitive cues are correct; it only guards against case-name hardcoding.
