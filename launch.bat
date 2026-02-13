@echo off
setlocal enabledelayedexpansion
TITLE DEEP-AEROTWIN: MASTER SYSTEM LAUNCHER

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
set "WINDOW_TITLE_SUFFIX=(%PORCE_SYSTEM_MODE%)"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [CONFIG] PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE%
echo.

REM ============================================================================
REM 0. CLEANUP (SAFE)
REM ============================================================================
echo [0/5] Cleaning previous launcher windows...
taskkill /F /FI "WINDOWTITLE eq MASTER LOG*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FLIGHT CONTROLLER*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISION SYSTEM*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ArduPilot SITL*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VIZ RECORDER*" /T >nul 2>&1
REM NOTE: do NOT kill all python.exe processes; that is unsafe on dev machines.
REM Kill SITL inside WSL (may affect other SITL instances).
wsl -e pkill -9 -f arducopter >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"
timeout /t 1 /nobreak >nul
echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 1. MASTER LOG SERVER
REM ============================================================================
echo [1/5] Starting MASTER LOG SERVER...
if exist "%VENV_ACTIVATE%" (
    start "MASTER LOG (Do Not Close)" cmd /k "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u log_server.py"
) else (
    echo [WARN] venv not found at "%VENV_ACTIVATE%". Using system Python.
    start "MASTER LOG (Do Not Close)" cmd /k "cd "%PROJECT_ROOT%\pipeline" && python -u log_server.py"
)
timeout /t 2 /nobreak >nul

REM ============================================================================
REM 2. SITL (WSL)
REM ============================================================================
echo [2/5] Starting SITL (WSL)...
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%PROJECT_ROOT%\pipeline\run_sitl.sh"`) do set SITL_SCRIPT_PATH=%%a
start "ArduPilot SITL" cmd /k "wsl -e bash "%SITL_SCRIPT_PATH%""

REM ============================================================================
REM 3. FLIGHT CONTROLLER (Brain)
REM ============================================================================
echo [3/5] Starting FLIGHT CONTROLLER...
if exist "%VENV_ACTIVATE%" (
    start "FLIGHT CONTROLLER %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200"
) else (
    start "FLIGHT CONTROLLER %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd "%PROJECT_ROOT%\pipeline" && python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200"
)

REM ============================================================================
REM 4. VISION SYSTEM (Eyes)
REM ============================================================================
echo [4/5] Starting VISION SYSTEM...
timeout /t 1 /nobreak >nul
if exist "%VENV_ACTIVATE%" (
    start "VISION SYSTEM %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200"
) else (
    start "VISION SYSTEM %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && cd "%PROJECT_ROOT%\pipeline" && python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200"
)

REM ============================================================================
REM 5. VIZ RECORDER
REM ============================================================================
echo [5/5] Starting VIZ RECORDER...
if exist "%VENV_ACTIVATE%" (
    start "VIZ RECORDER" cmd /c "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u viz_recorder.py"
) else (
    start "VIZ RECORDER" cmd /c "cd "%PROJECT_ROOT%\pipeline" && python -u viz_recorder.py"
)

echo.
echo [OK] System launched.
echo.
echo  - Master log: pipeline\\logs\\SYSTEM_ALL.log
echo  - Viz frames: pipeline\\logs\\viz_frames
echo.
pause
