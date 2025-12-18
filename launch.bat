@echo off
setlocal enabledelayedexpansion
TITLE ArduPilot Pipeline Launcher

REM ============================================================================
REM CONFIGURACION
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
set "PORCE_SYSTEM_MODE=SIMULATION"
set "WINDOW_TITLE_SUFFIX=(%PORCE_SYSTEM_MODE%)"

if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [CONFIG] Modo: %PORCE_SYSTEM_MODE%
echo.

REM ============================================================================
REM 0. LIMPIEZA
REM ============================================================================
echo [0/5] Limpiando procesos...
taskkill /F /FI "WINDOWTITLE eq MASTER LOG*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FLIGHT CONTROLLER*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISION SYSTEM*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ArduPilot SITL*" /T >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
wsl -e pkill -9 -f arducopter >nul 2>&1
wsl -e pkill -9 -f python3 >nul 2>&1
timeout /t 1 /nobreak >nul
echo [OK] Limpio.

REM ============================================================================
REM 1. MASTER LOG SERVER
REM ============================================================================
echo [1/5] Iniciando MASTER LOG SERVER...
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] Entorno virtual no encontrado.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\pipeline\logs" mkdir "%PROJECT_ROOT%\pipeline\logs"

start "MASTER LOG (Do Not Close)" cmd /k "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u log_server.py"

REM Esperar a que el servidor TCP levante
timeout /t 2 /nobreak >nul

REM ============================================================================
REM 2. SITL (WSL)
REM ============================================================================
echo [2/5] Iniciando SITL (WSL)...
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%PROJECT_ROOT%\pipeline\run_sitl.sh"`) do set SITL_SCRIPT_PATH=%%a
start "ArduPilot SITL" cmd /k "wsl -e bash "%SITL_SCRIPT_PATH%""

REM ============================================================================
REM 3. FLIGHT CONTROLLER (Brain)
REM ============================================================================
echo [3/5] Iniciando FLIGHT CONTROLLER...
start "FLIGHT CONTROLLER %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200"

REM ============================================================================
REM 4. VISION SYSTEM (Eyes)
REM ============================================================================
echo [4/5] Iniciando VISION SYSTEM...
timeout /t 1 /nobreak >nul
start "VISION SYSTEM %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200"

echo.
echo [OK] Sistema Lanzado.
echo.
echo  - Ventana "MASTER LOG": Muestra todos los logs en tiempo real.
echo  - Archivo Maestro: pipeline\logs\SYSTEM_ALL.log
echo.
pause