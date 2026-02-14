@echo off
setlocal
TITLE DEEP-AEROTWIN: LAUNCHER (TABS)

REM ============================================================================
REM CONFIG
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

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

REM timeout.exe fails when stdin is redirected; use PowerShell sleep (works everywhere).
powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul 2>&1

echo [OK] Cleanup done.
echo.

REM ============================================================================
REM 1. WINDOWS TERMINAL (TABS)
REM ============================================================================
echo [1/3] Opening tabs in Windows Terminal...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\launch_tabs.ps1" -ProjectRoot "%PROJECT_ROOT%" -Mode "%PORCE_SYSTEM_MODE%"
if errorlevel 1 (
  echo [ERROR] Failed to launch Windows Terminal tabs.
  exit /b 4
)

echo.
echo [OK] Tabs launched.
echo  - Master log: pipeline\\logs\\SYSTEM_ALL.log
echo  - Viz frames: pipeline\\logs\\viz_frames
echo  - Stop everything: powershell -NoProfile -ExecutionPolicy Bypass -File tools\\stop_pipeline.ps1
echo.
exit /b 0

