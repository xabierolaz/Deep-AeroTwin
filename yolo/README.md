# YOLO (etiquetado + re-entreno)

Clases (3):
- `biker`
- `cow`
- `tower`

Carpetas:
- `yolo/source/` (imágenes a etiquetar, **ignorado por git**)
- `yolo/labels/` (anotaciones `.txt` en formato YOLO)
- `yolo/runs/` (salidas de entrenamiento, **ignorado por git**)
- `yolo/weights/` (pesos finales `.pt` que **sí** se suben a git)

## Etiquetar

1. Ejecuta `yolo/label_and_train_yolo.bat`
2. Elige opción `1`
3. Controles:
   - Ratón: arrastra para dibujar bounding box (se guarda solo)
   - Teclas: `n` siguiente, `p` anterior, `1/2/3` clase, `u` deshacer, `c` borrar todo, `q` salir

## Limpieza (recomendado)

Para más robustez (menos falsos positivos), elimina cajas extremadamente pequeñas:
- Ejecuta `yolo/label_and_train_yolo.bat`
- Opción `1b`

## Preparar dataset (recomendado)

Para entrenar con Ultralytics necesitas estructura `images/` + `labels/` por split:
- Ejecuta `yolo/label_and_train_yolo.bat`
- Opción `0` (crea `yolo/dataset/` + actualiza `yolo/dataset.yaml`)

## Negativos (recomendado)

Para reducir falsos positivos en la escena de Unreal, añade imágenes **sin** objetos:
- Importa imágenes negativas y crea labels vacías: `yolo/label_and_train_yolo.bat` → opción `0b`
- Luego regenera el dataset: opción `0`

## Entrenar

1. Ejecuta `yolo/label_and_train_yolo.bat`
2. Elige opción `2`
3. Al terminar, el script copia el `best.pt` a:
   - `yolo/weights/final.pt` (listo para subir a git)

## Ajustar umbral (recomendado)

Para minimizar falsos positivos en negativos, haz un sweep de `conf`:
- `yolo/label_and_train_yolo.bat` → opción `3`
  - Te da valores recomendados para `PORCE_VISION_DET_CONF` y `PORCE_VISION_PUBLISH_CONF`.
