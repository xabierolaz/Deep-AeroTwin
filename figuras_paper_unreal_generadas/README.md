# Figuras generadas para el paper Unreal/PORCE

Esta carpeta contiene las figuras compuestas pedidas en la conversacion.

## Archivos principales

- `figure_1_static_tower_multipanel.png`: Figura 1, caso estatico con torre, paneles 1A-1F, todos en vista cenital.
- `figure_1_panels/`: los seis paneles de Figura 1 por separado, recomendados para componer la figura final manualmente.
- `figure_2_moving_peloton_multipanel.png`: Figura 2, obstaculo movil tipo peloton/biker, paneles 2A-2C.
- `manifest.json`: trazabilidad de runs, timestamps y frames fuente.
- `generate_figure1_separate_panels.py`: regenerador de los seis paneles separados de Figura 1.

## Lectura critica

- `tools/make_viz_gif_manual.py` no crea el multipanel: crea un GIF a partir de `pipeline/logs/viz_frames/frame_*.png`.
- El multipanel historico se generaba en `generate_paper_assets.py`, funcion `build_six_stage_sequence_figure(...)`.
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
