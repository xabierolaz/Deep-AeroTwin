@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "RUN_SECONDS=240"
set "BASELINE_DIR=%REPO_ROOT%\pipeline\logs\zero_trust\20260220_035901"
set "LATEST_FILE=%REPO_ROOT%\pipeline\logs\zero_trust\LATEST_RUN.txt"
if not "%~1"=="" set "RUN_SECONDS=%~1"
if not "%~2"=="" set "BASELINE_DIR=%~2"

echo [1/4] Lanzando Pipeline A...
pushd "%REPO_ROOT%" || goto :fail
call launch.bat
if errorlevel 1 goto :fail

echo [2/4] Esperando %RUN_SECONDS% segundos...
timeout /t %RUN_SECONDS% /nobreak >nul

echo [3/4] Deteniendo pipeline...
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\stop_pipeline.ps1"

if not exist "%LATEST_FILE%" (
  echo [ERROR] No existe LATEST_RUN.txt: %LATEST_FILE%
  goto :end
)
set /p RUN_DIR=<"%LATEST_FILE%"
if "%RUN_DIR%"=="" (
  echo [ERROR] LATEST_RUN.txt esta vacio.
  goto :end
)

echo [4/4] Comparando metricas...
set "TMP_PY=%TEMP%\porce_compare_%RANDOM%%RANDOM%.py"
> "%TMP_PY%" echo import json, os, sys
>> "%TMP_PY%" echo KEYS = ['evasion_route_generated','evasion_route_failed_hold','evasion_completed','waypoint_force_advance_blocked','failsafe_stage_action','failsafe_lateral_replan','failsafe_terminal_action']
>> "%TMP_PY%" echo def metrics(run_dir):
>> "%TMP_PY%" echo     events = os.path.join(run_dir, 'brain', 'events.jsonl')
>> "%TMP_PY%" echo     if not os.path.exists(events):
>> "%TMP_PY%" echo         raise SystemExit('ERROR: No existe events.jsonl en: ' + events)
>> "%TMP_PY%" echo     counts = {k: 0 for k in KEYS}
>> "%TMP_PY%" echo     with open(events, 'r', encoding='utf-8', errors='ignore') as f:
>> "%TMP_PY%" echo         for line in f:
>> "%TMP_PY%" echo             line = line.strip()
>> "%TMP_PY%" echo             if not line:
>> "%TMP_PY%" echo                 continue
>> "%TMP_PY%" echo             try:
>> "%TMP_PY%" echo                 obj = json.loads(line)
>> "%TMP_PY%" echo             except Exception:
>> "%TMP_PY%" echo                 continue
>> "%TMP_PY%" echo             kind = str(obj.get('kind',''))
>> "%TMP_PY%" echo             if kind in counts:
>> "%TMP_PY%" echo                 counts[kind] += 1
>> "%TMP_PY%" echo     counts['run_dir'] = run_dir
>> "%TMP_PY%" echo     return counts
>> "%TMP_PY%" echo def print_block(title, data):
>> "%TMP_PY%" echo     print(title, data['run_dir'])
>> "%TMP_PY%" echo     for k in KEYS:
>> "%TMP_PY%" echo         print('  {}={}'.format(k, data.get(k, 0)))
>> "%TMP_PY%" echo current_dir = sys.argv[1]
>> "%TMP_PY%" echo baseline_dir = sys.argv[2] if len(sys.argv) ^> 2 else ''
>> "%TMP_PY%" echo cur = metrics(current_dir)
>> "%TMP_PY%" echo print_block('[CURRENT]', cur)
>> "%TMP_PY%" echo if baseline_dir and os.path.isdir(baseline_dir):
>> "%TMP_PY%" echo     base = metrics(baseline_dir)
>> "%TMP_PY%" echo     print_block('[BASELINE]', base)
>> "%TMP_PY%" echo else:
>> "%TMP_PY%" echo     print('[BASELINE] no encontrado:', baseline_dir)
python "%TMP_PY%" "%RUN_DIR%" "%BASELINE_DIR%"
del /f /q "%TMP_PY%" >nul 2>&1

:end
popd
echo.
echo [DONE] Pulsa una tecla para cerrar...
pause >nul
exit /b 0

:fail
echo [ERROR] Fallo en ejecucion.
goto :end
