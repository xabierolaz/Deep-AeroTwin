@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Deep-AeroTwin helper: label 3 classes + retrain YOLO (Ultralytics)
REM Classes: biker, cow, tower

cd /d "%~dp0"

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
set "YOLO_DIR=%~dp0"
set "CLASSES_FILE=%YOLO_DIR%yolo_classes.txt"
set "DEFAULT_DATA=%YOLO_DIR%dataset.yaml"
set "DEFAULT_PROJECT=%YOLO_DIR%runs"
set "WEIGHTS_DIR=%YOLO_DIR%weights"
set "SOURCE_DIR=%YOLO_DIR%source"
set "LABELS_DIR=%YOLO_DIR%labels"
set "YOLO_CFG_DIR=%REPO_ROOT%\pipeline\logs"

if not exist "%YOLO_CFG_DIR%" mkdir "%YOLO_CFG_DIR%" >nul 2>&1
set "YOLO_CONFIG_DIR=%YOLO_CFG_DIR%"

if not exist "%WEIGHTS_DIR%" mkdir "%WEIGHTS_DIR%" >nul 2>&1
if not exist "%LABELS_DIR%" mkdir "%LABELS_DIR%" >nul 2>&1
if not exist "%CLASSES_FILE%" (
  > "%CLASSES_FILE%" (
    echo biker
    echo cow
    echo tower
  )
)

:menu
echo.
echo ================================
echo Deep-AeroTwin - YOLO workflow
echo ================================
echo  [0] Preparar dataset (train/val/test)
echo  [0b] Importar negativos (labels vacias)
echo  [1] Etiquetar imagenes (simple)
echo  [1b] Limpiar cajas muy pequenas (robusto)
echo  [2] Entrenar YOLO (ultralytics)
echo  [3] Ajustar umbral (min FP)
echo  [Q] Salir
echo.
set "choice="
set /p "choice=Elige una opcion: "

if /i "%choice%"=="0" goto prep
if /i "%choice%"=="0b" goto importneg
if /i "%choice%"=="1" goto label
if /i "%choice%"=="1b" goto prune
if /i "%choice%"=="2" goto train
if /i "%choice%"=="3" goto tune
if /i "%choice%"=="q" goto :eof
if /i "%choice%"=="quit" goto :eof

echo Opcion no valida.
goto menu

:prep
echo.
echo Preparando dataset YOLO (split por secuencia para evitar leakage)...
python "%YOLO_DIR%prepare_dataset.py" --src "%SOURCE_DIR%" --labels "%LABELS_DIR%" --classes "%CLASSES_FILE%" --out "%YOLO_DIR%dataset" --yaml-out "%YOLO_DIR%dataset.yaml" --group-mode auto --bucket-size 25 --val 0.15 --test 0.15 --seed 1337 --clean
goto menu

:importneg
echo.
set "NEG_DIR="
set /p "NEG_DIR=Carpeta con imagenes negativas (ENTER = %REPO_ROOT%\\3d_to_dataset_xabi\\dataset\\false_neg): "
if "%NEG_DIR%"=="" set "NEG_DIR=%REPO_ROOT%\\3d_to_dataset_xabi\\dataset\\false_neg"
echo Importando negativos y creando labels vacias...
python "%YOLO_DIR%import_negatives.py" --from-dir "%NEG_DIR%" --to-source "%SOURCE_DIR%" --to-labels "%LABELS_DIR%" --prefix "neg_"
goto menu

:prune
echo.
echo Limpieza robusta: elimina cajas extremadamente pequenas.
echo Regla: remove si min(w_px,h_px) ^< 6 OR area_px ^< 64 (en imagen 640x640).
echo Se hace backup en yolo/labels_backup_* antes de modificar.
echo.
python "%YOLO_DIR%prune_tiny_labels.py" --src "%SOURCE_DIR%" --labels "%LABELS_DIR%" --classes "%CLASSES_FILE%" --min-dim 6 --min-area 64 --rule union
goto menu

:label
echo.
echo Etiquetador simple (OpenCV): next/prev + autosave.
echo Clases (1 por linea): "%CLASSES_FILE%"
echo Imagenes (por defecto): "%SOURCE_DIR%"
echo Labels (YOLO .txt): "%LABELS_DIR%"
echo.
set "IMG_DIR="
set /p "IMG_DIR=Carpeta de imagenes (ENTER = %SOURCE_DIR%): "
if "%IMG_DIR%"=="" set "IMG_DIR=%SOURCE_DIR%"

