# SPPA use-case SOTA strategy (2026-07-16)

## What “SOTA” means here

**Not:** densest or most photoreal mesh vs Trellis/Hunyuan/TripoSR.

**Yes:** best *operational semantic proxy* for UAV digital twins when:

- input is tag / detector / sparse telemetry (not a clean studio crop every frame);
- the twin must stay interactive (Unreal + other load);
- wrong confident geometry is worse than a conservative fallback;
- pose updates every frame, topology rarely.

Virtues to maximize:

1. Role-labeled part structure (readable object class)
2. Metric dims from calibration or safe priors
3. Millisecond local build
4. Low triangle/vertex budget
5. Descriptor/update contract (no full regenerate on pose)
6. Explicit fallback under weak evidence
7. Orders-of-magnitude lighter than neural generators

## Implemented now

| Lever | Where | Effect |
|---|---|---|
| Mesh LOD `high/balanced/ultra_light` | `xyt_generate_3d.py` Mesh | −25–45% tris on vehicles vs high |
| Auto LOD policy | `select_use_case_mesh_lod` | distance/confidence → LOD |
| CLI | `--mesh-lod`, `--budget-mode`, `--distance-m` | production path |
| Use-case score | `score_use_case_sota` | operational ranking in [0,1] |
| Benchmark | `run_sppa_use_case_sota_benchmark.py` | tables + JSON |
| Paper table | `tab:use-case-sota` | claims bounded |

### Measured (metric dims, after cheap-wheel + aggressive LOD)

| Mode | Mean tris | Mean build ms | Mean × lighter vs TripoSR | Gate |
|---|---:|---:|---:|---|
| **balanced** (default) | **639** | **0.23** | **~48×** | passed |
| **ultra_light** | **552** | **0.19** | higher | passed |

Use-case score mean (balanced) **~0.83**. Regression gates live in
`run_sppa_use_case_sota_benchmark.py` (`gate_status: passed`).

### Speed / poly levers implemented

1. Cheap-disk wheels (cylinder) instead of torus under balanced/ultra_light  
2. Lower default tessellation tables  
3. Skip visual detail rails/braces under ultra_light  
4. Auto LOD biased to ultra_light when far/weak/dense (`select_use_case_mesh_lod`)  
5. Optional connectors flag for future part culling  

## Next levers (priority order)

1. **Always-on silhouette conditioning** when mask+scale present (part θ, not only L/W).
2. **Distance-adaptive part set** for high-detail recipes (drop lights/mirrors first).
3. **HISM + changed-only scheduler** as the default dense-scene path.
4. Public metric UAV set when available for external occupancy score.

## Honesty line for reviewers

SPPA can be SOTA *for the twin proxy job* while losing every photoreal beauty contest. That is the product thesis.
