@echo off
setlocal
TITLE DEEP-AEROTWIN: PIPELINE B LAUNCHER (REAL_TWIN)

REM ============================================================================
REM CONFIG
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

set "PORCE_DEFAULTS_FORCE=1"
call "%PROJECT_ROOT%\tools\load_porce_defaults.bat" "%PROJECT_ROOT%\pipeline\porce_defaults.env" "%PORCE_DEFAULTS_FORCE%"
if errorlevel 1 (
  echo [ERROR] Failed to load shared defaults from pipeline\porce_defaults.env
  exit /b 5
)
call "%PROJECT_ROOT%\tools\load_porce_defaults.bat" "%PROJECT_ROOT%\pipeline\b_porce_defaults.env" "1"
if errorlevel 1 (
  echo [ERROR] Failed to load Pipeline B defaults from pipeline\b_porce_defaults.env
  exit /b 5
)

if not exist "%PROJECT_ROOT%\pipeline\logs\zero_trust" mkdir "%PROJECT_ROOT%\pipeline\logs\zero_trust" >nul 2>&1
set "PORCE_OBSTACLE_TOKEN_FILE=%PROJECT_ROOT%\pipeline\logs\zero_trust\OBSTACLE_TOKEN.txt"

if not defined PORCE_OBSTACLE_TOKEN_REQUIRED set "PORCE_OBSTACLE_TOKEN_REQUIRED=1"
if /I not "%PORCE_OBSTACLE_TOKEN_REQUIRED%"=="0" (
  if not defined PORCE_OBSTACLE_TOKEN if exist "%PORCE_OBSTACLE_TOKEN_FILE%" (
    set /p PORCE_OBSTACLE_TOKEN=<"%PORCE_OBSTACLE_TOKEN_FILE%"
  )
  if not defined PORCE_OBSTACLE_TOKEN (
    for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\")"') do set "PORCE_OBSTACLE_TOKEN=%%i"
  )
  if defined PORCE_OBSTACLE_TOKEN (
    >"%PORCE_OBSTACLE_TOKEN_FILE%" echo %PORCE_OBSTACLE_TOKEN%
  )
)
if not defined PORCE_UNREAL_TELEMETRY_TOKEN set "PORCE_UNREAL_TELEMETRY_TOKEN=%PORCE_OBSTACLE_TOKEN%"
if not defined PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED set "PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED=%PORCE_OBSTACLE_TOKEN_REQUIRED%"

if not defined PORCE_AUDIT_STAMP (
  for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "PORCE_AUDIT_STAMP=%%i"
)
if defined PORCE_AUDIT_ROOT (
  if /I "%PORCE_AUDIT_ROOT%"=="%PROJECT_ROOT%\pipeline\logs\zero_trust" (
    set "PORCE_AUDIT_ROOT=%PROJECT_ROOT%\pipeline\logs\zero_trust\pipeline_b\%PORCE_AUDIT_STAMP%"
  )
) else (
  set "PORCE_AUDIT_ROOT=%PROJECT_ROOT%\pipeline\logs\zero_trust\pipeline_b\%PORCE_AUDIT_STAMP%"
)
if not exist "%PORCE_AUDIT_ROOT%" mkdir "%PORCE_AUDIT_ROOT%"

if not defined PORCE_AUDIT_ENABLE set "PORCE_AUDIT_ENABLE=1"
if not defined PORCE_CONFIG_BANNER set "PORCE_CONFIG_BANNER=1"

if not defined PORCE_LOG_SERVER_FILE set "PORCE_LOG_SERVER_FILE=%PORCE_AUDIT_ROOT%\SYSTEM_ALL.log"

echo %PORCE_AUDIT_ROOT%>"%PROJECT_ROOT%\pipeline\logs\zero_trust\LATEST_RUN_B.txt"

set "PORCE_SYSTEM_MODE=REAL_TWIN"
if not defined PORCE_MOCK_MAVLINK set "PORCE_MOCK_MAVLINK=1"
if not defined PORCE_ENABLE_EVASION set "PORCE_ENABLE_EVASION=0"
if not defined PORCE_VISION_SOURCE set "PORCE_VISION_SOURCE=VIDEO_FILE"
if /I "%PORCE_VISION_SOURCE%"=="VIDEO_FILE" (
  set "PORCE_VISION_VIDEO_PATH_CHECK=%PORCE_VISION_VIDEO_PATH%"
  echo(%PORCE_VISION_VIDEO_PATH_CHECK%| findstr /r /c:"[^ ]" >nul
  if errorlevel 1 (
    echo [ERROR] Pipeline B requiere video fuente.
    echo [HINT] Setea: set PORCE_VISION_VIDEO_PATH=D:\ruta\mockup.mp4
    exit /b 6
  )
)
set "PORCE_VISION_DEBUG_WINDOW=1"
set "PORCE_VISION_DEBUG_DOCK=0"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [MODE] Pipeline B ^(REAL_TWIN^) - video ingest + Unreal twin consumer
echo [SECURITY] PORCE_OBSTACLE_TOKEN_REQUIRED=%PORCE_OBSTACLE_TOKEN_REQUIRED% token_prefix=%PORCE_OBSTACLE_TOKEN:~0,8%...
echo [AUDIT] PORCE_AUDIT_ROOT=%PORCE_AUDIT_ROOT%
echo [VISION] source=%PORCE_VISION_SOURCE% path=%PORCE_VISION_VIDEO_PATH%
echo [BRAIN] mock_mavlink=%PORCE_MOCK_MAVLINK% evasion=%PORCE_ENABLE_EVASION%
echo.

REM ============================================================================
REM 0. CLEANUP (SAFE)
REM ============================================================================
echo [0/2] Cleaning previous pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"

powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1

echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 1. WINDOWS TERMINAL (TABS)
REM ============================================================================
echo [1/2] Opening tabs in Windows Terminal...
if /I "%PORCE_FORCE_CMD_WINDOWS%"=="1" (
  echo [INFO] PORCE_FORCE_CMD_WINDOWS=1, forcing cmd fallback windows...
  call :fallback_cmd_tabs
  if errorlevel 1 (
    echo [ERROR] Failed to launch fallback component windows.
    exit /b 4
  )
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\b_launch_tabs.ps1" -ProjectRoot "%PROJECT_ROOT%"
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
start "BRAIN (REAL_TWIN)" cmd /k "set PORCE_SYSTEM_MODE=REAL_TWIN && cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u flight_controller.py 2>&1 | python tee.py --prefix \"%PORCE_TEE_PREFIX_BRAIN%\" --cap-lines %PORCE_TEE_CAP_LINES%"
start "EYES (REAL_TWIN VIDEO)" cmd /k "set PORCE_SYSTEM_MODE=REAL_TWIN && cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u vision_system.py 2>&1 | python tee.py --prefix \"%PORCE_TEE_PREFIX_EYES%\" --cap-lines %PORCE_TEE_CAP_LINES%"
start "VIZ RECORDER" cmd /k "cd /d \"%PIPELINE_DIR%\" && %PYENV%python -u viz_recorder.py 2>&1 | python tee.py --prefix \"VIZ\" --cap-lines %PORCE_TEE_CAP_LINES%"
exit /b 0
