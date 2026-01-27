@echo off
echo "Lanzando ventana de verificacion visual de YOLO..."
echo "Presione 'q' en la ventana de la imagen para cerrar."

REM Ejecutar el script de Python usando el venv especifico del proyecto
D:\ArduPilot_SITL_Install\3d_to_dataset_xabi\venv\Scripts\python.exe D:\ArduPilot_SITL_Install\pipeline\visual_verification.py run_visual_test

echo "Ventana cerrada."
pause
