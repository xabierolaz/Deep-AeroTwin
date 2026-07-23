# Datos de vuelo real (Murillo de las Limas, Navarra)

Grabaciones de campo de julio 2026. Cada carpeta `*_VIDEO` contiene el vídeo
grabado a bordo y un JSON de sincronización; los `.bin` son logs dataflash de
ArduPilot del mismo día.

**Nota:** esta carpeta está untracked en git (datos, no código).

## Emparejamiento vídeo ↔ log

Verificado por timestamps (el JSON del vídeo da el instante Unix exacto del
primer frame; el `.bin` se empareja por ventana temporal):

| Vídeo | Inicio vídeo (del JSON) | Log ArduPilot | Notas |
|---|---|---|---|
| `M_20_1_VIDEO/` | 2026-07-06 07:40:30.164 Z | `2026-07-06 07-47-13.bin` | Toma 1 misión 20_1 |
| `M_20_1R_VIDEO/` | 2026-07-06 09:24:21.953 Z | `2026-07-06 09-29-05.bin` | Retoma 1 |
| `M_20_1RR_VIDEO/` | 2026-07-06 09:38:48.253 Z | `2026-07-06 09-43-41.bin` | Retoma 2 — **usada en la prueba Pipeline B** |
| `M_1_LiDAR+RGB_VIDEO/` | 2026-07-08 14:25:11.909 Z | `2026-07-08 14-32-36.bin` | Vuelo LiDAR+RGB (día 8) |

Ojo: el nombre del `.bin` es posterior al inicio del vídeo (~5 min) porque el
log se crea al armar/registrar y el vídeo empieza antes. El emparejamiento
correcto se hace SIEMPRE por ventana temporal, no por nombre.

## Formato del JSON de sincronización

```json
{
  "output_file": "/mnt/ssd/07/06/3/VIDEO/video_2026-07-06_09-38-48_253.mp4",
  "video_start_unix_ms": 1783330728253,
  "video_start_iso_local": "2026-07-06T09:38:48.253+00:00"
}
```

- `video_start_unix_ms`: instante Unix (ms) del primer frame del vídeo. Es la
  clave para alinear vídeo ↔ mensajes del log (`TimeUS`/GPS).
- No contiene fps, duración ni intrínsecos: se obtienen del propio mp4 (cv2).

## Datos medidos de M_20_1RR (prueba Pipeline B)

- Vídeo: 58.49 fps, 4049 frames, 69.2 s, 2160×3840 (vertical).
- Ventana vídeo: `[1783330728.3, 1783330797.5]` Unix s.
- Log `09-43-41.bin`: ventana `[1783330568.4, 1783331021.2]` (~453 s).
- El vídeo empieza 159.9 s dentro del log y termina antes que el log: solo se
  usa el tramo de vuelo que cubre el vídeo (requisito del experimento).

## `video_final.mp4` (vídeo de análisis del Pipeline B)

`video_final.mp4` es el recorte del vídeo M_20_1RR usado como entrada de análisis
en el Pipeline B. **Este procedimiento de recorte es interno al proyecto y no
debe aparecer en el paper publicado**; el paper solo declara sincronización por
contenido sin citar el valor del offset.

Procedimiento de recorte (documentado en `video_final.json`, autoritativo):

- **Vídeo fuente**: `M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4` (2160×3840
  vertical, 58.49 fps, 4049 frames, 69.2 s).
- **Corte temporal**: comienza ~12 s después del inicio del original (frame ~722
  del original @58.49 fps).
- **Corte espacial**: recorte vertical central del original a ratio ~4:3
  (2160×1620 → 1280×960), reduciendo alto manteniendo el ancho completo.
- **Formato de salida**: 1280×960 @ 10 fps, 239 frames, 23.9 s.

Verificación empírica (2026-07-23): cross-correlación del frame 0 de
`video_final.mp4` contra un barrido de frames del original con crop vertical
central 2160×1620 → 1280×960. Pico de correlación 0.90 en el frame 722 del
original (offset 12.34 s), consistente con el valor declarado en `video_final.json`.

### JSON de sincronización de `video_final`

- **`video_final.json`** — **AUTORITATIVO** (`video_start_unix_ms=1783330741109`,
  offset ~12.9 s). Verificado correcto.
- **`video_final_sync.json`** — **DEPRECADO / INCORRECTO**
  (`video_start_unix_ms=1783330744238`, offset +15.985 s). Desplazado ~3.1 s
  respecto al offset real. No usar.
- `trajectory_video_final.meta.json` se generó con el JSON erróneo; si se
  reutiliza, debe regenerarse con `video_final.json`.

## Uso

El replay determinista (vídeo + pose real sincronizada → Brain → Unreal SPPA)
vive en `tools/real_flight_replay/`. Ver `docs/` para el procedimiento.
