@echo off
TITLE DEEP-AEROTWIN: PIPELINE A (SIMULATION) [TABS]
echo ======================================================
echo    LAUNCHING PIPELINE A: AUTONOMOUS SIMULATION (TABS)
echo ======================================================
echo.
echo [CONFIG] Setting PORCE_SYSTEM_MODE=SIMULATION
set "PORCE_SYSTEM_MODE=SIMULATION"

REM Vision defaults for Unreal PIE (drone camera viewport).
REM You can override any of these by setting env vars before running this .bat.
if not defined PORCE_CAPTURE_WINDOW_TITLE set "PORCE_CAPTURE_WINDOW_TITLE=AirTraffic Preview"
if not defined PORCE_CAPTURE_WINDOW_CLASS set "PORCE_CAPTURE_WINDOW_CLASS=UnrealWindow"
if not defined PORCE_CAPTURE_EXPECT_WIDTH set "PORCE_CAPTURE_EXPECT_WIDTH=640"
if not defined PORCE_CAPTURE_EXPECT_HEIGHT set "PORCE_CAPTURE_EXPECT_HEIGHT=640"
if not defined PORCE_VISION_DEBUG_WINDOW set "PORCE_VISION_DEBUG_WINDOW=1"
if not defined PORCE_VISION_DEBUG_DOCK set "PORCE_VISION_DEBUG_DOCK=1"

REM Llamar al lanzador maestro (que lee la variable de entorno)
call "%~dp0launch.bat"
