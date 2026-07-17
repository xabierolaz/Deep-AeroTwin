# SPPA Agnostic Image-Space Parts Probe

Experimental agnostic image-space shape-fitting probe. It uses real pixels, detector bbox, and unlabeled mask geometry only; detector labels and SPPA tags are retained only for audit. The same fitter is applied to every detector crop and reports visible generic primitive cues rather than class-specific part templates. It tests whether generic visual primitive cues improve over mask-only fitting before any SPPA production integration.

- Rows: 4
- Figure: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\figures\sppa_agnostic_mask_vs_image_cues_grid.png`
- Labels used by fitter: False

| Case | Mask-only scope | Image cue scope | Round raw | Round pairs | Lines | Coherent lines | Edge density | Grade | Flags |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| biker | unlabeled_component_candidate | round_part_pair_candidate | 8 | 3 | 16 | false | 0.11424 | experimental_image_part_candidate | low_detector_confidence, weak_lower_support_separation |
| tower | axis_aligned_envelope_only | multi_line_structure_candidate | 8 | 0 | 16 | true | 0.23511 | experimental_image_part_candidate | low_detector_confidence, small_image_evidence, weak_lower_support_separation |
| tractor | single_blob_envelope_only | round_part_pair_candidate | 8 | 3 | 16 | false | 0.28921 | experimental_image_part_candidate | small_image_evidence, weak_lower_support_separation |
| tractor_trailer | axis_aligned_envelope_only | multi_line_structure_candidate | 8 | 0 | 16 | false | 0.21675 | experimental_image_part_candidate | low_detector_confidence, weak_lower_support_separation |

## Interpretation

This probe tests the user's desired bridge from real detection to proxy primitives without using class-specific rules. The image-space path is more ambitious than mask-only fitting because it can expose generic visual primitives that the detector mask may erase. It is still not a claim of perfect arbitrary reconstruction: circles and lines remain unnamed primitive candidates until SPPA assigns conservative semantics through a separate audited normalizer.
