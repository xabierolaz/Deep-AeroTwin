# Figuras generadas para el paper Unreal/PORCE

Esta carpeta contiene las figuras compuestas pedidas en la conversacion.

## Archivos principales

- `figure_1_static_tower_multipanel.png`: Figura 1, caso estatico con torre, paneles 1A-1F, todos en vista cenital.
- `figure_1_panels/`: los seis paneles de Figura 1 por separado, recomendados para componer la figura final manualmente.
- `figure_2_moving_peloton_multipanel.png`: Figura 2 provisional, obstaculo movil tipo peloton/biker, paneles 2A-2C.
- `manifest.json`: trazabilidad de runs, timestamps y frames fuente.
- `generate_figure1_separate_panels.py`: regenerador de los seis paneles separados de Figura 1.
- `reference_historical_porce_six_stage_sequence.png`: figura historica de seis paneles generada por `generate_paper_assets.py`.
- `reference_historical_porce_yolo_future_overlay.png`: figura historica de overlay YOLO/futuro.

## Lectura critica

- `tools/make_viz_gif_manual.py` no crea el multipanel: crea un GIF a partir de `pipeline/logs/viz_frames/frame_*.png`.
- El multipanel historico se generaba en `generate_paper_assets.py`, funcion `build_six_stage_sequence_figure(...)`.
- La Figura 1 generada aqui usa un episodio continuo con torre del run `20260220_112052`; todos los paneles corresponden a la misma torre y se ordenan como secuencia temporal.
- Orden activo de lectura: `1A` navegacion nominal, `1B` deteccion sin accion, `1C` detalle de deteccion con radios, `1D` evasion activa, `1E` detalle/grid de evasion, `1F` resumen final de ruta.
- Decision actual: los seis paneles de Figura 1 deben ser cenitales/top-down, con el grid real `81 x 81` superpuesto y deteccion unica de torre. `1B` y `1C` ya no deben ser capturas oblicuas Unreal/HUD.
- Los seis paneles usan el mismo encuadre fijo activo: eje X `[-200, 400]` m y eje Y `[-400, 200]` m, con las mismas etiquetas `East (m)` y `North (m)`. Es un encuadre cuadrado `1:1` centrado para aprovechar la diagonal `WP0/WP1` a `WP4`.
- La version amplia anterior se conserva como contexto en `figure_1_panels_wide_context/`, `figure_1_static_tower_multipanel_wide_context.png` y `figure_1_panels_contact_sheet_wide_context.png`.
- La version cercana anterior se conserva como contexto en `figure_1_panels_close_context/`, `figure_1_static_tower_multipanel_close_context.png` y `figure_1_panels_contact_sheet_close_context.png`.
