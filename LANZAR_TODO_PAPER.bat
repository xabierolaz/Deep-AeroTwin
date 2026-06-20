@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "UE_EDITOR=D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
set "UE_CMD=D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
set "UPROJECT=%PROJECT_ROOT%\Unreal\AirTraffic.uproject"
set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

if not exist "%UPROJECT%" (
  echo [ERROR] Unreal project not found: %UPROJECT%
  exit /b 2
)

if not exist "%UE_EDITOR%" (
  echo [ERROR] UnrealEditor.exe not found: %UE_EDITOR%
  exit /b 3
)

title Deep-AeroTwin paper launcher
echo [Deep-AeroTwin] Paper launcher
echo [ALL-IN-ONE] Use this file to launch Unreal + PIE + full paper pipeline.
echo [NOTE] launch.bat is pipeline-only and assumes Unreal/PIE is already ready.
echo [ROOT] %PROJECT_ROOT%
echo.

rem Final paper capture defaults. launch.bat keeps these because PORCE_DEFAULTS_FORCE=0.
set "PORCE_DEFAULTS_FORCE=0"
set "PORCE_SYSTEM_MODE=SIMULATION"
set "PORCE_VISION_RECORD_ENABLE=1"
set "PORCE_VISION_RECORD_MAX_SECONDS=420"
set "PORCE_TELEMETRY_YAW_SMOOTH_ENABLE=1"
set "PORCE_TELEMETRY_YAW_SMOOTH_MAX_RATE_DPS=30.0"
set "PORCE_TELEMETRY_YAW_SMOOTH_TAU_S=0.65"
set "PORCE_TELEMETRY_ATTITUDE_SMOOTH_ENABLE=1"
set "PORCE_TELEMETRY_ATTITUDE_SMOOTH_MAX_RATE_DPS=45.0"
set "PORCE_TELEMETRY_ATTITUDE_SMOOTH_TAU_S=0.50"
set "PORCE_VISION_DEBUG_WINDOW=1"
set "PORCE_VISION_DEBUG_DOCK=1"
set "PORCE_VISION_DEBUG_TOPMOST=1"
set "PORCE_VISION_DEBUG_TITLE=YOLOv11 evidence"
set "PORCE_VISION_PROCESS_PRIORITY=high"
set "PORCE_UNREAL_PROCESS_PRIORITY=High"
set "PORCE_VISION_OVERLAY_MODE=paper"
set "PORCE_VISION_TARGET_CLASS_NAMES=biker,cow,tower"
set "PORCE_VISION_TARGET_CLASS_FALLBACK_NAMES=person,bicycle"
set "PORCE_OBS_STATIC_CLASS_NAMES=tower,cow"
set "PORCE_VISION_DYNAMIC_CLUSTER_ENABLE=1"
set "PORCE_VISION_DYNAMIC_CLUSTER_CLASS_NAMES=biker,bicycle,person"
set "PORCE_VISION_DYNAMIC_CLUSTER_GEO_M=12.0"
set "PORCE_VISION_DYNAMIC_CLUSTER_DIST_M=18.0"
set "PORCE_VISION_MAX_OBS_PER_FRAME=8"
set "PORCE_VISION_MIN_AGL_TO_PUBLISH_M=10.0"
set "PORCE_CAPTURE_WINDOW_TITLE=AirTraffic Preview"
set "PORCE_CAPTURE_WINDOW_CLASS=UnrealWindow"
set "PORCE_CAPTURE_WINDOW_EXACT=0"
set "PORCE_CAPTURE_WINDOW_METHOD=printwindow"
set "PORCE_CAPTURE_WINDOW_FOCUS=0"
set "PORCE_CAPTURE_WINDOW_CLICK_FOCUS=0"
set "PORCE_CAPTURE_WINDOW_TOPMOST=0"
set "PORCE_SIM_CONTROL_LOOP_STARTUP_DELAY_S=5.0"
set "PORCE_CONTROL_LOOP_STARTUP_DELAY_S=5.0"
set "PORCE_CONTROL_ARM_RETRY_INTERVAL_S=5.0"
set "PORCE_TEE_CAP_LINES=300"
set "PORCE_FORCE_CMD_WINDOWS=0"
set "PORCE_ALLOW_CMD_WINDOWS_FALLBACK=0"
set "PORCE_TERMINAL_KEEP_OPEN=0"
if not defined PORCE_WT_WINDOW set "PORCE_WT_WINDOW=DeepAeroTwinPORCE"
if not defined PORCE_PREPARE_UNREAL set "PORCE_PREPARE_UNREAL=1"

if /I "%PORCE_LAUNCH_DRY_RUN%"=="1" (
  echo [DRY-RUN] Launcher syntax and paths are OK.
  echo [DRY-RUN] This is the root all-in-one launcher: %PROJECT_ROOT%\LANZAR_TODO_PAPER.bat
  echo [DRY-RUN] Pipeline-only launcher remains: %PROJECT_ROOT%\launch.bat
  exit /b 0
)

