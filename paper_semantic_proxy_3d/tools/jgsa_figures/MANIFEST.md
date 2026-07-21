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
| `fig_pareto_neural.png` | `fig:pareto-neural` | `benchmarks\results\sppa_neural_flagship_wave.json` (SPPA 1 449.7 B/0.5613; generic 1 433.5 B/0.3641; VH 32 768 B/0.5164; TripoSR 2.45 MB/0.231 y 1.47 MB/0.128; Hunyuan3D-2mini 46.5 MB/0.171 y 10.5 MB/0.157; TripoSG 2.05 MB/0.002 [artefacto de paridad documentado] y 12.6 MB/0.147; Hunyuan3D-2 full 50.8 MB/0.177 y 13.0 MB/0.148) | `fig_pareto_neural.py` |
| `fig_probes_grid.png` | `fig:probes-grid` | Recorte de `figures\sppa_real_input_probe_grid.png` (columnas "not reproduced" eliminadas; 7 columnas desde x=184, ancho ≈190.5 → 1520×1030) | `fig_probes_grid.py` |
| `fig_runtime_scaling.png` | `fig:runtime-scaling` | `experiments\sppa_packaged_render\20260703T033655Z_packaged_render\packaged_render_summary.json` (dense sweep HISM: pose P95 18.921/41.609/78.933 ms, shape 38.657/94.018/186.113 ms, create 9.883/8.250/7.920 ms @100/250/500) — ver nota 2 | `fig_runtime_scaling.py` |
| `fig_mission_twin_delta.png` | `fig:mission-twin-delta` (propuesto; figura conceptual de misión, aún no referenciada en el tex) | Ilustración conceptual (sin datos cuantitativos nuevos; solo imaginería existente, sin renders nuevos): (a) `benchmarks\blender_twin_wave\frames\t1_oblique30_az000.png` (render Blender v2 fotorrealista, torre; recorte 570×380); (b)(c) `benchmarks\oblique_twin_wave\frames\t2_oblique45_az000.png` (captura UE/Cesium; banda 360×240 sin torre); proxy de (c) recortado de `tools\jgsa_figures\assets\render_fam_lattice_tower.png` (familia lattice_tower, segmentado por saturación). Chip de (c): valores sellados de `benchmarks\results\sppa_neural_flagship_wave.json` (descriptor 1 449.7 B ≈ 1.45 kB; inference_ms mediana 9.45 ≈ 9.4 ms CPU) | `fig_mission_twin_delta.py` |

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

## Cambios 2026-07-21 (pasada de legibilidad de figuras)

Motivo: figuras diminutas e ilegibles, torre poco reconocible en las figs. 2 y
3, suelo de Cesium sin cargar en la fig. 11a, y dos pérdidas respecto a
versiones anteriores (figura del camión paramétrico y tabla medida vs
generadores texto/imagen). Cambios:

- `fig_worked_example.png` (era Fig. 3, ahora Fig. 4): frame del worked
  example 916 → **1584** (mismo stream grabado 20260620_084932). El frame 916
  tenía la torre en el borde izquierdo (bbox x1=4, 93 px); f1584 la tiene
  dentro de cuadro (bbox 29×84 px, x 83..112), terreno Cesium cargado
  (gradiente medio 9.44 vs 6.83), caso GT-matched `f01584_d0` (anchor t0,
  loc err 17.8 m, obs 18.03×4.17 m — `benchmarks/real_stream_wave/results.jsonl`).
  Layout de 1 fila de 5 paneles → 2 filas; (b) recorte real queda
  directamente sobre (d) proxy compilado para la comparación de siluetas;
  (d) ahora usa `tools/jgsa_figures/assets/render_fam_lattice_tower.png`
  (render Blender por roles del grafo sellado) en vez del preview pálido de
  `figures/assets/proxy_lattice_tower.png`. Fuentes subidas a 8–10 pt.
  Script: `tools/jgsa_figures/fig_worked_example.py` (ROOT ahora apunta al
  repo, no a AYTE DOCTOR).
