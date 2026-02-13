from ultralytics import YOLO
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULTS = [
    REPO_ROOT / "pipeline" / "weights" / "yolo_3d_dome_v1_best.pt",
    REPO_ROOT / "yolo11n.pt",
    REPO_ROOT / "3d_to_dataset_xabi" / "yolo11n.pt",
]

# Allow passing an explicit model path: `python inspect_model.py path/to/model.pt`
model_path = None
if len(sys.argv) > 1 and sys.argv[1].strip():
    model_path = Path(sys.argv[1].strip())
else:
    for p in DEFAULTS:
        if p.exists():
            model_path = p
            break

if model_path is None:
    raise SystemExit("No se encontró ningún modelo (.pt).")

print(f"--- INSPECCIONANDO: {model_path} ---")

try:
    model = YOLO(str(model_path))
    print("\nCLASES ENTRENADAS:")
    print(model.names)
    
    # Verificacion rapida
    names = model.names
    if 'tower' in names.values():
        print("\n[VEREDICTO] -> Es tu modelo CUSTOM (Tiene 'tower').")
    elif 'cow' in names.values() and 'person' in names.values():
        print("\n[VEREDICTO] -> Es el modelo BASE de YOLO (COCO dataset).")
        print("Detectara vacas y personas, pero NO torres electricas especificamente.")
    else:
        print("\n[VEREDICTO] -> Modelo desconocido.")
        
except Exception as e:
    print(f"Error cargando modelo: {e}")
