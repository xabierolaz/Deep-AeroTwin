from ultralytics import YOLO
import torch

def train():
    # Verificar GPU
    if torch.cuda.is_available():
        print(f"Usando GPU: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
    else:
        print("ADVERTENCIA: No se detectó GPU. El entrenamiento será lento.")

    # Cargar modelo pre-entrenado (nano version para velocidad)
    model = YOLO("yolo11n.pt")  # Usamos v11 nano, puedes cambiar a 'yolov8n.pt' si prefieres

    # Entrenar
    # workers=0 es importante en Windows para evitar errores de multiprocessing con dataloaders
    results = model.train(
        data="D:/ArduPilot_SITL_Install/3d_to_dataset_xabi/dataset.yaml", 
        epochs=50, 
        imgsz=640, 
        batch=16, 
        device=0,
        workers=0,
        patience=10,
        name="yolo_3d_experiment"
    )
    
    # Validar
    metrics = model.val()
    print(metrics.box.map)

    # Exportar a formato ONNX (opcional, útil para inferencia rápida después)
    # model.export(format="onnx")

if __name__ == '__main__':
    # Fix para Windows multiprocessing
    from multiprocessing import freeze_support
    freeze_support()
    train()
