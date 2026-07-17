# SPPA protocol amendment 05 — external neural reference analysis (secondary)

Amendment date: 2026-07-17

Prospective registration of a **new secondary analysis** added after the sealed
confirmatory run. **Does not re-seal predictions; does not change H1 estimand,
n, margin, seeds, sealed predictions, or confirmatory analysis v2.** H1 remains
the sealed SPPA-MVFit vs Generic-MVFit decision of Amendment 03/04.

## E1. Purpose

Answer the expected reviewer question "how does SPPA-MVFit compare to external
neural image-to-3D generators on the same held-out cases" with **locally
measured** numbers, replacing the qualitative-only external contrast and the
hardcoded `NEURAL_REFERENCE` table used in the use-case benchmark.

## E2. Status

Secondary descriptive analysis. Neural baseline outputs are generated
**post-seal**; they are not part of the sealed confirmatory comparison and do
not alter H1, its CI, or the sealed artifacts in any way.

## E3. Subset

60 actors from the sealed held-out test, stratified: 10 per morphology family
(5 CSG-ID + 5 implicit-OOD), selected deterministically (sorted case_id order
inside each family-by-stratum cell). A subset manifest with the case_id list
and public-input hashes is published with the results.

## E4. Inputs (two prespecified conditions)

- **(a) clean-crop (generous):** one shaded oblique render of the source actor
  — the neural methods' best input condition.
- **(b) telemetry-matched (harsh):** the actual 96x96 top observation mask as
  the input image — the closest visual analog of the telemetry channel SPPA
  consumes.
- SPPA-MVFit rows are the **existing sealed results** on the same 60 cases
  (clean condition), read-only from `raw_metrics.csv`.

## E5. Alignment (prespecified, generous)

Neural meshes are uniformly scaled so their bounding-box extents match the GT
actor bounding box, centered on the GT bounding-box center, yaw aligned to the
GT frame. No per-case manual tuning; one fixed script. Non-watertight or
degenerate outputs are voxelized with the same fixed rule and counted as-is;
only a hard crash excludes a case, and exclusions are reported.

## E6. Metrics

Per case: voxel IoU at 64-cubed (same voxelizer and WORLD frame as the sealed
evaluation), triangle count, generation wall time in ms (warm, per-case
inference, model load excluded), peak CUDA VRAM in MB. Report mean/median per
method overall and by stratum, plus paired deltas vs SPPA-MVFit.

## E7. Honesty boundaries

- In condition (a) neural generators receive richer input (clean RGB crop)
  than telemetry tags/silhouettes; in (b) they receive mismatched input they
  were not trained for. Neither is a leaderboard; the comparison measures an
  operating point (IoU vs triangles / ms / VRAM).
- Photoreal asset quality remains neural territory and is not claimed here.
- A visual beauty ranking against SOTA generators remains **prohibited** by
  the claim-evidence matrix.
