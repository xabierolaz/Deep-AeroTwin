@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "PYTHON_CMD=python"
if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_CMD=%PROJECT_ROOT%\venv\Scripts\python.exe"
)

"%PYTHON_CMD%" "%PROJECT_ROOT%\tools\validate_zero_trust_run.py" %*
exit /b %errorlevel%
