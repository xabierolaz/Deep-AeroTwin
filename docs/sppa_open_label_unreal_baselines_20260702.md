# SPPA Open-Label, Unreal Switch, and Lightweight Baselines - 2026-07-02

This note records measured artifacts generated after the zero-trust audit of the SPPA universality claim.

## Unreal / Porce Backend Switch

Command: `tools/verify_sppa_backend.ps1` after rebuilding `AirTrafficEditor` with UE 5.7.

Artifacts:

- Report: `pipeline/logs/sppa_backend_verify_latest.json`
- Log: `pipeline/logs/sppa_backend_verify_latest.log`

Measured result:

- Backend enum exposes `UNREAL_ASSETS` and `SEMANTIC_PROXY`.
- Default backend remains `UNREAL_ASSETS`.
- `SetSpawnBackend` and `ToggleSpawnBackend` switch both directions.
- SPPA proxy generation smoke covers: bike, cow, tower, car, ambulance, tree, antenna, mystery_object, unknown.
- Unknown/tentative fallback generated 3 mesh components with collision disabled.

Interpretation: Unreal now has open-label input coverage through exact classes, keyword archetypes, and fallback. This is not evidence of correct high-fidelity geometry for every word.

## Python Open-Label Smoke

Command: `python tools/sppa_sota_benchmark/run_sppa_batch.py --objects-csv experiments/sppa_open_label_smoke/open_labels.csv --output-dir experiments/sppa_open_label_smoke/batch_outputs`

Observed examples:

- `car` -> `exact_class`, 864 triangles.
- `ambulance` -> `keyword_archetype/light_vehicle`, 864 triangles.
- `antenna` -> `keyword_archetype/vertical_structure`, 90 triangles.
- `mystery_object` -> `fallback_unknown_label`, 94 triangles.

## Lightweight Baselines

Command: `python tools/sppa_sota_benchmark/run_lightweight_baselines.py --output-dir experiments/sppa_lightweight_baselines/20260702_parametric_parts --reps 50`

Artifacts:

- Metrics CSV: `experiments/sppa_lightweight_baselines/20260702_parametric_parts/lightweight_baseline_metrics.csv`
- Summary: `experiments/sppa_lightweight_baselines/20260702_parametric_parts/lightweight_baseline_summary.md`
- Contact sheets: `experiments/sppa_lightweight_baselines/20260702_open_label/views/contact_sheets/`
- Paper figure: `paper_semantic_proxy_3d/figures/sppa_lightweight_truck_views.png`

Summary table:

```
| Method | n classes | median build ms | p95 build ms | triangle range | mean dimension error |
|---|---:|---:|---:|---:|---:|
| billboard | 6 | 0.0007 | 0.0011 | 2-2 | 0.3333 |
| box | 6 | 0.0046 | 0.0058 | 12-12 | 0.0000 |
| capsule_proxy | 6 | 0.0585 | 0.0685 | 212-212 | 0.0081 |
| ellipsoid | 6 | 0.0372 | 0.0447 | 144-144 | 0.0000 |
| sppa_fixed | 6 | 0.2924 | 0.3563 | 488-1668 | 0.2852 |
| sppa_global_scaled | 6 | 0.4575 | 0.4963 | 488-1668 | 0.0000 |
| sppa_parametric | 6 | 0.2902 | 0.3285 | 488-1692 | 0.1589 |
```

Interpretation: boxes and billboards are faster and geometrically simpler; SPPA stays sub-ms but is not the latency winner against trivial proxies. Its argument must be recognizability/semantic structure under bounded cost.

## Scale Variant Benchmark

Command: `python tools/sppa_sota_benchmark/run_scale_variants.py --output-dir experiments/sppa_scale_variants/20260702_parametric_parts --reps 50`

Artifacts:

- Metrics CSV: `experiments/sppa_scale_variants/20260702_parametric_parts/scale_adaptation_metrics.csv`
- Summary: `experiments/sppa_scale_variants/20260702_parametric_parts/scale_adaptation_summary.md`
- Contact sheets: `experiments/sppa_scale_variants/20260702_parametric_parts/views/contact_sheets/`
- Part-invariance check: `experiments/sppa_scale_variants/20260702_parametric_parts/truck_same_width_height_part_invariance.csv`
- Paper figures: `paper_semantic_proxy_3d/figures/sppa_scale_truck_short_views.png`, `paper_semantic_proxy_3d/figures/sppa_scale_truck_long_views.png`

Summary table:

```
| Method | n variants | median dim error | median build ms | triangle range |
|---|---:|---:|---:|---:|
| sppa_fixed | 12 | 0.3350 | 0.2941 | 488-1668 |
| sppa_global_scaled | 12 | 0.0000 | 0.4619 | 488-1668 |
| sppa_parametric | 12 | 0.2170 | 0.2928 | 488-1692 |
| box | 12 | 0.0000 | 0.0045 | 12-12 |
```

Vehicle-only subset:

```
| Method | n variants | median dim error | median build ms | triangle range |
|---|---:|---:|---:|---:|
| sppa_fixed | 4 | 0.3926 | 0.4201 | 864-1668 |
| sppa_global_scaled | 4 | 0.0000 | 0.6401 | 864-1668 |
| sppa_parametric | 4 | 0.0223 | 0.3448 | 864-1692 |
| box | 4 | 0.0000 | 0.0045 | 12-12 |
```

Interpretation: `sppa_global_scaled` is the trivial baseline that removes AABB dimension error by scaling every part. It is not the defended SPPA behavior because it deforms cab, wheels, windows, and body together. `sppa_parametric` keeps vehicle cab/wheel dimensions bounded and changes cargo/body span and axle placement for supported vehicle archetypes. This is still explicit-dimension adaptation, not silhouette fitting, mask fitting, user readability evidence, or Unreal frame-time evidence.

## Remaining Non-Claims

- No human recognition or NASA-TLX/SAGAT evidence.
- No VR headset FPS or GPU frame-time benchmark yet.
- No real UAV mask/silhouette fitting benchmark yet.
- No guarantee that arbitrary words map to correct specific morphology; unknown labels use conservative fallback.
