from ultralytics import YOLO
import os

# Buscar el modelo
model_path = "yolo11n.pt"
if not os.path.exists(model_path):
    model_path = "3d_to_dataset_xabi/yolo11n.pt"

print(f"--- INSPECCIONANDO: {model_path} ---")

try:
    model = YOLO(model_path)
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
