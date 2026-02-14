@echo off
TITLE DEEP-AEROTWIN: PIPELINE B (DIGITAL TWIN) [TABS]
echo ======================================================
echo    LAUNCHING PIPELINE B: REAL-TIME DIGITAL TWIN (TABS)
echo ======================================================
echo.
echo [CONFIG] Setting PORCE_SYSTEM_MODE=REAL_TWIN
set "PORCE_SYSTEM_MODE=REAL_TWIN"

REM Pipeline B uses the same tabbed launcher but skips SITL.
call "%~dp0launch.bat"

