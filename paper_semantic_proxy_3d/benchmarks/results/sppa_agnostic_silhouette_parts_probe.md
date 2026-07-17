# SPPA Agnostic Silhouette Parts Probe

Experimental agnostic shape-fitting probe. It uses detector bbox/mask geometry only, not semantic labels, to test whether image-space evidence can support part proposals before SPPA recipe integration. It is not a ground-truth segmentation, not a 3D reconstruction metric, and not a production claim.

- Rows: 4
- Figure: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\figures\sppa_agnostic_silhouette_parts_grid.png`
- Labels used by fitter: False

| Case | Grade | Scope | Mask polys | Components | Supports | PCA angle | Elongation | Flags |
|---|---|---|---:|---:|---:|---:|---:|---|
| biker | experimental_part_candidate | unlabeled_component_candidate | 2 | 1 | 1 | 58.1 | 2.19 | low_detector_confidence, weak_lower_support_separation |
| tower | experimental_weak | axis_aligned_envelope_only | 1 | 1 | 0 | 91.0 | 5.14 | low_detector_confidence, small_image_evidence, weak_lower_support_separation |
| tractor | experimental_envelope_only | single_blob_envelope_only | 1 | 1 | 1 | 126.9 | 1.51 | small_image_evidence, weak_lower_support_separation |
| tractor_trailer | experimental_envelope_only | axis_aligned_envelope_only | 1 | 1 | 1 | 99.3 | 3.03 | low_detector_confidence, weak_lower_support_separation |

## Interpretation

This is deliberately not a SPPA production path yet. It tests whether the mask contains enough geometry to propose parts without using the semantic label. `experimental_envelope_only` means the image supports a coarse oriented proxy but not reliable internal parts. `experimental_part_candidate` means the geometry exposes either unlabeled detector components or multiple compact supports. A weak grade means the visual evidence should not be over-interpreted; SPPA should keep a conservative family-level proxy or high uncertainty.
