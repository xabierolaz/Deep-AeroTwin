@echo off
TITLE DEEP-AEROTWIN: PIPELINE A (SIMULATION)
echo ======================================================
echo    LAUNCHING PIPELINE A: AUTONOMOUS SIMULATION
echo ======================================================
echo.
echo [CONFIG] Setting PORCE_SYSTEM_MODE=SIMULATION
set "PORCE_SYSTEM_MODE=SIMULATION"

REM Llamar al lanzador maestro (que lee la variable de entorno)
call launch.bat