- `fig_family_graphs_blender.png` (Fig. 2): rejilla 2×3 → **3×2** (cada
  panel pasa de ~1/3 a ~1/2 del ancho de texto); leyenda de roles partida en
  dos filas. Mismos renders sellados (`assets/render_fam_*.png`), sin tocar
  geometría. Script: `tools/jgsa_figures/compose_family_graphs.py`.
- `fig_real_stream_main.png` / `fig_real_stream_localization.png` (Fig. 12):
  `FIG_FRAME` 478 → **642** en `benchmarks/real_stream_wave/make_fig_e7.py`.
  f478 tenía las teselas de Cesium sin cargar (suelo borroso); f642 tiene
  terreno cargado, torre centrada (bbox 74 px, conf 0.44) y el anchor GT t0
  reproyectado a 9 px del bbox (verificado con `sanity_geometry.ned_to_px`).
  Candidatos f650/f1778 descartados: el anchor t0 reproyectaba fuera de
  cuadro o a >200 px del bbox.
- `fig_e11_oblique.png` (Fig. 13): figsize (16,10) → (11,7), fuentes 6–9 →
  9–11 pt, supertítulo eliminado (duplicaba el caption), `bbox_inches=tight`.
  Script: `benchmarks/oblique_twin_wave/run_e11_aggregate.py` (escribe en
  `benchmarks/oblique_twin_wave/`; se copia a `figures/`).
- **Figura camión restaurada al main text** (Fig. 3, `fig:sppa-flow`):
  `figures/fig_pipeline_overview.png` (copia byte a byte de
  `sppa_language_to_parts_to_3d_v17.png`, ya documentada arriba) insertada en
  §3.1 tras el párrafo "Vehicle adaptation". El suplemento (archivado) ya no
  duplica la figura: cita `\ref{main-fig:sppa-flow}`.
- **Tabla de generadores restaurada al main text** (Tabla 7,
  `tab:neural-external-wave`, §4.8): `\input` del mismo fragmento autogenerado
  `benchmarks/results/sppa_neural_flagship_wave.tex` que usa el suplemento
  (valores sellados de `benchmarks/results/sppa_neural_flagship_wave.json`;
  envuelto en `\resizebox{\linewidth}{!}{...}`, overfull 39 pt → 0).
- Tamaños en el tex: `fig_h1_by_family`/`fig_robustness_conditions`/
  `fig_pareto_neural` 0.6 → 0.9\linewidth; `fig_stream_map` 0.52 → 0.75;
  `fig_family_graphs_blender` 0.8 → 0.82\linewidth + límite de altura
  0.74\textheight (rejilla 3×2 apaisada-alta).
- Captions actualizados con los valores medidos del nuevo frame
  (`fig:worked-example`: 0.41, 29×84 px, 18.0×4.2 m; `fig:real-stream`:
  Frame 642). Ningún número tecleado a mano: todos salen de
  `results.jsonl`/`events.jsonl` del stream.
- Resultado: main 27 → 29 pp, suplemento 15 pp, compilación limpia (0
  overfull, 0 refs indefinidas).

## Cambios 2026-07-21 (2ª pasada de legibilidad: ancho completo y fig. 3)

Motivo: las figuras seguían sin aprovechar el ancho de página y las variantes
short/long de la figura del camión apenas se distinguían.

- `fig_pipeline_overview.png` (Fig. 3, `fig:sppa-flow`): la fila "Visual
  consequence" se redibuja con proporciones SELLADAS del chequeo de
  invarianza paramétrica
  (`experiments/sppa_scale_variants/20260703_parametric_part_invariance_after_scheduler_policy.json`):
  short truck 5.2×2.3×2.7 m, cargo 2.263 m, 6 neumáticos; long truck
  8.2×2.3×2.7 m (mismo W×H), cargo 5.188 m (+2.925), 8 neumáticos; cabina y
  escala de neumático Δ = 0.0. Flechas de cota sobre el cargo y chips con los
  deltas sellados. Script: `tools/sppa_sota_benchmark/render_sppa_language_to_parts_to_3d_v17.py`
  (regenera también `sppa_language_to_parts_to_3d_v17.png`, que se copia a
  `fig_pipeline_overview.png`, misma convención de copia byte a byte).
