@echo off
TITLE DEEP-AEROTWIN: PIPELINE B (COMPAT ALIAS)
echo ======================================================
echo    PIPELINE B IS DEPRECATED IN THIS REPO
echo ======================================================
echo.
echo [MODE] Redirecting to unified Pipeline A launcher...

call "%~dp0launch_pipeline_A.bat"
exit /b %ERRORLEVEL%
