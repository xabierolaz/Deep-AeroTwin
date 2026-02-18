@echo off
TITLE DEEP-AEROTWIN: PIPELINE A (UNIFIED) [TABS]
echo ======================================================
echo    LAUNCHING PIPELINE A: SINGLE OPERATION MODE (TABS)
echo ======================================================
echo.
echo [MODE] Pipeline A (SIMULATION) is the only operational mode.

REM Ejecutar en cmd persistente para que no se cierre la ventana si hay error.
cmd /k ""%~dp0launch.bat""
