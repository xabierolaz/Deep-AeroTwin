# SESSION HANDOFF — 2026-07-21 (paper SPPA-MVFit, JGSA)

Estado al cerrar la sesión. Leer esto primero al retomar. Todo el trabajo de
la sesión está commiteado; lo que sigue explica el porqué de cada cosa.

## Dónde vive el paper

- `paper_semantic_proxy_3d/` dentro de `D:\Deep-AeroTwin-UE57-Test` es un
  **junction** a `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d` (mismos archivos;
  git los ve por la ruta del repo). Editar en la ruta del repo.
- Compilar: `pdflatex -interaction=nonstopmode semantic_proxy_3d_paper.tex`
  ×2 (MiKTeX instalado). Render QA: `pdftoppm -png -r 60`.
- Estado actual: **main 31 pp, 0 overfull, 0 refs indefinidas**. Suplemento
  ELIMINADO del envío (archivado; su PDF ya no se trackea, ver `.gitignore`).
- `tools/jgsa_figures/MANIFEST.md` = proveniencia de TODAS las figuras
  (regla de la casa: ningún número de figura se teclea a mano; todo sale de
  JSON/CSV sellados). Actualizarlo al tocar figuras.

## Commits de esta sesión (en orden)

1. `2b9b679a` Readability pass: figs 2/3/11 rehechas, camión + tabla
   neural-wave restauradas al main, SPPA expandido (Semantic Primitive Proxy
   Assembly), RP×30, anti-paja, guarda OOD de H1 en §4.1.
2. `f5777ec3` Sin suplemento en el envío JGSA (manifiestos alineados,
   PDF del suplemento fuera del tracking).
3. `387df16c` Figuras a ancho completo; fig. 3 con variantes short/long a
   proporciones selladas del invariance check (cargo 2.263→5.188 m, 6→8
   neumáticos, cab/tire Δ=0).
4. `259e1943` Fotos reales de vuelo (torre, tractor) por todo el pipeline en
   §4.9 (nueva Fig 11).
