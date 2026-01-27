import os
import time
import sys
import cv2
from ultralytics import YOLO
import numpy as np
from datetime import datetime

# --- CONFIGURACIÓN ---
IMAGE_PATH = "D:/ArduPilot_SITL_Install/Unreal/Saved/Screenshots/WindowsEditor/raw_capture.png"
MODEL_PATH = "D:/ArduPilot_SITL_Install/pipeline/weights/best.pt" # Ruta actualizada
DETECTION_CONFIDENCE_THRESHOLD = 0.4
POLLING_INTERVAL_S = 1.0

# --- UTILIDADES ---
def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [VISUAL-VERIFICATION] {msg}", flush=True)

class VisualVerificationSystem:
    def __init__(self):
        log("Iniciando Sistema de Verificación Visual v1.2")
        
        if not os.path.exists(MODEL_PATH):
            log(f"ERROR: No se encuentra el modelo en '{MODEL_PATH}'")
            sys.exit(1)
        
        log(f"Cargando modelo desde: {MODEL_PATH}")
        try:
            self.model = YOLO(MODEL_PATH)
            log("Modelo YOLO cargado exitosamente.")
        except Exception as e:
            log(f"ERROR: No se pudo cargar el modelo YOLO. {e}")
            sys.exit(1)

        self.last_mod_time = 0
        self.window_name = "YOLO Detection"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 800, 600)

    def run(self):
        log("Iniciando bucle de detección...")
        while True:
            try:
                if not os.path.exists(IMAGE_PATH):
                    log(f"Esperando a que se cree la imagen en: {IMAGE_PATH}")
                    time.sleep(1)
                    continue

                mod_time = os.path.getmtime(IMAGE_PATH)
                if mod_time == self.last_mod_time:
                    time.sleep(POLLING_INTERVAL_S)
                    continue
                
                self.last_mod_time = mod_time

                img = None
                for _ in range(5):
                    try:
                        img = cv2.imread(IMAGE_PATH)
                        if img is not None:
                            break
                    except Exception:
                        pass
                    time.sleep(0.05)

                if img is None:
                    log("Error: No se pudo leer la imagen.")
                    continue

                results = self.model(img, verbose=False, conf=DETECTION_CONFIDENCE_THRESHOLD)

                annotated_img = results[0].plot()

                cv2.imshow(self.window_name, annotated_img)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    log("Cerrando ventana de detección.")
                    break

            except Exception as e:
                log(f"CRASH EN BUCLE PRINCIPAL: {e}")
                cv2.destroyAllWindows()
                break
        
        cv2.destroyAllWindows()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'run_visual_test':
        visual_system = VisualVerificationSystem()
        visual_system.run()
    else:
        print("Este script es para verificación visual. Ejecútelo con el argumento 'run_visual_test'.")
        time.sleep(5)
