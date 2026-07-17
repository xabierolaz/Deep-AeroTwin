# SPPA Agnostic Detection-Representation Invariance

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Rows checked: 4
- Variants checked: 12
- Failures: 0

| Case | Mutation | Geometry changed | Baseline hash | Mutated hash | Status |
|---|---|---:|---|---|---|
| biker | reversed_used_detections | false | `4f999acf1df2` | `4f999acf1df2` | pass |
| biker | duplicated_used_detections | false | `4f999acf1df2` | `4f999acf1df2` | pass |
| biker | removed_redundant_native_mask | false | `4f999acf1df2` | `4f999acf1df2` | pass |
| tower | reversed_used_detections | false | `a63ae890c6bd` | `a63ae890c6bd` | pass |
| tower | duplicated_used_detections | false | `a63ae890c6bd` | `a63ae890c6bd` | pass |
| tower | removed_redundant_native_mask | false | `a63ae890c6bd` | `a63ae890c6bd` | pass |
| tractor | reversed_used_detections | false | `f70fb82a39ce` | `f70fb82a39ce` | pass |
| tractor | duplicated_used_detections | false | `f70fb82a39ce` | `f70fb82a39ce` | pass |
| tractor | removed_redundant_native_mask | false | `f70fb82a39ce` | `f70fb82a39ce` | pass |
| tractor_trailer | reversed_used_detections | false | `66aa7766cc59` | `66aa7766cc59` | pass |
| tractor_trailer | duplicated_used_detections | false | `66aa7766cc59` | `66aa7766cc59` | pass |
| tractor_trailer | removed_redundant_native_mask | false | `66aa7766cc59` | `66aa7766cc59` | pass |

## Interpretation

This verifier reruns the agnostic image-space fitter after representation-only mutations of detector evidence: reversing detection order, duplicating identical detection masks, and removing a redundant native mask when used detection masks are present. A pass means the normalized primitive report depends on the unlabeled geometry, not on JSON ordering or duplicate mask entries. It does not prove primitive correctness.
