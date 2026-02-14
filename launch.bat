@echo off
setlocal enabledelayedexpansion
TITLE DEEP-AEROTWIN: LAUNCHER (TABS)

REM ============================================================================
REM CONFIG
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"

REM Respect caller mode (launch_pipeline_A/B), default to SIMULATION.
if not defined PORCE_SYSTEM_MODE set "PORCE_SYSTEM_MODE=SIMULATION"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [CONFIG] PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE%
echo.

REM ============================================================================
REM 0. CLEANUP (SAFE)
REM ============================================================================
echo [0/3] Cleaning previous pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"
timeout /t 1 /nobreak >nul
echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 1. WINDOWS TERMINAL
REM ============================================================================
set "WT_EXE="
where wt.exe >nul 2>&1
if not errorlevel 1 set "WT_EXE=wt.exe"
if not defined WT_EXE (
  if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe" (
    set "WT_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"
  )
)

if not defined WT_EXE (
  echo [ERROR] Windows Terminal (wt.exe) not found. Install Windows Terminal and retry.
  exit /b 2
)

REM WSL path to run_sitl.sh
set "SITL_SCRIPT_PATH="
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%PIPELINE_DIR%\run_sitl.sh"`) do set SITL_SCRIPT_PATH=%%a

REM Build python activation snippet for cmd.exe
set "PYENV="
if exist "%VENV_ACTIVATE%" (
  set "PYENV=call \"%VENV_ACTIVATE%\" &&"
) else (
  echo [WARN] venv not found at "%VENV_ACTIVATE%". Using system Python.
)

echo [1/3] Opening tabs in Windows Terminal...

REM One window, multiple tabs.
REM NOTE: We keep the tabs open (/k) so you can see logs and exit codes.
if /i "%PORCE_SYSTEM_MODE%"=="SIMULATION" (
  "%WT_EXE%" ^
    new-tab --title "MASTER LOG" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u log_server.py" ^
    ; new-tab --title "SITL (WSL)" cmd /k "wsl -e bash \"%SITL_SCRIPT_PATH%\"" ^
    ; new-tab --title "BRAIN (SIM)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200" ^
    ; new-tab --title "EYES (SIM)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200" ^
    ; new-tab --title "VIZ RECORDER" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u viz_recorder.py"
) else (
  "%WT_EXE%" ^
    new-tab --title "MASTER LOG" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u log_server.py" ^
    ; new-tab --title "BRAIN (TWIN)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200" ^
    ; new-tab --title "EYES (TWIN)" cmd /k "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200" ^
    ; new-tab --title "VIZ RECORDER" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV% python -u viz_recorder.py"
)

echo.
echo [OK] Tabs launched.
echo  - Master log: pipeline\\logs\\SYSTEM_ALL.log
echo  - Viz frames: pipeline\\logs\\viz_frames
echo  - Stop everything: powershell -NoProfile -ExecutionPolicy Bypass -File tools\\stop_pipeline.ps1
echo.
exit /b 0

