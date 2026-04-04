@echo off
setlocal
TITLE DEEP-AEROTWIN: PIPELINE LAUNCHER

REM ============================================================================
REM CONFIG
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

REM Shared defaults (single source in pipeline\porce_defaults.env)
set "PORCE_DEFAULTS_FORCE=1"
call "%PROJECT_ROOT%\tools\load_porce_defaults.bat" "%PROJECT_ROOT%\pipeline\porce_defaults.env" "%PORCE_DEFAULTS_FORCE%"
if errorlevel 1 (
  echo [ERROR] Failed to load shared defaults from pipeline\porce_defaults.env
  exit /b 5
)
set "PORCE_UNREAL_TELEMETRY_INGEST_ENABLE=0"
set "PORCE_UNREAL_TELEMETRY_ENABLE=0"
set "PORCE_SITL_ALLOW_HOME_FALLBACK=0"
if not defined PORCE_WSL_PRECHECK_ENABLE set "PORCE_WSL_PRECHECK_ENABLE=1"
if not defined PORCE_WSL_AUTO_RECOVER set "PORCE_WSL_AUTO_RECOVER=1"
if not defined PORCE_WSL_AUTO_RECOVER_ON_STOP set "PORCE_WSL_AUTO_RECOVER_ON_STOP=1"
if not defined PORCE_OBSTACLE_TOKEN_PERSIST set "PORCE_OBSTACLE_TOKEN_PERSIST=0"
if /I "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="true" set "PORCE_OBSTACLE_TOKEN_PERSIST=1"
if /I "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="yes" set "PORCE_OBSTACLE_TOKEN_PERSIST=1"
if /I "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="on" set "PORCE_OBSTACLE_TOKEN_PERSIST=1"
if not "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="1" set "PORCE_OBSTACLE_TOKEN_PERSIST=0"

if not exist "%PROJECT_ROOT%\pipeline\logs\zero_trust" mkdir "%PROJECT_ROOT%\pipeline\logs\zero_trust" >nul 2>&1
set "PORCE_OBSTACLE_TOKEN_FILE=%PROJECT_ROOT%\pipeline\logs\zero_trust\OBSTACLE_TOKEN.txt"

if not defined PORCE_OBSTACLE_TOKEN_REQUIRED set "PORCE_OBSTACLE_TOKEN_REQUIRED=1"
if /I not "%PORCE_OBSTACLE_TOKEN_REQUIRED%"=="0" (
  if /I "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="1" if not defined PORCE_OBSTACLE_TOKEN if exist "%PORCE_OBSTACLE_TOKEN_FILE%" (
    set /p PORCE_OBSTACLE_TOKEN=<"%PORCE_OBSTACLE_TOKEN_FILE%"
  )
  if defined PORCE_OBSTACLE_TOKEN (
    set "PORCE_OBSTACLE_TOKEN=%PORCE_OBSTACLE_TOKEN: =%"
    echo(%PORCE_OBSTACLE_TOKEN%| findstr /R /I "^[0-9A-F][0-9A-F]*$" >nul
    if errorlevel 1 set "PORCE_OBSTACLE_TOKEN="
    if not "%PORCE_OBSTACLE_TOKEN:~32,1%"=="" set "PORCE_OBSTACLE_TOKEN="
    if "%PORCE_OBSTACLE_TOKEN:~31,1%"=="" set "PORCE_OBSTACLE_TOKEN="
  )
  if not defined PORCE_OBSTACLE_TOKEN (
    for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\")"') do set "PORCE_OBSTACLE_TOKEN=%%i"
  )
  if /I "%PORCE_OBSTACLE_TOKEN_PERSIST%"=="1" if defined PORCE_OBSTACLE_TOKEN (
    >"%PORCE_OBSTACLE_TOKEN_FILE%" <nul set /p ="%PORCE_OBSTACLE_TOKEN%"
  )
)
if not defined PORCE_UNREAL_TELEMETRY_TOKEN set "PORCE_UNREAL_TELEMETRY_TOKEN=%PORCE_OBSTACLE_TOKEN%"
if not defined PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED set "PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED=%PORCE_OBSTACLE_TOKEN_REQUIRED%"

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
echo %PORCE_AUDIT_ROOT%>"%PROJECT_ROOT%\pipeline\logs\zero_trust\LATEST_RUN.txt"

set "PORCE_SYSTEM_MODE=SIMULATION"
set "PORCE_VISION_DEBUG_WINDOW=1"
set "PORCE_VISION_DEBUG_DOCK=1"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [MODE] Unified mode: Pipeline (SIMULATION)
echo [SECURITY] PORCE_OBSTACLE_TOKEN_REQUIRED=%PORCE_OBSTACLE_TOKEN_REQUIRED% token_persist=%PORCE_OBSTACLE_TOKEN_PERSIST% token_prefix=%PORCE_OBSTACLE_TOKEN:~0,8%...
echo [AUDIT] PORCE_AUDIT_ROOT=%PORCE_AUDIT_ROOT%
echo.

REM ============================================================================
REM 0. WSL PRECHECK (SAFE)
REM ============================================================================
if /I "%PORCE_WSL_PRECHECK_ENABLE%"=="1" (
  echo [0/3] Checking WSL health...
  call :precheck_wsl
  if errorlevel 1 (
    echo [ERROR] WSL is not healthy. Abort launch.
    echo [HINT] Try: wsl --shutdown
    exit /b 6
  )
)

REM ============================================================================
REM 1. CLEANUP (SAFE)
REM ============================================================================
echo [1/3] Cleaning previous pipeline processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"

REM timeout.exe fails when stdin is redirected; use PowerShell sleep (works everywhere).
powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1

echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 2. WINDOWS TERMINAL (TABS)
REM ============================================================================
echo [2/3] Opening tabs in Windows Terminal...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\launch_tabs.ps1" -ProjectRoot "%PROJECT_ROOT%"
if errorlevel 1 (
  echo [ERROR] Failed to launch component windows via tools\launch_tabs.ps1
  exit /b 4
)

echo.
echo [OK] Tabs launched.
echo  - Master log: %PORCE_LOG_SERVER_FILE%
echo  - Viz frames: pipeline\\logs\\viz_frames
echo  - Stop everything: powershell -NoProfile -ExecutionPolicy Bypass -File tools\\stop_pipeline.ps1
echo.
exit /b 0

:precheck_wsl
wsl -e sh -lc "echo WSL_OK" >nul 2>&1
if not errorlevel 1 (
  echo [OK] WSL ready.
  exit /b 0
)
echo [WARN] WSL precheck failed.
if /I "%PORCE_WSL_AUTO_RECOVER%"=="1" (
  echo [INFO] Trying WSL recover with wsl --shutdown...
  wsl --shutdown >nul 2>&1
  powershell -NoProfile -Command "Start-Sleep -Milliseconds 800" >nul 2>&1
  wsl -e sh -lc "echo WSL_OK" >nul 2>&1
  if not errorlevel 1 (
    echo [OK] WSL recovered.
    exit /b 0
  )
)
exit /b 1
