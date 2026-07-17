# SPPA Agnostic Path-Invariance Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Neutral image dir: `D:\Deep-AeroTwin-UE57-Test\experiments\sppa_agnostic_shape_fitting\20260704_path_invariance\neutral_inputs`
- Rows checked: 4
- Failures: 0

| Case | Mutated image | Geometry changed | Baseline hash | Mutated hash | Status |
|---|---|---:|---|---|---|
| biker | `experiments/sppa_agnostic_shape_fitting/20260704_path_invariance/neutral_inputs/object_crop_000.png` | false | `4f999acf1df2` | `4f999acf1df2` | pass |
| tower | `experiments/sppa_agnostic_shape_fitting/20260704_path_invariance/neutral_inputs/object_crop_001.png` | false | `a63ae890c6bd` | `a63ae890c6bd` | pass |
| tractor | `experiments/sppa_agnostic_shape_fitting/20260704_path_invariance/neutral_inputs/object_crop_002.png` | false | `f70fb82a39ce` | `f70fb82a39ce` | pass |
| tractor_trailer | `experiments/sppa_agnostic_shape_fitting/20260704_path_invariance/neutral_inputs/object_crop_003.png` | false | `66aa7766cc59` | `66aa7766cc59` | pass |

## Interpretation

This verifier copies each frozen real input image to a neutral filename that does not contain object words such as cyclist, tower, tractor, or trailer. It then reruns the agnostic image-space fitter with only the image path changed. A pass means the normalized primitive report is invariant to file naming and directory naming for this replay. It does not prove primitive correctness; it guards against path/name hardcoding.
