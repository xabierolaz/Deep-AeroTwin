# SPPA Evidence-Calibrated Material Cycle - 2026-07-02

## External Reviewer Gate Before Implementation

All three external reviewers rejected PBR/photorealistic texturing as a defensible SPPA contribution. The acceptable improvement was narrower: evidence-calibrated procedural material cues that encode semantic part role, evidence source, and uncertainty without claiming observed texture or human-performance improvement.

Reviewer constraints implemented in this cycle:

- No PBR asset generation.
- No text-to-3D or high-fidelity texture claim.
- Materials must declare whether they are semantic priors or unknown fallbacks.
- Unknown classes must remain visually conservative.
- Runtime path must remain optional inside Unreal and must not replace curated asset spawning.
- Any paper claim must be limited to implementation and measured cost until a user study exists.

## Implemented Artifacts

- Python descriptor/material contract: `XYT-xabi-yolo-telemetry/xyt_generate_3d.py`.
- Batch benchmark material manifests: `tools/sppa_sota_benchmark/run_sppa_batch.py`.
- Material ablation benchmark: `tools/sppa_sota_benchmark/run_material_ablation.py`.
- MTL-aware renderer for visual audit: `tools/sppa_sota_benchmark/render_mesh_views.py`.
- Unreal evidence-calibrated semantic materials and component tags: `Unreal/Plugins/PorceTelemetry/Source/PorceTelemetry/Private/PorceSemanticProxyActor.cpp`.
- Unreal descriptor ingestion and reflection smoke now check material role, evidence source, and uncertainty-style tags: `Unreal/Scripts/verify_sppa_backend.py`.

## Python Smoke Results

- `car`: exact class, semantic-prior materials, 4 material roles.
- `mystery_object`: fallback unknown label, fallback-unknown materials, explicit warning/desaturated uncertainty roles.

Example manifests:

- `experiments/sppa_material_smoke/car/car.materials.json`
- `experiments/sppa_material_smoke/mystery_object/mystery_object.materials.json`

## Unreal Smoke Results

`tools/verify_sppa_backend.ps1` passed after the implementation. The report is:

- `pipeline/logs/sppa_backend_verify_latest.json`

Confirmed properties:

- Backend switch still supports `UNREAL_ASSETS` and `SEMANTIC_PROXY`.
- Default backend remains asset spawning.
- Semantic proxy actor exposes `bUseEvidenceCalibratedMaterials`.
- Semantic proxy actor exposes `ConfigureProxyFromDescriptorJson`, `ApplyProxyUpdatePacketJson`, `DescriptorMetersToCentimeters`, and `MaxDescriptorParts`.
- A real `SPPA-DESC-0.2` descriptor fixture produced exactly 12 Unreal mesh components from 12 descriptor parts; a matching `pose_update` packet preserved topology and a mismatched packet was rejected.
- Generated proxy parts include `SPPA_MATERIAL_ROLE_*`, `SPPA_EVIDENCE_SOURCE_*`, and `SPPA_UNCERTAINTY_STYLE_*` tags.
- Unknown fallback includes `SPPA_EVIDENCE_SOURCE_fallback_unknown` and `SPPA_UNCERTAINTY_STYLE_warning_marker`.

## Material Ablation Results

Corrected run directory: `experiments/sppa_material_ablation/20260702_evidence_materials_corrected`.

# SPPA Material Ablation Benchmark

Measured data. This benchmark isolates debug-path proxy construction/export and material-manifest overhead. It is not a user study, not a perceptual-discriminability test, and not a dense Unreal frame-time benchmark.
All build, export, and manifest timings are repeated per class/method; the table reports medians across the six class-level medians, with P95 shown the same way.

| Method | n classes | reps/class | build p50 ms | build p95 ms | export p50 ms | export p95 ms | manifest p50 ms | manifest p95 ms | materials | triangles |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sppa_flat | 6 | 50 | 0.3562 | 0.4139 | 0.8047 | 0.9000 | 0.0007 | 0.0009 | 1-1 | 488-1668 |
| sppa_class_color | 6 | 50 | 0.3569 | 0.3784 | 0.8019 | 0.8864 | 0.0006 | 0.0008 | 1-1 | 488-1668 |
| sppa_part_material | 6 | 50 | 0.3566 | 0.4167 | 0.8073 | 0.8760 | 0.2311 | 0.2749 | 3-5 | 488-1668 |
| sppa_part_material_metadata_low_conf | 6 | 50 | 0.3568 | 0.4155 | 0.8071 | 0.8810 | 0.2284 | 0.2631 | 3-5 | 488-1668 |

Not measured: packaged Unreal frame time, draw calls, material-instance cost, dense-scene scaling, and user recognition/workload.

## Honest Interpretation

The material layer increases descriptor richness and makes the visual/evidence contract inspectable. Unreal can now ingest descriptor parts in a smoke test, but this does not prove better pilot recognition, lower workload, safer operation, or dense runtime suitability. The measured overhead is repeated debug-path overhead, not dense Unreal frame-time; the low-confidence condition is a metadata/uncertainty-style condition, not a proven perceptual effect. The next required evidence is a packaged Unreal dense-scene benchmark and a controlled legibility/false-confidence study.
