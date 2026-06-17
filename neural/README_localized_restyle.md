# Restyle localizado por detección (AeroTwin)

En vez de pasar el restyle de StreamDiffusionV2 sobre **todo** el frame, se aplica
**solo donde YOLO detecta** un objeto (biker / cow / tower) y se funde con el
original en el resto. La intensidad se controla con sliders.

## Piezas

- `detect_clip.py` — corre el YOLO sobre un clip y escribe `detections.json`
  (cajas por frame, en píxeles del vídeo). **Corre en WSL con GPU** (necesita
  torch+ultralytics). Aquí en el sandbox no hay torch.
- `region_composite.py` — solo cv2/numpy, corre en cualquier sitio. Construye
  máscaras suavizadas (feather + dilatación) desde `detections.json` y compone
  el clip estilizado dentro de las regiones sobre el original.
- `localized_restyle_slider.html` — previsualización interactiva sobre un frame
  real del clip. Mueve los sliders y mira el composite al instante; abajo te
  genera el comando exacto de `region_composite.py` con esos valores. Puedes
  cargar tu `detections.json` real para usar las cajas de YOLO.

## Fórmula

Por píxel: `out = original + (estilizado − original) · m`, donde `m ∈ [0,1]`
es la máscara: dentro de cada caja vale la fuerza de su clase × `alpha`, con
suelo opcional `base-style` para todo el fondo, y borde difuminado (`feather`).

## Flujo

```bash
# 1) WSL/GPU — detectar
python neural/detect_clip.py --video tmp/ejea_clip_input.mp4 \
  --out neural/detections.json --conf 0.40

# 2) cualquier sitio — componer el restyle localizado
python neural/region_composite.py \
  --original tmp/ejea_clip_input.mp4 \
  --styled   neural/StreamDiffusionV2/poc_ejea/output_000.mp4 \
  --dets     neural/detections.json \
  --output   neural/ejea_localized.mp4 \
  --alpha 1.0 --base-style 0.0 --feather 25 --dilate 12 \
  --class-alpha cow=1.0,tower=0.9,biker=0.7
```

`--debug-mask` añade un `*_mask.mp4` para inspeccionar la máscara.

## Estado / limitaciones (verificado)

- `region_composite.py`: **probado** en el sandbox sobre 30 frames reales del
  clip de Ejea con cajas de ejemplo; máscara y blend correctos (ver
  `tmp/slider_frames/verify_*.png`).
- `detect_clip.py`: **no ejecutado aquí** (sin torch en el sandbox; el proxy
  bloquea la descarga). Lógica estándar de ultralytics; revísalo en el primer
  run de WSL.
- Esto es **compositing**: mete el frame ya estilizado (estilo global) dentro de
  las regiones detectadas. NO hace que la difusión "trabaje más" solo en el
  objeto (region-conditioning en espacio latente). Eso es el upgrade v2 y
  requiere tocar el bucle de inferencia de StreamDiffusionV2.
- El clip estilizado y el original deben corresponder frame a frame; hay 2
  frames de desfase (191 vs 189) — usa `--frame-offset` si notas drift.
