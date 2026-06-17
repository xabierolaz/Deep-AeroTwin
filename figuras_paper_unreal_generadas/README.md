# Figuras generadas para el paper Unreal/PORCE

Esta carpeta contiene las figuras compuestas pedidas en la conversacion.

## Archivos principales

- `figure_1_static_tower_multipanel.png`: Figura 1, caso estatico con torre, paneles 1A-1F.
- `figure_1_panels/`: los seis paneles de Figura 1 por separado, recomendados para componer la figura final manualmente.
- `figure_2_moving_peloton_multipanel.png`: Figura 2 provisional, obstaculo movil tipo peloton/biker, paneles 2A-2C.
- `manifest.json`: trazabilidad de runs, timestamps y frames fuente.
- `generate_figure1_separate_panels.py`: regenerador de los seis paneles separados de Figura 1.
- `reference_historical_porce_six_stage_sequence.png`: figura historica de seis paneles generada por `generate_paper_assets.py`.
- `reference_historical_porce_yolo_future_overlay.png`: figura historica de overlay YOLO/futuro.

## Lectura critica

- `tools/make_viz_gif_manual.py` no crea el multipanel: crea un GIF a partir de `pipeline/logs/viz_frames/frame_*.png`.
- El multipanel historico se generaba en `generate_paper_assets.py`, funcion `build_six_stage_sequence_figure(...)`.
- La Figura 1 generada aqui usa un episodio con torre del run disponible `20260218_234222`; 1D resume la ventana de evasion de torre dentro de ese run, no una mision nueva garantizada como solo-torre.
- Las capturas Unreal de `1B` y `1C` deben ir con HUD/bounding boxes de deteccion. Esta decision queda cerrada como requisito visual de la Figura 1.
