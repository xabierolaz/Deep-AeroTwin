@echo off
TITLE DEEP-AEROTWIN: PIPELINE B (DIGITAL TWIN)
echo ======================================================
echo    LAUNCHING PIPELINE B: REAL-TIME DIGITAL TWIN
echo ======================================================
echo.
echo [CONFIG] Setting PORCE_SYSTEM_MODE=REAL_TWIN
set "PORCE_SYSTEM_MODE=REAL_TWIN"

REM Configuracion especifica:
REM En modo Twin, quizas no queremos lanzar SITL si usamos un dron real.
REM Por ahora, usamos una version modificada del launch sequence.

set "PROJECT_ROOT=%~dp0"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

echo [0/4] Limpiando procesos antiguos...
taskkill /F /FI "WINDOWTITLE eq FLIGHT CONTROLLER*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISION SYSTEM*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VIZ RECORDER*" /T >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo [1/4] Iniciando MASTER LOG SERVER...
start "MASTER LOG (Twin)" cmd /k "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u log_server.py"

echo [2/4] Iniciando FLIGHT CONTROLLER (Brain)...
REM El Brain servirá /api/unreal/sync para que Unreal lo lea
start "FLIGHT CONTROLLER (Twin)" cmd /c "set PORCE_SYSTEM_MODE=REAL_TWIN && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN"

echo [3/4] Iniciando VISION SYSTEM (Eyes)...
REM En el futuro, esto leera RTSP. Por ahora usa captura de pantalla pero con parametros REAL_TWIN
start "VISION SYSTEM (Twin)" cmd /c "set PORCE_SYSTEM_MODE=REAL_TWIN && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u vision_system.py 2>&1 | python tee.py --prefix EYES"

echo [4/4] Iniciando VIZ RECORDER...
start "VIZ RECORDER (Twin)" cmd /c "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u viz_recorder.py"

echo.
echo [INFO] Pipeline B iniciado.
echo [INFO] Unreal debe estar configurado para consultar: http://127.0.0.1:8080/api/unreal/sync
echo.
pause
