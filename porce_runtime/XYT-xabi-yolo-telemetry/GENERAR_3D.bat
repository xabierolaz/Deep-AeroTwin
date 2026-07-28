@echo off
setlocal

set "ROOT=%~dp0"
set "OUTDIR=%ROOT:~0,-1%"
set "WORD=%~1"
set "INTERACTIVE=0"

if "%WORD%"=="" (
    set "INTERACTIVE=1"
    set /p WORD=Palabra 3D ^(cow/biker/tree/car/truck^):
)

if "%WORD%"=="" (
    echo No has escrito ninguna palabra.
    pause
    exit /b 1
)

python "%ROOT%xyt_generate_3d.py" "%WORD%" --out-dir "%OUTDIR%"
if errorlevel 1 (
    echo.
    echo Error generando el modelo. Comprueba que Python esta instalado.
    pause
    exit /b 1
)

echo.
echo Listo: "%OUTDIR%\%WORD%.obj"
if "%INTERACTIVE%"=="1" pause
