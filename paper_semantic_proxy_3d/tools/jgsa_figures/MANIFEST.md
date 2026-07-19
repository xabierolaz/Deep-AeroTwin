# MANIFEST — Figuras JGSA del paper SPPA

Manifiesto de procedencia de las 14 figuras referenciadas por
`semantic_proxy_3d_paper.tex` (nombres exactos en `figures\`).
Regla: todo número mostrado en una figura procede de un artefacto JSON/CSV
sellado o de benchmark; ningún valor se tecleó a mano en los scripts
(los compositores leen los JSON en tiempo de render).

- Scripts de charts (matplotlib, estilo Okabe-Ito 300 dpi): `tools\jgsa_figures\fig_*.py`, estilo común `jgsa_style.py`.
- Scripts Blender (Blender 4.5, `-b --factory-startup`): `tools\jgsa_figures\blender\*.py` + helper `sppa_scene.py`.
- Compositores (PIL/matplotlib): `tools\jgsa_figures\compose_*.py`.
- Export de assets 3D desde el paquete sellado (solo lectura):
  `tools\jgsa_figures\export_blender_assets.py` → `tools\jgsa_figures\assets\`
  (`blender_assets.json`, `gt_truck.obj`, `gt_quadruped.obj`, `masks_truck.png`).
  El export re-verifica por aserción el IoU voxel de cada caso contra
  `raw_metrics.csv` sellado (truck 0.570722, quadruped 0.821777; ambos < 1e-9).
- Paquete sellado `reproducibility\sppa_mvfit\` usado solo en lectura
  (`sys.dont_write_bytecode=True`).

## Tabla figura → fuente → script

| Figura (`figures\`) | Label en el paper | Fuente(s) exacta(s) | Script(s) |
|---|---|---|---|
| `fig_pipeline_overview.png` | `fig:pipeline-overview` | Diagrama preexistente del pipeline SPPA (label→parts→3D, variantes short/long truck); copia byte a byte de `figures\sppa_language_to_parts_to_3d_v17.png` (contenido verificado contra el caption) | — (copia intencional) |
| `fig_family_graphs_blender.png` | `fig:family-graphs` | `tools\jgsa_figures\assets\blender_assets.json` (actores por defecto `mv.default_theta()`, roles de `benchmarks\mvfit_reviewer_experiments\e6_role_aware\ROLE_MAPPING_FROZEN.md`) | `blender\render_family_graphs.py` → `assets\render_fam_*.png`; `compose_family_graphs.py` |
| `fig_role_colored_blender.png` | `fig:role-colored` | Render: caso `test-csg_id-quadruped-018`, θ sellado (`sealed_method_outputs.jsonl`), GT de `private_source_actors.jsonl` voxelizado 64³. Barras E6: `benchmarks\mvfit_reviewer_experiments\e6_role_aware\role_aware_iou.json` (true 0.3193 vs shuffle_random 0.0534 vs cyclic 0.0173; Δ=0.2651 [0.2496, 0.2809], n=120 csg_id) | `blender\render_role_overlay.py` → `assets\render_role_overlay.png`; `compose_role_colored.py` |
| `fig_fitting_sequence_blender.png` | `fig:fitting-sequence` | Caso `test-csg_id-articulated_vehicle-013` (clean): máscaras de `reproducibility\sppa_mvfit\data\test\observation_masks.npy` (vía `assets\masks_truck.png`); θ_init de `mv.initialize_theta`; θ_fit sellado; GT mesh 64³ marching cubes (`assets\gt_truck.obj`); IoU 0.571 = valor sellado | `blender\render_fitting_sequence.py` → `assets\render_fit_{init,fit,gt}.png`; `compose_fitting_sequence.py` |
| `fig_h1_by_family.png` | `fig:h1-by-family` | Point estimates: `reproducibility\sppa_mvfit\results\test\confirmatory_summary.json` (cross-check < 1e-9 por aserción). IC 95 % por celda: bootstrap within-cell (10 000 resamples, seed 77157) sobre `reproducibility\sppa_mvfit\results\test\raw_metrics.csv` — ver nota 1 | `fig_h1_by_family.py` |
| `fig_robustness_conditions.png` | `fig:robustness-conditions` | `benchmarks\mvfit_posthoc_analysis\t1_robustness\robustness_conditions_table.json` (Δ 0.190/0.163/0.118/0.189/0.189, todas > margen +0.030) | `fig_robustness_conditions.py` |
| `fig_2x2_decomposition.png` | `fig:2x2-decomposition` | `benchmarks\mvfit_posthoc_analysis\t2_graph_x_fitting\graph_x_fitting_2x2.json` (0.180/0.427/0.367/0.557; efectos +0.248/+0.190/+0.187/+0.130) | `fig_2x2_decomposition.py` |
| `fig_wrong_family_matrix.png` | `fig:wrong-family-matrix` | `benchmarks\mvfit_reviewer_experiments\e1_wrong_family\wrong_family_matrix.json` (diagonal correcta 0.557 vs wrong mean 0.205) | `fig_wrong_family_matrix.py` |
| `fig_view_ablation.png` | `fig:view-ablation` | `benchmarks\mvfit_reviewer_experiments\e2_top_only\top_only_ablation.json` (dual 0.557 / top 0.458 / side 0.545) + miniaturas de `observation_masks.npy` / `public_cases.json` | `fig_view_ablation.py` |
| `fig_external_scatter.png` | `fig:external-scatter` | `benchmarks\external_mesh_sanity\external_sanity.json` (SPPA 0.413 / generic 0.370 / visual hull 0.656) | `fig_external_scatter.py` |
| `fig_external_gallery.png` | `fig:external-gallery` | Galería cualitativa preexistente (ModelNet40 car 0.628/0.397; Objaverse water tower 0.118/0.126); copia byte a byte de `figures\external_sanity_qualitative.png` (contenido verificado contra el caption) | — (copia intencional) |
| `fig_pareto_neural.png` | `fig:pareto-neural` | `benchmarks\results\sppa_neural_external_wave.json` (SPPA 1 449.7 B/0.5613; generic 1 433.5 B/0.3641; VH 32 768 B/0.5164; TripoSR 2.45 MB/0.231 y 1.47 MB/0.128; Hunyuan3D-2mini 46.5 MB/0.171 y 10.5 MB/0.157) | `fig_pareto_neural.py` |
| `fig_probes_grid.png` | `fig:probes-grid` | Recorte de `figures\sppa_real_input_probe_grid.png` (columnas "not reproduced" eliminadas; 7 columnas desde x=184, ancho ≈190.5 → 1520×1030) | `fig_probes_grid.py` |
| `fig_runtime_scaling.png` | `fig:runtime-scaling` | `experiments\sppa_packaged_render\20260703T033655Z_packaged_render\packaged_render_summary.json` (dense sweep HISM: pose P95 18.921/41.609/78.933 ms, shape 38.657/94.018/186.113 ms, create 9.883/8.250/7.920 ms @100/250/500) — ver nota 2 | `fig_runtime_scaling.py` |

## Notas

1. **ICs de `fig_h1_by_family`.** Los IC 95 % por celda familia×estrato no están
   materializados en ningún artefacto sellado; se derivaron por bootstrap
   within-cell (10 000 resamples, seed 77157, idéntico protocolo que el resto
   del paper) sobre los pares por actor de `raw_metrics.csv`. Los point
   estimates de cada celda se cross-chequean contra `confirmatory_summary.json`
   con aserción < 1e-9 dentro del propio script. El Δ global 0.190
   [0.181, 0.199] es el valor sellado del confirmatorio.

2. **Fuente de `fig_runtime_scaling` (discrepancia documentada).** La figura
   usa el dense sweep HISM consistente del run
   `20260703T033655Z_packaged_render`. Los números "17.8/19.3 ms @100" que
   aparecen en texto/tablas del supplement corresponden a un run distinto
   (2026-07-02, backend actor-proxy, tabla del supplement ≈ línea 2096), no al
   HISM. Decisión: la figura muestra un único sweep internamente consistente y
   no mezcla backends.

3. **Fix de coordenadas del GT (Grupo A).** La versión de trimesh instalada
   devolvía `VoxelGrid.marching_cubes` en coordenadas de índice de voxel
   (0..64), ignorando el transform mundo. `export_blender_assets.py` detecta
   ese caso y aplica el transform manualmente (world = lows + grid·steps,
   x∈[-4.8,4.8], y∈[-3.2,3.2], z∈[0,6.4], 64³). Verificado: bbox del GT en
   mundo ≈ bbox del actor ajustado (intersección positiva en los 3 ejes para
   ambos casos) y alineación visual en los renders compuestos.

4. **Renders Blender.** Eevee (`BLENDER_EEVEE_NEXT`), view transform Standard
   (AgX lavaba la paleta Okabe-Ito), cámara 3/4 ajustada al bbox, suelo blanco,
   paleta de roles fija: primary structure #0072B2, cabin/head #E69F00,
   wheels/legs #009E73, cargo/crown #56B4E9, appendages #D55E00,
   frame/platforms #CC79A7.

## Estado

Las 14 figuras referenciadas por el paper contienen render/datos reales;
no queda ningún placeholder. Verificación 2026-07-18: existencia, integridad
PIL (`Image.verify()`), dimensiones y fuentes de datos — todo OK.