- `fig_worked_example.png` (Fig. 4): (a) pasa del frame completo a un
  **recorte left-center** del frame 1584 (píxeles fuente (0,180)-(400,460))
  que abarca dos columnas — el frame completo dejaba la torre a 29 px de 640,
  ilegible en papel; el título del panel declara el recorte. Rejilla 2×3:
  fila 1 = (a) crop + (b) evidencia; fila 2 = (c) planta, (e) twin, (d) proxy
  (d queda bajo b, manteniendo la yuxtaposición silueta↔proxy).
- Figs. 8/9 (`fig_wrong_family_matrix`, `fig_view_ablation`): de minipages
  0.52/0.44 lado a lado → apiladas a 0.85/0.72\linewidth.
- Tamaños tex: `fig_h1_by_family`, `fig_robustness_conditions`,
  `fig_pareto_neural` 0.9 → \linewidth; `fig_stream_map` 0.75 → 0.85;
  `fig_family_graphs_blender` 0.9\linewidth con límite 0.82\textheight.
- Resultado: main 29 → 30 pp, compilación limpia (0 overfull, 0 refs
  indefinidas).

## Cambios 2026-07-21 (3ª pasada: fotos reales de vuelo en §4.9)

El usuario aportó dos fotos reales de vuelo (`rea_flight_data/real_photos/tower.png`,
`rea_flight_data/real_photos/tractor.png`, 640×480) para sustituir las
imágenes de mala calidad de los probes anteriores. Pipeline completo
ejecutado con ellas:

1. **Detección** (YOLOE-26s, checkpoint `yoloe-26s-seg.pt`, config universal,
  CPU): `experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu/`
  via `tools/sppa_sota_benchmark/run_sppa_open_vocab_detector.py`.
  Torre: `electric pylon` conf 0.490, máscara nativa de 75 puntos. Tractor:
  `two-wheeled vehicle` conf 0.479 (wrong token real) + `bush` 0.069.
2. **Anotaciones revisadas**:
  `experiments/sppa_detection_reference/20260721_real_flight_photos_annotations/real_input_2d_annotations.json`
  (mismo esquema que la referencia 20260703; reviewed tags tower/tractor).
3. **Replay SPPA** (misma `build_real_image_assumed_flight_replay.py` y
  supuestos declarados de vuelo que la referencia: torre 45 m AGL yaw 12°,
  tractor 35 m AGL yaw 68°, cámara nadir vfov 70°):
  `experiments/sppa_geometric_projection/20260721_real_flight_photos_replay/`,
  copia del JSON en `benchmarks/results/real_flight_photos_replay.json`.
  Torre: huella de máscara 39.9×17.5 m → gate a 5.60×5.60×28.00 m
  (`constraint_fused_vertical_height`). Tractor: 7.1×6.0 m →
  4.75×2.50×2.60 m (`constraint_fused_vehicle_observation`); etiqueta
  detector `two-wheeled vehicle` → `generic_vehicle` conservador,
  `reviewed_semantic_tag=tractor` en el arquetipo runtime.
4. **Proxies** con el builder paramétrico congelado
  (`XYT-xabi-yolo-telemetry/xyt_generate_3d.py`, `build_label_observed`) a
  las dims gateadas: torre 150 caras / 396 tris (pilar lattice cónico con
  crucetas), tractor 228 caras / 576 tris. Render software propio (OBJ+MTL,
  painter's algorithm) en `tools/jgsa_figures/render_real_flight_proxies.py`
  → `figures/assets/real_flight/` y `figures/fig_real_flight_probes.png`
  (Fig. 11, §4.9). Texto §3.5 y §4.9 actualizado con los valores medidos;
  los cuatro probes archivados de 2026-07-03/04 quedan retenidos en RP.
