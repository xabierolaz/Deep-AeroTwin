@echo off
setlocal
TITLE DEEP-AEROTWIN: PIPELINE A LAUNCHER (UNIFIED)

REM ============================================================================
REM CONFIG
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

REM Shared defaults (single source in pipeline\porce_defaults.env)
call "%PROJECT_ROOT%\tools\load_porce_defaults.bat" "%PROJECT_ROOT%\pipeline\porce_defaults.env"
if errorlevel 1 (
  echo [ERROR] Failed to load shared defaults from pipeline\porce_defaults.env
  exit /b 5
)

if not defined PORCE_OBSTACLE_TOKEN_REQUIRED set "PORCE_OBSTACLE_TOKEN_REQUIRED=1"
if /I not "%PORCE_OBSTACLE_TOKEN_REQUIRED%"=="0" if not defined PORCE_OBSTACLE_TOKEN (
  for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\")"') do set "PORCE_OBSTACLE_TOKEN=%%i"
)

if not defined PORCE_AUDIT_STAMP (
  for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "PORCE_AUDIT_STAMP=%%i"
)
if defined PORCE_AUDIT_ROOT (
  if /I "%PORCE_AUDIT_ROOT%"=="%PROJECT_ROOT%\pipeline\logs\zero_trust" (
    set "PORCE_AUDIT_ROOT=%PROJECT_ROOT%\pipeline\logs\zero_trust\%PORCE_AUDIT_STAMP%"
  )
) else (
  if not defined PORCE_AUDIT_ROOT set "PORCE_AUDIT_ROOT=%PROJECT_ROOT%\pipeline\logs\zero_trust\%PORCE_AUDIT_STAMP%"
)
if not exist "%PORCE_AUDIT_ROOT%" mkdir "%PORCE_AUDIT_ROOT%"

if not defined PORCE_AUDIT_ENABLE set "PORCE_AUDIT_ENABLE=1"
if not defined PORCE_CONFIG_BANNER set "PORCE_CONFIG_BANNER=1"

REM Session-scoped master log file (avoid overwriting between runs).
if not defined PORCE_LOG_SERVER_FILE set "PORCE_LOG_SERVER_FILE=%PORCE_AUDIT_ROOT%\SYSTEM_ALL.log"

REM Make it easy to find the latest run folder.
if not exist "%PROJECT_ROOT%\pipeline\logs\zero_trust" mkdir "%PROJECT_ROOT%\pipeline\logs\zero_trust" >nul 2>&1
echo %PORCE_AUDIT_ROOT%>"%PROJECT_ROOT%\pipeline\logs\zero_trust\LATEST_RUN.txt"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\write_run_info.ps1" -OutputDir "%PORCE_AUDIT_ROOT%" -ProjectRoot "%PROJECT_ROOT%" >nul 2>&1
set "PORCE_SYSTEM_MODE=SIMULATION"
set "PORCE_VISION_DEBUG_WINDOW=1"
set "PORCE_VISION_DEBUG_DOCK=1"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [MODE] Unified mode: Pipeline A (SIMULATION)
echo [SECURITY] PORCE_OBSTACLE_TOKEN_REQUIRED=%PORCE_OBSTACLE_TOKEN_REQUIRED% token_prefix=%PORCE_OBSTACLE_TOKEN:~0,8%...
echo [AUDIT] PORCE_AUDIT_ROOT=%PORCE_AUDIT_ROOT%
echo.

REM ============================================================================
REM 0. CLEANUP (SAFE)
REM ============================================================================
echo [0/3] Cleaning previous pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"

REM timeout.exe fails when stdin is redirected; use PowerShell sleep (works everywhere).
powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1

echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 1. WINDOWS TERMINAL (TABS)
REM ============================================================================
echo [1/3] Opening tabs in Windows Terminal...
if /I "%PORCE_FORCE_CMD_WINDOWS%"=="1" (
  echo [INFO] PORCE_FORCE_CMD_WINDOWS=1, forcing cmd fallback windows...
  call :fallback_cmd_tabs
  if errorlevel 1 (
    echo [ERROR] Failed to launch fallback component windows.
    exit /b 4
  )
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\launch_tabs.ps1" -ProjectRoot "%PROJECT_ROOT%"
  if errorlevel 1 (
    echo [WARN] Tab launcher failed. Falling back to cmd windows...
    call :fallback_cmd_tabs
    if errorlevel 1 (
      echo [ERROR] Failed to launch fallback component windows.
      exit /b 4
    )
  )
)

echo.
echo [OK] Tabs launched.
echo  - Master log: %PORCE_LOG_SERVER_FILE%
echo  - Viz frames: pipeline\\logs\\viz_frames
echo  - Validate latest run: tools\\validate_latest_run.bat
echo  - Stop everything: powershell -NoProfile -ExecutionPolicy Bypass -File tools\\stop_pipeline.ps1
echo.
exit /b 0

:fallback_cmd_tabs
set "VENV_ACT=%PROJECT_ROOT%\venv\Scripts\activate.bat"
set "PYENV="
if exist "%VENV_ACT%" (
  set "PYENV=call \"%VENV_ACT%\" && "
) else (
  echo [WARN] venv not found at: %VENV_ACT% ; using system python
)

start "MASTER LOG" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u log_server.py"
start "SITL (WSL)" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV%wsl --cd \"%PIPELINE_DIR%\" --exec bash run_sitl.sh 2>&1 | python tee.py --prefix \"SITL\" --cap-lines %PORCE_TEE_CAP_LINES%"
start "BRAIN (SIM)" cmd /k "set PORCE_SYSTEM_MODE=SIMULATION && cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u flight_controller.py 2>&1 | python tee.py --prefix \"%PORCE_TEE_PREFIX_BRAIN%\" --cap-lines %PORCE_TEE_CAP_LINES%"
start "EYES (SIM)" cmd /k "set PORCE_SYSTEM_MODE=SIMULATION && set PORCE_VISION_DEBUG_WINDOW=1 && set PORCE_VISION_DEBUG_DOCK=1 && cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u vision_system.py 2>&1 | python tee.py --prefix \"%PORCE_TEE_PREFIX_EYES%\" --cap-lines %PORCE_TEE_CAP_LINES%"
start "VIZ RECORDER" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u viz_recorder.py 2>&1 | python tee.py --prefix \"VIZ\" --cap-lines %PORCE_TEE_CAP_LINES%"
exit /b 0
