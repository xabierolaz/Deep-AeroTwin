@echo off
cd /d "%~dp0"
echo "Lanzando ventana de verificacion visual de YOLO..."
echo "Presione 'q' en la ventana de la imagen para cerrar."

REM Ejecutar el script de Python (usa el Python activo en PATH/venv)
python pipeline\visual_verification.py run_visual_test

echo "Ventana cerrada."
pause