5. `29ab64d2` Comparativa real flight: SPPA vs TripoSR/Hunyuan en fotos
   aéreas (TripoSR blobs 26.8k/39.7k tris; Hunyuan fallo duro "No surface
   found"; SPPA 396/576 tris ~0.2 ms CPU). Artefactos en
   `benchmarks/results/real_flight_comparison_20260721.{json,md}`.
6. `1539017f` Fig 11 con columna de competencia (panel d TripoSR + nota
   Hunyuan).
7. `26399ae8` Últimos remanentes auditoría: E14 sin supertítulo, etiquetas
   E7 con chip blanco.
8. `74eaaeec` Revisión editorial (7 puntos): fig 1 con foto real, tablas
   8/10 claras, figs 13/14/15 grandes, conclusión asertiva.
9. `7bd048e3` video_final resincronizado + pasada de vídeo real en §4.10
   (nueva Fig 12) + Declarations + DOI placeholder.

## Estado del paper (qué es cada figura/tabla)

- Fig 1 misión: (a) **foto real de vuelo** tower.png + bbox YOLOE medido.
- Fig 2 familias 3×2 (torre legible por roles).
- Fig 3 mecanismo camión (variantes selladas).
- Fig 4 worked example, frame 1584 del stream (torre dentro de cuadro).
- Fig 5 Algorithm 1 (fitter 31 candidatas).
- Fig 6 H1 por familia (+0.190 sellado, 12/12 positivas).
- Fig 7 robustez (margen aguanta corrupciones).
- Fig 8 wrong-family matrix. Fig 9 view ablation.
- Fig 10 Pareto (SPPA 1.45 kB/0.561 vs neurales).
- Fig 11 fotos reales vuelo: evidencia→gate→proxy→TripoSR blob (+Hunyuan fail).
- Fig 12 **vídeo real** (video_final): frame 182 + telemetría ArduPilot +
  99/239 frames con tower-class + crecimiento bbox.
- Fig 13 real stream f642 (crop torre, anchors GT, chips blancos).
- Fig 14 E11 2×2. Fig 15 E14 LiDAR simulado.
- Tabla 1 posicionamiento; Tabla 7 ola neural medida (TripoSR, H-mini,
  TripoSG, H-full ×2 entradas + SPPA/Generic/VH); Tabla 8 runtime en dos
  bloques (real vs replay sintético); Tabla 10 E11 simplificada.

## Datos clave de la sesión (no olvidar)

- **Expansión SPPA**: Semantic Primitive Proxy Assembly (del manuscrito
  original f2d69975).
- **Frames elegidos del stream** (`pipeline/logs/zero_trust/20260620_084932/vision`):
  worked example = 1584 (GT t0, loc 17.8 m, obs 18.0×4.2 m); fig 13 = 642
  (anchor t0 a 9 px del bbox). case_id usa %05d (`f01584_d0`).
- **Terreno Cesium**: discriminar cargado/no cargado = gradiente medio
  (|∇|>4) + fracción de píxel negro (<25) — el globo negro/wireframe engaña
  al gradiente solo.
- **video_final.mp4** (corte del usuario de M_20_1RR, 1280×960 @10 fps,
  239 frames): frame 0 = **frame 752** del original (**+12.856 s**), medido
  por template matching (ratio 5.8493). Ventana 09:39:01.109–09:39:24.909 Z.
  Sync: `rea_flight_data/video_final.json`. Trayectoria:
  `tools/real_flight_replay/out/trajectory_video_final.csv` (239 poses,
  hueco máx GPS 0.22 s).
  - Ventana de recorte 4:3 medida: original (0,1200)–(2160,2820) →
    fx=fy=1421 px, pp=(640,480) en video_final.
  - YOLOE: 147 dets; tower-class 99/239 frames (conf med 0.31; mejor 0.576
    f182). `experiments/sppa_detection_reference/20260721_video_final_yoloe26s/`.
  - **Las fotos tower.png/tractor.png NO están en la ventana de video_final**
    (torre ≈ frame 2492/t=42.6 s; tractor ≈ frame 54/t=0.9 s del ORIGINAL).
    Si se quiere vídeo centrado en ellas, hace falta otro corte.
- **GT de apoyos**: `tools/real_flight_replay/out/tower_ground_truth.csv`
  (P1–P4, ortofoto PNOA ~1–2 m; OSM comprobado VACÍO en la zona 2026-07-21).
- **BLOQUEANTE — montura de cámara sin calibrar**: el fit del toolkit
  (`camera_mount_fit.json`, rms 277 px, 4 puntos) proyecta sesgo sistemático
  40–80 m contra P1–P4; re-ajuste grid yaw/pitch/roll no baja de ~42 m en el
  límite del modelo. La evaluación métrica de huellas queda DIFERIDA hasta
  calibrar la montura (specs gimbal o pasada de calibración con los apoyos).

## Pendientes (en tu campo / próxima sesión)

1. **Mintar DOI Zenodo** del paquete `reproducibility/sppa_mvfit/` y
   sustituir el placeholder en Data Availability (línea "pending mint").
2. **Formato Springer** (opcional pero recomendado): clase `svjour3` +
   `spbasic` para la versión final; highlights (ya existe HIGHLIGHTS.md).
3. **Calibración de montura** para cerrar el estudio métrico de video_final
   (datos todos listos: sync, trayectoria, detecciones, P1–P4, crop window).
4. **Decisión Fig 12 antigua (mapa del vuelo)**: movida a RP; si se quiere
   de vuelta, está en `figures/fig_stream_map.png`.
5. **Shap-E/Point-E**: fuera de la Tabla 7 (test superseded); reintegrables
   como bloque aparte si se desea.
6. **MVFit-v2 (fidelidad)**: el usuario quiere "que no haga falta defenderla
   con palabras". Respuesta dada: es investigación nueva (más partes /
   supercuádricas → protocolo nuevo, re-preregistro y re-sellado; el fitter
   NO es el cuello de botella: +0.002 al doblar presupuesto). Preparar
   propuesta aparte si se activa.
7. Vídeo completo a 640×480 blur-fill: método validado en clip de 10 s
   (`rea_flight_data/M_20_1RR_VIDEO/..._blurfill_sample.mp4`); no procesado
   entero (quedó a la espera; para evidencia, correr detector sobre frames
   verticales originales y usar blur-fill solo para display).

## Convenciones que NO romper

- Nada de números a mano en figuras/tablas: siempre desde JSON/CSV sellado.
- `paper_semantic_proxy_3d/benchmarks/results/*.tex` autogenerados → no
  editar a mano; regenerar con su script.
- Claims: lo confirmatorio está SELLADO (`reproducibility/sppa_mvfit/`);
  no tocar grafos ni protocolo sin nuevo preregistro.
- git: commitear solo lo de la línea de trabajo actual; el árbol tiene
  trabajo preexistente de otras líneas (Unreal C++, pipeline, tools) que se
  deja fuera salvo petición expresa.
