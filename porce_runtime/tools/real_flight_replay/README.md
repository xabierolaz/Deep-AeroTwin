# tools/real_flight_replay

Replay determinista del vuelo real M_20_1RR (Murillo de las Limas, Navarra):
video + pose sincronizada del `.bin` → deteccion → proyeccion al mundo.

## Motor de proyeccion unificado (GeoProjector)

Los scripts de proyeccion usan el **motor canonico `GeoProjector`** de Pipeline A
(`pipeline/geo_projector.py`), no matemática duplicada. Esto asegura que
Pipeline A (simulacion) y Pipeline B (vuelo real) proyecten con la misma
geometria pinhole + rotacion body->NED.

| Script | Motor | Deteccion | Salida |
|---|---|---|---|
| `infer_tower_position.py` | `GeoProjector` (`bbox_to_ground_footprint_m` + `pixel_to_ground_offset_m`) | YOLOE-26s-seg bbox + mascara | `experiments/tower_position_inference_*/` |
| `analyze_video_final_gt.py` | `GeoProjector` (`pixel_to_ground_offset_m`) | detecciones preexistentes | `experiments/sppa_real_stream_wave/20260721_video_final_gt_study/` |
| `fit_camera_mount.py` | `GeoProjector._rot_*` (delegadas) | correspondencias manuales | `out/camera_mount_fit.json` |

### Excepcion: `fit_camera_mount.py`

Este script hace **reproyeccion inversa** (world->pixel) para calibrar el mount,
la operacion opuesta a `GeoProjector` (pixel->world). `GeoProjector` no expone el
sentido inverso, por lo que `fit_camera_mount.py` mantiene su propia funcion
`project()`. Sin embargo, las **rotaciones** (`_rot_x/_rot_y/_rot_z`) y la matriz
de alineacion (`A_BC` == `R_body_cam_align`) se delegan a `GeoProjector` para
garantizar la misma convencion, y `R_EARTH` esta alineado a 6371000.0.

## Mount de camara (importante)

**`out/camera_mount_fit.json` (v3, AUTORITATIVO)**: `mount_yaw=22,
mount_pitch=-24`, recalibrado 2026-07-23 por minimizacion de mediana de error
contra GT PNOA sobre 100 detecciones de torre, usando el offset de video
correcto (+12.856s). Usar este mount.

El mount legacy (yaw=155, pitch=-37) se calibro con el offset de video ERRONEO
(+15.985s) y producia una proyeccion invertida ~131 grados. Esta deprecado.

`fit_camera_mount.py` escribe por defecto en `tools/real_flight_replay/camera_mount_fit.json`
(sin `out/`); esa salida es del calibrador de reproyeccion y **no debe usarse**
(para eso esta el `out/camera_mount_fit.json` v3).

## Coordenadas del dron

`out/drone_coords_from_bin.csv`: coordenadas zero-trust extraidas directamente
del `.bin` (mensajes GPS + ATT), interpoladas a los 239 frames al offset correcto.
Fuente autoritativa de la trayectoria del dron.

## Flujo tipico

```bash
# 1. Extraer coordenadas reales del .bin
python tools/real_flight_replay/extract_trajectory.py \
    --bin "papers/pipeline_a_telemetry/data/2026-07-06 09-43-41.bin" \
    --video "papers/pipeline_a_telemetry/data/video_final.mp4" \
    --video-json "papers/pipeline_a_telemetry/data/video_final.json" \
    --out-csv out/drone_coords_from_bin.csv

# 2. Inferir posicion de torres (deteccion + mascara + proyeccion GeoProjector)
python tools/real_flight_replay/infer_tower_position.py

# 3. (opcional) estudio GT contra PNOA
python tools/real_flight_replay/analyze_video_final_gt.py
```
