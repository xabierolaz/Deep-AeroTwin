# SPPA mesh LOD: fidelity vs triangles (2026-07-16)

## What this is

Production generator change in `XYT-xabi-yolo-telemetry/xyt_generate_3d.py`:

- `SPPA_MESH_LOD` ∈ `{high, balanced, ultra_light}` (default **`balanced`**)
- LOD-aware tessellation for sphere / cylinder / torus / connectors
- Hard-coded high tire/sphere tessellation overrides removed so policy can act
- Optional `Mesh.tire()` helper (hub + torus) for future wheel upgrades

This is **system geometry work**, not a paper-only rewrite.

## Measured budgets (triangles)

| Archetype | high | balanced (default) | ultra_light | balanced/high |
|---|---:|---:|---:|---:|
| biker | 1124 | **788** | 668 | 0.70 |
| tower | 396 | **396** | 396 | 1.00 |
| tractor | 1056 | **688** | 552 | 0.65 |
| tractor_trailer | 1988 | **1268** | 1004 | 0.64 |
| car | 896 | **480** | 320 | 0.54 |
| cow | 2216 | **1176** | 840 | 0.53 |
| person | 400 | **240** | 184 | 0.60 |
| tree | 476 | **188** | 236* | 0.40 |

\*tree ultra vs high from audit file; balanced is the production default.

Artifact: `benchmarks/results/sppa_mesh_lod_budget.json`  
Visual: `figures/sppa_mesh_lod_comparison.png`

## Design intent

- **Keep part structure** (cab/cargo/wheels/rider/frame) — fidelity of roles, not photoreal mesh density.
- **Spend triangles where silhouettes read** (wheel major ring, torso) not on minor tube rings.
- **Boxes stay free** (12 tris): tower barely changes because it is already box/cylinder sparse.

## Next ambition (not done yet)

1. Silhouette-conditioned part scale (MVFit θ) wired into production `build_label_parametric` for real detector masks.
2. Adaptive part count: drop detail parts under distance/confidence budget.
3. True multi-view occupancy loss on real/UAV data with metric GT when available.
4. Prefer low-poly tire disk + hub when torus still costs too much at dense scenes.
