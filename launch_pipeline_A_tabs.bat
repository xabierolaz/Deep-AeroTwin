@echo off
setlocal enabledelayedexpansion
TITLE DEEP-AEROTWIN: PIPELINE A (SIMULATION) [TABS]

echo ======================================================
echo    LAUNCHING PIPELINE A: AUTONOMOUS SIMULATION (TABS)
echo ======================================================
echo.

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"

REM Config
set "PORCE_SYSTEM_MODE=SIMULATION"

REM Vision defaults for Unreal PIE (drone camera viewport).
if not defined PORCE_CAPTURE_WINDOW_TITLE set "PORCE_CAPTURE_WINDOW_TITLE=AirTraffic Preview"
if not defined PORCE_CAPTURE_EXPECT_WIDTH set "PORCE_CAPTURE_EXPECT_WIDTH=640"
if not defined PORCE_CAPTURE_EXPECT_HEIGHT set "PORCE_CAPTURE_EXPECT_HEIGHT=640"
if not defined PORCE_VISION_DEBUG_WINDOW set "PORCE_VISION_DEBUG_WINDOW=1"
if not defined PORCE_VISION_DEBUG_DOCK set "PORCE_VISION_DEBUG_DOCK=1"

REM Stop any previous run (works for windows or tabs)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>&1

REM Resolve Windows Terminal path
set "WT_EXE=wt.exe"
where wt.exe >nul 2>&1
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe" (
    set "WT_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"
  )
)

if not exist "%WT_EXE%" (
  echo [WARN] Windows Terminal (wt.exe) not found. Falling back to multi-window launcher.
  call "%PROJECT_ROOT%\launch_pipeline_A.bat"
  exit /b 0
)

REM Get WSL path to run_sitl.sh
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%PIPELINE_DIR%\run_sitl.sh"`) do set SITL_SCRIPT_PATH=%%a

REM Build python activation snippet for cmd.exe
set "PYENV="
if exist "%VENV_ACTIVATE%" set "PYENV=call \"%VENV_ACTIVATE%\" &&"

echo [OK] Opening Windows Terminal tabs...

REM One window, multiple tabs.
"%WT_EXE%" ^
  new-tab --title "MASTER LOG" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u log_server.py" ^
  ; new-tab --title "SITL (WSL)" cmd /k "wsl -e bash \"%SITL_SCRIPT_PATH%\"" ^
  ; new-tab --title "BRAIN (SIM)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200" ^
  ; new-tab --title "EYES (SIM)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200" ^
  ; new-tab --title "VIZ RECORDER" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u viz_recorder.py"

echo.
echo [OK] Tabs launched.
echo  - To stop everything: run tools\\stop_pipeline.ps1
echo.
exit /b 0

