@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
pushd "%PROJECT_ROOT%"

if "%~1"=="" (
  python tools\make_viz_gif_manual.py --latest-run --fps 0 --width 0
) else (
  python tools\make_viz_gif_manual.py --latest-run --fps 0 --width 0 --out "%~1"
)

set "RC=%ERRORLEVEL%"
echo.
if %RC% EQU 0 (
  echo [OK] GIF generado.
) else (
  echo [ERROR] Fallo al generar GIF ^(code=%RC%^).
)
popd
pause
exit /b %RC%
