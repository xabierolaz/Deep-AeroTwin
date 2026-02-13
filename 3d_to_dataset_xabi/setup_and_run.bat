@echo off
cd /d "%~dp0"

echo --- (Opcional) Instalar dependencias del repo...
echo     pip install -r ..\\pipeline\\requirements.txt
echo     (PyTorch debe estar instalado con soporte CUDA en tu sistema)

echo.
echo --- Generando Dataset Sintetico (esto puede tardar unos minutos)...
python generate_dataset.py --preview

echo.
echo --- Iniciando Entrenamiento YOLO...
python train_yolo.py

echo.
echo --- PROCESO COMPLETADO ---
