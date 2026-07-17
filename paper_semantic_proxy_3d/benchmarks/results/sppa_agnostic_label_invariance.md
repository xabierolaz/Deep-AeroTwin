# SPPA Agnostic Label-Invariance Verification

- Status: pass
- Replay JSON: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\benchmarks\results\real_image_assumed_flight_replay.json`
- Rows checked: 4
- Failures: 0

| Case | Geometry changed after label mutation | Baseline hash | Mutated hash | Status |
|---|---:|---|---|---|
| biker | false | `4f999acf1df2` | `4f999acf1df2` | pass |
| tower | false | `a63ae890c6bd` | `a63ae890c6bd` | pass |
| tractor | false | `f70fb82a39ce` | `f70fb82a39ce` | pass |
| tractor_trailer | false | `66aa7766cc59` | `66aa7766cc59` | pass |

## Interpretation

This verifier mutates detector labels, reviewed SPPA tags, publication labels, normalization strings, detector model names, and nested detection class IDs/names. It then reruns the agnostic image-space fitter and compares normalized geometry reports after removing audit-only label fields. A pass means the geometric primitive cues are invariant to those semantic fields for the frozen real-image replay.
