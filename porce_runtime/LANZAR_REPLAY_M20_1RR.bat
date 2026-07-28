@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem ============================================================================
rem  LANZAR_REPLAY_M20_1RR.bat — Replay determinista de vuelo real (Pipeline B)
rem  Vuelo exacto del video M_20_1RR + deteccion de apoyos real -> Brain ->
rem  Unreal/Cesium (proxy SPPA) con el dron siguiendo la trayectoria real.
rem ============================================================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "REPLAY_DIR=%PROJECT_ROOT%\tools\real_flight_replay"
rem Repo root (parent of porce_runtime): Unreal\ lives there.
for %%I in ("%PROJECT_ROOT%\..") do set "REPO_ROOT=%%~fI"
if not defined PORCE_UNREAL_ENGINE_ROOT set "PORCE_UNREAL_ENGINE_ROOT=D:\Epic Games\UE_5.7"
if not defined UE_EDITOR set "UE_EDITOR=%PORCE_UNREAL_ENGINE_ROOT%\Engine\Binaries\Win64\UnrealEditor.exe"
if not defined UE_CMD set "UE_CMD=%PORCE_UNREAL_ENGINE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
set "UPROJECT=%REPO_ROOT%\Unreal\AirTraffic.uproject"

rem --- Token compartido (fijo para reproducibilidad del replay) ---
set "PORCE_OBSTACLE_TOKEN=replaym20token1234567890123456"

title Deep-AeroTwin REPLAY M_20_1RR
echo [REPLAY] Pipeline B replay de vuelo real M_20_1RR

echo [1/7] Parando procesos previos del pipeline...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\tools\stop_pipeline.ps1" -Quiet >nul 2>nul

echo [2/7] Anclando escena Unreal a la zona de vuelo real (commandlet)...
"%UE_CMD%" "%UPROJECT%" -run=pythonscript -script="%REPO_ROOT%\Unreal\Scripts\apply_replay_spawn_origin_and_save.py" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > "%PROJECT_ROOT%\pipeline\logs\replay_apply_origin.log" 2>&1 || goto :error

echo [3/7] Brain (REAL_TWIN + replay telemetry + audit)...
start "REPLAY Brain" cmd /c "set PORCE_SYSTEM_MODE=REAL_TWIN&& set PORCE_REPLAY_TELEMETRY_ENABLE=1&& set PORCE_OBSTACLE_TOKEN=%PORCE_OBSTACLE_TOKEN%&& set PORCE_AUDIT_ROOT=%REPLAY_DIR%\out\audit_replay&& cd /d %PROJECT_ROOT%\pipeline && python -u flight_controller.py"

echo [4/7] Enlace de video simulado (telemetria)...
start "REPLAY VideoLink" cmd /c "cd /d %REPLAY_DIR% && python -u video_link_server.py --port 8099"

echo [5/7] Unreal Editor...
powershell -NoProfile -Command "$p=Get-Process UnrealEditor -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*AirTraffic*' } | Select-Object -First 1; if (-not $p) { Start-Process -FilePath '%UE_EDITOR%' -ArgumentList @('%UPROJECT%','/Game/Ejea','-log') | Out-Null }"

echo      Esperando Brain HTTP...
set "BRAIN_OK=0"
for /L %%I in (1,1,40) do (
  curl.exe -fsS --max-time 1 "http://127.0.0.1:8080/health" >nul 2>nul && set "BRAIN_OK=1" && goto :brain_ok
  timeout /t 1 /nobreak >nul
)
:brain_ok
if not "%BRAIN_OK%"=="1" echo [WARN] Brain HTTP no listo; continuando.

echo      Esperando MCP Unreal...
set "MCP_OK=0"
for /L %%I in (1,1,60) do (
  python "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=hide_stats --timeout 5 >nul 2>nul && set "MCP_OK=1" && goto :mcp_ok
  timeout /t 2 /nobreak >nul
)
:mcp_ok
if not "%MCP_OK%"=="1" ( echo [ERROR] MCP Unreal no responde. & goto :error )

echo [6/7] PIE + inyeccion del componente twin (SPPA)...
python "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=stop --timeout 15 >nul 2>nul
python "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=set_game_view --arg enabled=true --timeout 30 >nul 2>nul
python "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=set_viewport_resolution --arg width=1280 --arg height=720 --timeout 30 >nul 2>nul
python "%PROJECT_ROOT%\tools\unreal_mcp_call.py" control_editor "{}" --arg action=play --arg mode=new_window --timeout 180
timeout /t 5 /nobreak >nul
python "%REPLAY_DIR%\setup_pie_component.py" --token %PORCE_OBSTACLE_TOKEN% --retries 60

echo [7/7] Vision (video real por el enlace) + driver del dron...
start "REPLAY Vision" cmd /c "set PORCE_SYSTEM_MODE=REAL_TWIN&& set PORCE_OBSTACLE_TOKEN=%PORCE_OBSTACLE_TOKEN%&& set PORCE_VISION_SOURCE=VIDEO_LINK&& set PORCE_VISION_VIDEO_LINK_URL=http://127.0.0.1:8099&& set PORCE_VISION_VIDEO_ROTATE=0&& set PORCE_VISION_TELEMETRY_REPLAY_FILE=%REPLAY_DIR%\out\trajectory_m20_1rr.csv&& set PORCE_VISION_TELEMETRY_REPLAY_POST_ENABLE=1&& set PORCE_YOLO_MODEL=%REPLAY_DIR%\out\yolo_tower_real_tower_portrait_v1.pt&& set PORCE_CAMERA_MOUNT_YAW_DEG=155&& set PORCE_CAMERA_MOUNT_PITCH_DEG=-37&& set PORCE_CAMERA_MOUNT_ROLL_DEG=0&& set PORCE_CAMERA_VFOV_DEG=77&& set PORCE_VISION_IMGSZ=1280&& set PORCE_VISION_TARGET_CLASS_NAMES=tower&& set PORCE_VISION_DET_CONF=0.25&& set PORCE_VISION_PUBLISH_CONF=0.25&& set PORCE_VISION_DEBUG_WINDOW=1&& set PORCE_VISION_DEBUG_TITLE=REPLAY M20_1RR torres&& cd /d %PROJECT_ROOT%\pipeline && python -u vision_system.py"
timeout /t 3 /nobreak >nul
start "REPLAY Driver" cmd /c "cd /d %REPLAY_DIR% && python -u drone_marker_driver.py --token %PORCE_OBSTACLE_TOKEN%"

echo.
echo [REPLAY] Todo lanzado. El dron repite el vuelo exacto; los apoyos se
echo          detectan en el video real y se reconstruyen como proxies SPPA.
echo          Metricas tras la corrida: python %REPLAY_DIR%\analyze_replay.py ^& python %REPLAY_DIR%\compute_replay_metrics.py
exit /b 0

:error
echo [ERROR] Fallo en el lanzamiento (ver logs en pipeline\logs y consolas).
exit /b 1
