# Visor en vivo con slider de noise_scale (capa neural)

Lo que pediste: una ventana con un **slider** que sube/baja el realismo de
StreamDiffusionV2 sobre la vista de Unreal, en tiempo real. Arquitectura:

```
[Ventana Unreal] --PrintWindow--> live_viewer.py (Windows, venv, cv2)
       trackbar noise_scale ──┐         │ frame JPEG + noise_scale (HTTP)
                              ▼         ▼
                       live_server.py (WSL, ~/sdv2_venv, GPU 5090)
                       modelo SDV2 caliente · slider EN VIVO
                              │ frame restyled JPEG
                              ▼
                 vista lado a lado  INPUT | RESTYLED
```

El slider funciona **sin reiniciar**: `live_server.py` muta
`session.init_noise_scale` entre chunks, que es el término dominante (peso 0.9)
de `compute_noise_scale_and_step` en `streamv2v/inference.py`.

## Arrancar

1. **Servidor (WSL/GPU)** — doble clic / ejecutar `tmp\run_live_server.cmd`
   (deja esa ventana abierta; mantiene WSL vivo). Carga el modelo (~1-2 min).
2. **Cliente (Windows)** — con la ventana de Unreal abierta, ejecutar
   `tmp\run_live_viewer.cmd`. Mueve el trackbar; `[r]` reinicia sesión, `[q]` sale.

### Probar el servidor SIN Unreal
```
venv\Scripts\python.exe neural\live_viewer.py --video tmp\ejea_clip_input.mp4 --server http://127.0.0.1:9500
```

## Rendimiento esperado
Según el handoff: 480² da DiT ~28 fps, end-to-end ~12-18 fps. El servidor procesa
en chunks de 4 frames, así que ~1 de cada 4 POST devuelve imagen (el cliente
muestra el último restyled). Para más FPS: `--use_taehv` (descarga `taew2_1.pth`,
ver demo/README) y/o `--use_tensorrt`.

## ESTADO — honesto
- **NO probado end-to-end desde el sandbox** (no hay GPU/torch ni la ventana de
  Unreal aquí). Construido contra la API REAL verificada:
  `start_stream_session` / `run_stream_batch` / `compute_noise_scale_and_step`
  (streamv2v/inference.py) y el contrato de tensores de `demo/util.py`
  (RGB, `/127.5-1`, `(1,3,N,H,W)` bfloat16). Sintaxis compilada OK.
- Captura PrintWindow = misma que `tmp/printwindow_probe.py` (ya probada en runs D1).
- Riesgos a verificar en el 1er run real:
  1. `pip install fastapi uvicorn` en `~/sdv2_venv` (el .cmd lo intenta).
  2. Cambios bruscos del slider pueden tardar 1-2 chunks en verse (es esperado).
  3. Si el título de la ventana no es "AirTraffic (64-bit", pásalo con `--title`.
  4. El primer batch necesita 5 frames; los siguientes 4 (chunk del modelo).

## Pendiente (siguiente, del handoff)
- Inpaint generativo por detección (sabor 2b): "genera bien una torre donde hay
  una torre" con prompt por clase, en vez de pegar el objeto real. Más trabajo
  (ControlNet/inpaint). El modo detección-consciente actual (objeto REAL en bbox)
  ya está en `tmp/detaware_composite.py` + `tmp/ejea_detaware.mp4`.
