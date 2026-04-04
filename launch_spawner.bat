@echo off
setlocal EnableExtensions
TITLE DEEP-AEROTWIN: PIPELINE + SPAWNER

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "BRAIN_URL=http://127.0.0.1:8080"
set "SPAWN_SCRIPT=%REPO_ROOT%\tmp\spawn_unreal_obstacles.ps1"
set "AUDIT_SCRIPT=%REPO_ROOT%\tmp\audit_spawn_alignment.ps1"
set "SPAWN_DURATION_S=20"
set "SPAWN_HZ=3"
set "BRAIN_READY_TIMEOUT_PRE_S=90"
set "BRAIN_READY_TIMEOUT_SPAWN_S=60"

if not "%~1"=="" set "SPAWN_DURATION_S=%~1"
if not "%~2"=="" set "SPAWN_HZ=%~2"

if not exist "%SPAWN_SCRIPT%" (
  echo [ERROR] No existe script de spawner: %SPAWN_SCRIPT%
  goto :end_error
)
if not exist "%AUDIT_SCRIPT%" (
  echo [WARN] No existe script de auditoria: %AUDIT_SCRIPT%
)

if not defined PORCE_OBSTACLE_TOKEN (
  for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\")"') do set "PORCE_OBSTACLE_TOKEN=%%i"
)
set "PORCE_OBSTACLE_TOKEN_PERSIST=0"
echo [SECURITY] Spawner token en memoria. prefix=%PORCE_OBSTACLE_TOKEN:~0,8%...

echo [1/4] Lanzando pipeline...
call "%REPO_ROOT%\launch.bat"
if errorlevel 1 (
  echo [ERROR] launch.bat fallo.
  goto :end_error
)

echo [2/4] Esperando Brain en %BRAIN_URL% ...
call :wait_brain %BRAIN_READY_TIMEOUT_PRE_S%
if errorlevel 1 (
  echo [WARN] Brain aun no responde en /api/status. Continuamos y reintentamos antes de spawn.
)

echo [3/4] En Unreal: pulsa Play. Luego pulsa una tecla aqui para inyectar obstaculos...
pause >nul

echo [4/5] Ejecutando spawner ^(duration=%SPAWN_DURATION_S%s hz=%SPAWN_HZ%^)
call :wait_brain %BRAIN_READY_TIMEOUT_SPAWN_S%
if errorlevel 1 (
  echo [ERROR] Brain no responde en /api/status antes del spawn.
  goto :end_error
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%SPAWN_SCRIPT%" -BrainUrl "%BRAIN_URL%" -DurationS %SPAWN_DURATION_S% -Hz %SPAWN_HZ%
if errorlevel 1 (
  echo [ERROR] Fallo durante el spawner.
  goto :end_error
)

if exist "%AUDIT_SCRIPT%" (
  echo [5/5] Ejecutando auditoria de alineacion ^(lat/lon -^> world_m^)...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%AUDIT_SCRIPT%" -BrainUrl "%BRAIN_URL%" -WarnErrorM 0.5
  set "AUDIT_EXIT=%errorlevel%"
  if "%AUDIT_EXIT%"=="0" (
    echo [OK] Auditoria de alineacion sin discrepancias relevantes.
  ) else (
    if "%AUDIT_EXIT%"=="2" (
      echo [WARN] Auditoria detecto discrepancias sobre umbral.
    ) else (
      echo [WARN] No se pudo completar la auditoria de alineacion ^(exit=%AUDIT_EXIT%^).
    )
  )
)

echo.
echo [OK] Spawner completado.
echo [INFO] Para parar todo: powershell -NoProfile -ExecutionPolicy Bypass -File tools\stop_pipeline.ps1
goto :end_ok

:end_error
echo.
echo [DONE] Estado: ERROR
pause
exit /b 1

:end_ok
echo.
echo [DONE] Estado: OK
pause
exit /b 0

:wait_brain
set "WAIT_S=%~1"
if "%WAIT_S%"=="" set "WAIT_S=60"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$u='%BRAIN_URL%/api/status'; $deadline=(Get-Date).AddSeconds(%WAIT_S%); $ok=$false; while((Get-Date) -lt $deadline){ try { $null = Invoke-RestMethod -Uri $u -TimeoutSec 2; $ok=$true; break } catch { Start-Sleep -Milliseconds 700 } }; if($ok){ exit 0 } else { exit 1 }"
exit /b %errorlevel%