pushd "%YOLO_DIR%" >nul
python "%YOLO_DIR%annotate.py" --src "%IMG_DIR%" --labels "%LABELS_DIR%" --classes "%CLASSES_FILE%"
popd >nul
goto menu

:train
echo.
echo Entrenamiento YOLO (script: 3d_to_dataset_xabi\train_yolo.py)
echo.

set "DATA_YAML="
set "DEFAULT_DATA=%YOLO_DIR%dataset.yaml"
set /p "DATA_YAML=Ruta a dataset.yaml (ENTER = %DEFAULT_DATA%): "
if "%DATA_YAML%"=="" set "DATA_YAML=%DEFAULT_DATA%"

set "RUN_NAME="
set /p "RUN_NAME=Nombre de run (ENTER = yolo_unreal_v1): "
if "%RUN_NAME%"=="" set "RUN_NAME=yolo_unreal_v1"

set "EPOCHS="
set /p "EPOCHS=Epochs (ENTER = 200): "
if "%EPOCHS%"=="" set "EPOCHS=200"

set "IMGSZ="
set /p "IMGSZ=Img size (ENTER = 640): "
if "%IMGSZ%"=="" set "IMGSZ=640"

set "BATCH="
set /p "BATCH=Batch (ENTER = 16): "
if "%BATCH%"=="" set "BATCH=16"

set "DEVICE="
set /p "DEVICE=Device (ENTER = 0, CPU = cpu): "
if "%DEVICE%"=="" set "DEVICE=0"

set "BASE_MODEL="
set /p "BASE_MODEL=Base model (ENTER = yolo11n.pt): "
if "%BASE_MODEL%"=="" set "BASE_MODEL=yolo11n.pt"

set "PATIENCE="
set /p "PATIENCE=Patience (ENTER = 30): "
if "%PATIENCE%"=="" set "PATIENCE=30"

echo.
echo Running:
echo   python 3d_to_dataset_xabi\train_yolo.py --data "%DATA_YAML%" --name "%RUN_NAME%" --epochs %EPOCHS% --imgsz %IMGSZ% --batch %BATCH% --device "%DEVICE%" --model "%BASE_MODEL%" --project "%DEFAULT_PROJECT%" --patience %PATIENCE% --save-period 10
echo.

python "%REPO_ROOT%\3d_to_dataset_xabi\train_yolo.py" --data "%DATA_YAML%" --name "%RUN_NAME%" --epochs %EPOCHS% --imgsz %IMGSZ% --batch %BATCH% --device "%DEVICE%" --model "%BASE_MODEL%" --project "%DEFAULT_PROJECT%" --patience %PATIENCE% --save-period 10
set "rc=%ERRORLEVEL%"

echo.
if not "%rc%"=="0" (
  echo Training fallo (exit code %rc%).
  goto menu
)

echo OK.
set "BEST_PT=%DEFAULT_PROJECT%\%RUN_NAME%\weights\best.pt"
if exist "%BEST_PT%" (
  copy /Y "%BEST_PT%" "%WEIGHTS_DIR%\%RUN_NAME%_best.pt" >nul
  copy /Y "%BEST_PT%" "%WEIGHTS_DIR%\final.pt" >nul
  echo Pesos:
  echo   "%BEST_PT%"
  echo Copias (para subir a git):
  echo   "%WEIGHTS_DIR%\%RUN_NAME%_best.pt"
  echo   "%WEIGHTS_DIR%\final.pt"
) else (
  echo WARNING: no se encontro "%BEST_PT%".
)
echo.
echo Para usarlo en la pipeline:
echo   set PORCE_YOLO_MODEL="%WEIGHTS_DIR%\final.pt"
echo.
goto menu

:tune
echo.
set "WEIGHTS="
set /p "WEIGHTS=Ruta a pesos (ENTER = %WEIGHTS_DIR%final.pt): "
if "%WEIGHTS%"=="" set "WEIGHTS=%WEIGHTS_DIR%final.pt"
if not exist "%WEIGHTS%" (
  echo No existe: "%WEIGHTS%"
  goto menu
)

set "TUNE_DEVICE="
set /p "TUNE_DEVICE=Device para evaluar (ENTER = 0, CPU = cpu): "
if "%TUNE_DEVICE%"=="" set "TUNE_DEVICE=0"

echo.
echo Ajustando umbral para minimizar falsos positivos (usa yolo/dataset/)...
python "%YOLO_DIR%tune_conf.py" --weights "%WEIGHTS%" --dataset "%YOLO_DIR%dataset" --imgsz 640 --device "%TUNE_DEVICE%" --pred-batch 8 --min-conf 0.05 --max-conf 0.40 --step 0.05 --strict-zero-fp
goto menu