echo [1/5] Stopping previous pipeline/SITL processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet
if errorlevel 1 (
  echo [WARN] stop_pipeline.ps1 returned an error; continuing.
)

if /I "%PORCE_PREPARE_UNREAL%"=="1" (
  echo.
  echo [2/5] Preparing Unreal paper scene by commandlet...
  call :run_unreal_script apply_ejea_spawn_origin_and_save.py || exit /b %errorlevel%
  call :run_unreal_script apply_cesium_paper_streaming_profile.py || exit /b %errorlevel%
  call :run_unreal_script configure_cesium_ejea_route_precache.py || exit /b %errorlevel%
  call :run_unreal_script canonicalize_peloton_only.py || exit /b %errorlevel%
  call :run_unreal_script apply_paper_all_obstacles_profile_and_save.py || exit /b %errorlevel%
  call :run_unreal_script apply_paper_runtime_camera_profile.py || exit /b %errorlevel%
  call :run_unreal_script audit_paper_peloton_state.py || exit /b %errorlevel%
) else (
  echo.
  echo [2/5] Unreal commandlet preparation skipped.
  echo       Set PORCE_PREPARE_UNREAL=1 to force scene prep/audit, or 0 to skip.
)

echo.
echo [3/5] Opening Unreal Ejea scene if needed...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Get-Process UnrealEditor -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*AirTraffic*' } | Select-Object -First 1; if (-not $p) { $p=Start-Process -FilePath '%UE_EDITOR%' -ArgumentList @('%UPROJECT%','/Game/Ejea','-log') -PassThru; Write-Host ('[OK] Unreal launched, pid=' + $p.Id) } else { Write-Host ('[OK] Unreal already running, pid=' + $p.Id) }; $priority='%PORCE_UNREAL_PROCESS_PRIORITY%'; if ($p -and $priority) { try { $p.PriorityClass=$priority; Write-Host ('[OK] Unreal priority=' + $priority) } catch { Write-Host ('[WARN] Could not set Unreal priority: ' + $_.Exception.Message) } }"
if errorlevel 1 (
  echo [ERROR] Could not start or detect Unreal.
  exit /b 4
)

echo [PIE] Stopping any previous Play-In-Editor session before pipeline restart...
"%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=stop --timeout 15 >nul 2>nul

echo.
echo [4/5] Launching full SIMULATION pipeline in Windows Terminal tabs...
call "%PROJECT_ROOT%\launch.bat"
if errorlevel 1 exit /b %errorlevel%

echo.
echo [5/5] Waiting for Brain HTTP, then starting PIE in a separate game window...
call :wait_brain_http

set "MCP_READY=0"
for /L %%I in (1,1,90) do (
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=hide_stats --timeout 5 >nul 2>nul
  if not errorlevel 1 (
    set "MCP_READY=1"
    goto :mcp_ready
  )
  timeout /t 2 /nobreak >nul
)

:mcp_ready
if not "%MCP_READY%"=="1" (
  echo [WARN] Unreal MCP did not become ready. Open PIE manually, then vision can still capture AirTraffic.
) else (
  echo [PIE] Stopping any previous Play-In-Editor session...
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=stop --timeout 30 >nul 2>nul
  timeout /t 2 /nobreak >nul
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=set_game_view --arg enabled=true --timeout 30 >nul 2>nul
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=hide_stats --timeout 30 >nul 2>nul
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=set_viewport_resolution --arg width=960 --arg height=960 --timeout 30 >nul 2>nul
  "%PYTHON%" "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=play --arg mode=new_window --timeout 120
)

exit /b 0

:wait_brain_http
set "BRAIN_HTTP_READY=0"
for /L %%I in (1,1,40) do (
  curl.exe -fsS --max-time 1 "http://127.0.0.1:8080/health" >nul 2>nul
  if not errorlevel 1 (
    set "BRAIN_HTTP_READY=1"
    goto :brain_http_ready
  )
  timeout /t 1 /nobreak >nul
)

:brain_http_ready
if not "%BRAIN_HTTP_READY%"=="1" (
  echo [WARN] Brain HTTP did not become ready before PIE. Continuing; Unreal may log transient connection warnings.
) else (
  echo [OK] Brain HTTP ready.
)
exit /b 0

:run_unreal_script
set "SCRIPT_NAME=%~1"
set "SCRIPT_PATH=%PROJECT_ROOT%\Unreal\Scripts\%SCRIPT_NAME%"
set "LOG_PATH=%PROJECT_ROOT%\pipeline\logs\launch_%~n1_latest.log"
if not exist "%SCRIPT_PATH%" (
  echo [ERROR] Missing Unreal script: %SCRIPT_PATH%
  exit /b 10
)
echo       %SCRIPT_NAME%
"%UE_CMD%" "%UPROJECT%" -run=pythonscript -script="%SCRIPT_PATH%" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > "%LOG_PATH%" 2>&1
if errorlevel 1 (
  echo [ERROR] Unreal script failed: %SCRIPT_NAME%
  echo         Log: %LOG_PATH%
  exit /b %errorlevel%
)
exit /b 0
