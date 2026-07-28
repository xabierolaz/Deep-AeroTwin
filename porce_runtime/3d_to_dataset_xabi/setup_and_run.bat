@echo off
cd /d "%~dp0"

echo --- Activando entorno virtual...
call venv\Scripts\activate

echo.
echo --- Instalando PyTorch con soporte CUDA 12.4 (RTX 5090 Ready)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

echo.
echo --- Instalando librerias de renderizado y YOLO...
pip install ultralytics trimesh pyrender scipy Pillow opencv-python mapbox_earcut

echo.
echo --- Generando Dataset Sintetico (esto puede tardar unos minutos)...
python generate_dataset.py

echo.
echo --- Iniciando Entrenamiento YOLO...
python train_yolo.py

echo.
echo --- PROCESO COMPLETADO ---
