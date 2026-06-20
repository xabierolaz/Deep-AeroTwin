# Figuras generadas para el paper Unreal/PORCE

Esta carpeta contiene las figuras compuestas pedidas en la conversacion.

## Archivos principales

- `System Workflow.png`: diagrama de flujo del sistema regenerado por script y copiado a las dos carpetas `Imagenes/` usadas por LaTeX.
- `Pipeline A.png`: diagrama de arquitectura del workflow de simulacion regenerado por script y copiado a las dos carpetas `Imagenes/` usadas por LaTeX.
- `paper_figure_1_static_tower_sequence.png`: Figura 1 final para LaTeX, copiada tambien a las carpetas `Imagenes/` del paper raiz y de la plantilla IEEE.
- `paper_figure_2_moving_peloton_sequence.png`: Figura 2 final pendiente. Debe regenerarse solo desde una captura Unreal real actualizada, con pelotones `APelotonSplineActor` simples moviendose izquierda-derecha, torres/vacas activas segun el experimento completo, sin predicciones visuales y con YOLO en modo `paper`.
- `paper_figure_3_e2e_ablation.png`: Figura de ablacion E2E reconstruida desde la campana `pipeline/logs/e2e/campaign_20260612_174114.json`, copiada tambien a las carpetas `Imagenes/` del paper raiz y de la plantilla IEEE.
- `paper_figure_4_audited_collision_evasion.png`: Figura de validacion auditada del run `pipeline/logs/zero_trust/20260220_092802`, con reduccion de percepcion, grilla local y serie temporal de margen, copiada tambien a las carpetas `Imagenes/` del paper raiz y de la plantilla IEEE.
- `generate_architecture_latex_figures.py`: regenerador de `System Workflow.png`, `Pipeline A.png` y `architecture_manifest.json`.
- `generate_final_latex_figures.py`: regenerador de las dos figuras finales y de `final_manifest.json`.
- `generate_validation_latex_figures.py`: regenerador de las figuras de validacion y de `validation_manifest.json`.
- `architecture_manifest.json`: trazabilidad de los diagramas de arquitectura copiados a LaTeX.
- `final_manifest.json`: trazabilidad de los archivos finales, runs fuente y staging Unreal cuando exista una captura actual valida de Figura 2.
- `validation_manifest.json`: trazabilidad de la campana E2E, run auditado, frame 5053 y tracks proxy.
- `generate_paper_figures.py`: libreria de contexto compartida por los regeneradores finales.
- `yolo_crossing_precheck/final_artifacts/`: carpeta reservada para la evidencia minima de la Figura 2 movil cuando exista una captura actual valida. Los artefactos antiguos de 2026-06-17 fueron eliminados porque no representaban el estado actual de los pelotones.

## Version activa en LaTeX

La version activa del paper usa `System Workflow.png`, `Pipeline A.png`, `paper_figure_1_static_tower_sequence.png`, `paper_figure_2_moving_peloton_sequence.png`, `paper_figure_3_e2e_ablation.png` y `paper_figure_4_audited_collision_evasion.png`. De esas figuras, la unica pendiente es `paper_figure_2_moving_peloton_sequence.png`, porque debe salir de una ejecucion Unreal + ArduPilot + YOLO actualizada. Las seis capturas antiguas del bloque de resultados estan preservadas en el `.tex` dentro de `\iffalse ... \fi`, pero no se compilan.

La Figura 3 usa cuatro runs representativos de la campana E2E y las medias de diez runs por escenario. La Figura 4 no usa la captura visual del run historico porque esa ventana no corresponde a Unreal; usa los conteos y cajas serializados en `vision/events.jsonl`, los tres tracks proxy publicados justo antes del disparo y la trayectoria real de `brain/trajectory.csv`.

## Lectura critica

- La Figura 1 generada aqui usa un episodio continuo WP1->WP2 con una unica torre del run `pipeline/logs/paper_wp1_wp2_tower/paper_wp1_wp2_tower_p0.56_l+8.0_20260617_120539`.
- La torre usada esta en `lat=42.22904865463611`, `lon=-1.234404232738992`, progreso `0.56` del tramo WP1->WP2 y desplazamiento lateral `+8 m`.
- Orden activo de lectura: `1A` navegacion nominal, `1B` deteccion sin accion cerca del umbral, `1C` ultima deteccion sin accion con radios, `1D` inicio de evasion A*, `1E` evasion en curso, `1F` resumen final de ruta.
- Decision actual: los seis paneles de Figura 1 deben ser cenitales/top-down y compartir ejes. El `Local A* occupancy grid` no es absoluto ni permanente; se muestra solo en `1D` y `1E`, cuando el planner ya ha discretizado el vecindario local relativo al UAS.
- Los seis paneles usan el mismo encuadre fijo activo: eje X `[-40, 160]` m y eje Y `[-165, 35]` m, con las mismas etiquetas `East (m)` y `North (m)`. Es un encuadre cuadrado `1:1` de 200 m x 200 m centrado en el tramo WP1->WP2, con mas aire por encima de WP1 y menos espacio muerto bajo WP2.
- `1B` usa una deteccion sin accion a `75.1 m`; `1C` usa una deteccion sin accion a `67.1 m`, todavia fuera de `reaction_distance_eval_m=61 m`.
- Validacion del run: `accepted_types=["tower"]`, `clean_detection_count=9`, `valid_plan_count=1`, `valid_completion_count=1`, `failure_count=0`, evasion activa de progreso `0.2085` a `0.9412` antes de WP2.

## Terminos usados en leyendas

- `Planned flight path`: ruta nominal/global planificada del paper.
- `Actual UAS trajectory`: trayectoria ejecutada por el UAS; sustituye al termino interno `Flown path`.
- `Local A* evasion path`: ruta local generada por el planificador A*.
- `Active evasion segment`: tramo de la trayectoria ejecutada durante la evasion activa.
- `Dynamic reaction distance`: distancia de reaccion evaluada en el instante, distinta de `Base reaction distance`.
- `Detected tower obstacle` / `Tower obstacle`: obstaculo estatico tipo torre ya detectado.

## Limpieza de carpeta

- Esta carpeta contiene solo los artefactos actuales/finales y los scripts para regenerarlos.
- Las versiones historicas, contextos amplios/cercanos y capturas fuente antiguas no se conservan aqui para evitar confusion al sustituir figuras en LaTeX.
