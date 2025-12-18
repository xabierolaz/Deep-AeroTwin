@echo off
setlocal enabledelayedexpansion
TITLE DEEP-AEROTWIN: MASTER SYSTEM LAUNCHER

REM ============================================================================
REM CONFIGURACION
REM ============================================================================
set "PROJECT_ROOT=%~dp0"
set "PORCE_SYSTEM_MODE=SIMULATION"
set "WINDOW_TITLE_SUFFIX=(%PORCE_SYSTEM_MODE%)"

if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PIPELINE_DIR=%PROJECT_ROOT%\pipeline"
set "LOGS_DIR=%PIPELINE_DIR%\logs"

echo [LAUNCHER] Root: %PROJECT_ROOT%
echo [CONFIG] Modo: %PORCE_SYSTEM_MODE%
echo.

REM ============================================================================
REM 0. LIMPIEZA
REM ============================================================================
echo [0/6] Limpiando procesos...
taskkill /F /FI "WINDOWTITLE eq MASTER LOG*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq FLIGHT CONTROLLER*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VISION SYSTEM*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ArduPilot SITL*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq VIZ RECORDER*" /T >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
wsl -e pkill -9 -f arducopter >nul 2>&1
wsl -e pkill -9 -f python3 >nul 2>&1

if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%LOGS_DIR%\viz_frames" mkdir "%LOGS_DIR%\viz_frames"

REM Borramos wrappers viejos para forzar regeneracion limpia
if exist "%PIPELINE_DIR%\brain_wrapper.py" del "%PIPELINE_DIR%\brain_wrapper.py"
if exist "%PIPELINE_DIR%\viz_recorder.py" del "%PIPELINE_DIR%\viz_recorder.py"

timeout /t 1 /nobreak >nul
echo [OK] Limpio.

REM ============================================================================
REM 1. GENERACION DE HERRAMIENTAS (AUTO-GEN)
REM ============================================================================
echo [1/6] Generando herramientas...

REM --- Generar viz_recorder.py (Professional Paper Style) ---
set "VIZ_SCRIPT=%PIPELINE_DIR%\viz_recorder.py"
if exist "%VIZ_SCRIPT%" del "%VIZ_SCRIPT%"

echo #!/usr/bin/env python3 >> "%VIZ_SCRIPT%"
echo import matplotlib >> "%VIZ_SCRIPT%"
echo matplotlib.use('Agg') >> "%VIZ_SCRIPT%"
echo import matplotlib.pyplot as plt >> "%VIZ_SCRIPT%"
echo from matplotlib.patches import Circle, Rectangle >> "%VIZ_SCRIPT%"
echo from matplotlib.lines import Line2D >> "%VIZ_SCRIPT%"
echo import requests, math, time, os, shutil >> "%VIZ_SCRIPT%"
echo from constants import MAVLINK_HUB_HTTP_PORT, EARTH_RADIUS_M >> "%VIZ_SCRIPT%"
echo API_URL = f"http://127.0.0.1:{MAVLINK_HUB_HTTP_PORT}/api/ui/data" >> "%VIZ_SCRIPT%"
echo OUTPUT_DIR = os.path.join("logs", "viz_frames") >> "%VIZ_SCRIPT%"
echo def latlon_to_meters(lat, lon, home_lat, home_lon): >> "%VIZ_SCRIPT%"
echo     dlat = math.radians(lat - home_lat) >> "%VIZ_SCRIPT%"
echo     dlon = math.radians(lon - home_lon) >> "%VIZ_SCRIPT%"
echo     return dlon * EARTH_RADIUS_M * math.cos(math.radians(home_lat)), dlat * EARTH_RADIUS_M >> "%VIZ_SCRIPT%"
echo def main(): >> "%VIZ_SCRIPT%"
echo     if os.path.exists(OUTPUT_DIR): >> "%VIZ_SCRIPT%"
echo         try: shutil.rmtree(OUTPUT_DIR) >> "%VIZ_SCRIPT%"
echo         except: pass >> "%VIZ_SCRIPT%"
echo     os.makedirs(OUTPUT_DIR, exist_ok=True) >> "%VIZ_SCRIPT%"
echo     plt.style.use('seaborn-v0_8-whitegrid') >> "%VIZ_SCRIPT%"
echo     # RESOLUCION AUMENTADA (16x16 pulgadas a 150 DPI) >> "%VIZ_SCRIPT%"
echo     fig, ax = plt.subplots(figsize=(16, 16)) >> "%VIZ_SCRIPT%"
echo     frame = 0; hx, hy = [], [] >> "%VIZ_SCRIPT%"
echo     print(f"[VIZ] Iniciando motor grafico...") >> "%VIZ_SCRIPT%"
echo     while True: >> "%VIZ_SCRIPT%"
echo         st = time.time() >> "%VIZ_SCRIPT%"
echo         try:  >> "%VIZ_SCRIPT%"
echo             r = requests.get(API_URL, timeout=0.5) >> "%VIZ_SCRIPT%"
echo             data = r.json() if r.status_code==200 else None >> "%VIZ_SCRIPT%"
echo         except: data = None >> "%VIZ_SCRIPT%"
echo         if not data or not data.get('home'): >> "%VIZ_SCRIPT%"
echo             time.sleep(1); continue >> "%VIZ_SCRIPT%"
echo         h, t, obs, ev, wps = data['home'], data['telemetry'], data['obstacles'], data['evasion'], data['waypoints'] >> "%VIZ_SCRIPT%"
echo         # Conversiones >> "%VIZ_SCRIPT%"
echo         dx, dy = latlon_to_meters(t['lat'], t['lon'], h['lat'], h['lon']) >> "%VIZ_SCRIPT%"
echo         hx.append(dx); hy.append(dy) >> "%VIZ_SCRIPT%"
echo         if len(hx)^>2000: hx.pop(0); hy.pop(0) >> "%VIZ_SCRIPT%"
echo         ax.clear() >> "%VIZ_SCRIPT%"
echo         # 1. RUTA MISION (Global Plan) >> "%VIZ_SCRIPT%"
echo         mx, my = [0], [0] # Home >> "%VIZ_SCRIPT%"
echo         ax.text(0, 0, 'HOME', fontsize=10, fontweight='bold', color='#4C72B0') >> "%VIZ_SCRIPT%"
echo         for i, wp in enumerate(wps): >> "%VIZ_SCRIPT%"
echo             wx, wy = latlon_to_meters(wp['lat'], wp['lon'], h['lat'], h['lon']) >> "%VIZ_SCRIPT%"
echo             mx.append(wx); my.append(wy) >> "%VIZ_SCRIPT%"
echo             if i ^> 0: ax.text(wx+5, wy+5, f'WP{i}', fontsize=10, color='#4C72B0') >> "%VIZ_SCRIPT%"
echo         ax.plot(mx, my, '--', color='#4C72B0', linewidth=1.5, label='Global Mission', zorder=1) >> "%VIZ_SCRIPT%"
echo         ax.scatter(mx, my, marker='^', color='#4C72B0', s=80, zorder=2) >> "%VIZ_SCRIPT%"
echo         # 2. OBSTACULOS >> "%VIZ_SCRIPT%"
echo         for o in obs: >> "%VIZ_SCRIPT%"
echo             ox, oy = latlon_to_meters(o['lat'], o['lon'], h['lat'], h['lon']) >> "%VIZ_SCRIPT%"
echo             ax.add_patch(Circle((ox, oy), data['params']['safety_dist'], color='#C44E52', alpha=0.3)) >> "%VIZ_SCRIPT%"
echo             ax.plot(ox, oy, 'x', color='#C44E52') >> "%VIZ_SCRIPT%"
echo         # 3. RUTA EVASION & GRID (Local Plan) >> "%VIZ_SCRIPT%"
echo         if ev['active'] and ev['path'] and ev.get('grid_origin'): >> "%VIZ_SCRIPT%"
echo             # Calcular origen del grid en metros >> "%VIZ_SCRIPT%"
echo             gox, goy = latlon_to_meters(ev['grid_origin']['lat'], ev['grid_origin']['lon'], h['lat'], h['lon']) >> "%VIZ_SCRIPT%"
echo             # DIBUJAR GRID (400m x 400m alrededor del origen) >> "%VIZ_SCRIPT%"
echo             grid_sz = 10 # 10 metros >> "%VIZ_SCRIPT%"
echo             radius = 150 # Radio visual del grid >> "%VIZ_SCRIPT%"
echo             # Lineas verticales >> "%VIZ_SCRIPT%"
echo             for gx in range(int(gox)-radius, int(gox)+radius, grid_sz): >> "%VIZ_SCRIPT%"
echo                 # Alinear al origen del grid >> "%VIZ_SCRIPT%"
echo                 offset = (gx - gox) %% grid_sz >> "%VIZ_SCRIPT%"
echo                 line_x = gx - offset >> "%VIZ_SCRIPT%"
echo                 ax.plot([line_x, line_x], [goy-radius, goy+radius], '-', color='#DDDDDD', linewidth=0.5, zorder=0) >> "%VIZ_SCRIPT%"
echo             # Lineas horizontales >> "%VIZ_SCRIPT%"
echo             for gy in range(int(goy)-radius, int(goy)+radius, grid_sz): >> "%VIZ_SCRIPT%"
echo                 offset = (gy - goy) %% grid_sz >> "%VIZ_SCRIPT%"
echo                 line_y = gy - offset >> "%VIZ_SCRIPT%"
echo                 ax.plot([gox-radius, gox+radius], [line_y, line_y], '-', color='#DDDDDD', linewidth=0.5, zorder=0) >> "%VIZ_SCRIPT%"
echo             # DIBUJAR RUTA COMO CELDAS >> "%VIZ_SCRIPT%"
echo             ex = [dx] + [latlon_to_meters(p['lat'], p['lon'], h['lat'], h['lon'])[0] for p in ev['path']] >> "%VIZ_SCRIPT%"
echo             ey = [dy] + [latlon_to_meters(p['lat'], p['lon'], h['lat'], h['lon'])[1] for p in ev['path']] >> "%VIZ_SCRIPT%"
echo             ax.plot(ex, ey, '-', color='#E67E22', linewidth=1.5, label='Evasion Path', zorder=5) >> "%VIZ_SCRIPT%"
echo             # Dibujar celdas ocupadas por la ruta >> "%VIZ_SCRIPT%"
echo             for i in range(len(ex)): >> "%VIZ_SCRIPT%"
echo                 rect = Rectangle((ex[i]-5, ey[i]-5), 10, 10, color='#E67E22', alpha=0.3, zorder=4) >> "%VIZ_SCRIPT%"
echo                 ax.add_patch(rect) >> "%VIZ_SCRIPT%"
echo         # 4. TRAYECTORIA REAL (History) >> "%VIZ_SCRIPT%"
echo         ax.plot(hx, hy, '-', color='#555555', linewidth=1.5, alpha=0.7, label='Flown Path', zorder=3) >> "%VIZ_SCRIPT%"
echo         # 5. DRON (GPS Style Pointer - WIDER) >> "%VIZ_SCRIPT%"
echo         angle_rad = math.radians(90 - t['heading']) >> "%VIZ_SCRIPT%"
echo         d_size = 12 # Mas grande >> "%VIZ_SCRIPT%"
echo         # Mas ancho: angulo +/- 2.3 rad (aprox 130 grados) >> "%VIZ_SCRIPT%"
echo         p1 = (dx + d_size*math.cos(angle_rad), dy + d_size*math.sin(angle_rad)) >> "%VIZ_SCRIPT%"
echo         p2 = (dx + d_size*0.7*math.cos(angle_rad + 2.3), dy + d_size*0.7*math.sin(angle_rad + 2.3)) >> "%VIZ_SCRIPT%"
echo         p3 = (dx + d_size*0.7*math.cos(angle_rad - 2.3), dy + d_size*0.7*math.sin(angle_rad - 2.3)) >> "%VIZ_SCRIPT%"
echo         ax.fill([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color='black', zorder=10, label='Drone') >> "%VIZ_SCRIPT%"
echo         # INFO BOX >> "%VIZ_SCRIPT%"
echo         status = "NAVIGATING" >> "%VIZ_SCRIPT%"
echo         if ev['active']: status = "EVADING (A*)" >> "%VIZ_SCRIPT%"
echo         elif len(obs) ^> 0: status = "OBSTACLE DETECTED" >> "%VIZ_SCRIPT%"
echo         info = f"STATUS: {status}\nGPS: {t['lat']:.5f}, {t['lon']:.5f}\nALT: {t['alt']:.1f}m ^| HDG: {t['heading']}deg\nOBS: {len(obs)}" >> "%VIZ_SCRIPT%"
echo         props = dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#333333') >> "%VIZ_SCRIPT%"
echo         # INFO BOX: Abajo al Centro (Bottom Center) >> "%VIZ_SCRIPT%"
echo         ax.text(0.5, 0.03, info, transform=ax.transAxes, fontsize=16, horizontalalignment='center', verticalalignment='bottom', bbox=props, fontfamily='monospace') >> "%VIZ_SCRIPT%"
echo         # ESTILOS FUENTES Y EJES >> "%VIZ_SCRIPT%"
echo         # LEYENDA ESTATICA (FIXED) >> "%VIZ_SCRIPT%"
echo         legend_elements = [ >> "%VIZ_SCRIPT%"
echo             Line2D([0], [0], color='#4C72B0', lw=1.5, ls='--', label='Global Mission'), >> "%VIZ_SCRIPT%"
echo             Line2D([0], [0], color='#555555', lw=1.5, label='Flown Path'), >> "%VIZ_SCRIPT%"
echo             Line2D([0], [0], color='#E67E22', lw=1.5, label='Evasion Path'), >> "%VIZ_SCRIPT%"
echo             Line2D([0], [0], marker='^', color='w', markerfacecolor='black', markersize=10, label='Drone'), >> "%VIZ_SCRIPT%"
echo             Line2D([0], [0], marker='x', color='#C44E52', label='Obstacles', linestyle='None') >> "%VIZ_SCRIPT%"
echo         ] >> "%VIZ_SCRIPT%"
echo         ax.legend(handles=legend_elements, loc='upper right', fontsize=14, framealpha=0.9) >> "%VIZ_SCRIPT%"
echo         ax.tick_params(axis='both', which='major', labelsize=14) >> "%VIZ_SCRIPT%"
echo         ax.set_xlabel("East (m)", fontsize=16, fontweight='bold'); ax.set_ylabel("North (m)", fontsize=16, fontweight='bold') >> "%VIZ_SCRIPT%"
echo         # --- ENCUADRE ESTATICO (CINEMA MODE) --- >> "%VIZ_SCRIPT%"
echo         # Calculamos limites SOLO con la mision para congelar la camara >> "%VIZ_SCRIPT%"
echo         if len(mx) ^> 1: >> "%VIZ_SCRIPT%"
echo             min_x, max_x = min(mx), max(mx) >> "%VIZ_SCRIPT%"
echo             min_y, max_y = min(my), max(my) >> "%VIZ_SCRIPT%"
echo             # Margen fijo generoso >> "%VIZ_SCRIPT%"
echo             pad = 150 >> "%VIZ_SCRIPT%"
echo             ax.set_xlim(min_x - pad, max_x + pad) >> "%VIZ_SCRIPT%"
echo             ax.set_ylim(min_y - pad, max_y + pad) >> "%VIZ_SCRIPT%"
echo             ax.set_aspect('equal', adjustable='datalim') >> "%VIZ_SCRIPT%"
echo         ax.grid(True, linestyle=':', alpha=0.6) >> "%VIZ_SCRIPT%"
echo         # IMPORTANTE: Sin bbox_inches='tight' para evitar saltos entre frames >> "%VIZ_SCRIPT%"
echo         fig.savefig(os.path.join(OUTPUT_DIR, f"frame_{frame:04d}.png"), dpi=150) >> "%VIZ_SCRIPT%"
echo         if frame %% 10 == 0: print(f"[REC] Guardado Frame {frame}") >> "%VIZ_SCRIPT%"
echo         frame += 1; time.sleep(max(0, 1.0 - (time.time() - st))) >> "%VIZ_SCRIPT%"
echo if __name__ == '__main__':  >> "%VIZ_SCRIPT%"
echo     try: main() >> "%VIZ_SCRIPT%"
echo     except Exception as e: print(e) >> "%VIZ_SCRIPT%"

echo [OK] Herramientas generadas.
REM ============================================================================
REM 2. MASTER LOG SERVER
REM ============================================================================
echo [2/6] Iniciando MASTER LOG SERVER...
set "VENV_ACTIVATE=%PROJECT_ROOT%\venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] Entorno virtual no encontrado: %VENV_ACTIVATE%
    pause
    exit /b 1
)

start "MASTER LOG (Do Not Close)" cmd /k "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u log_server.py"
timeout /t 2 /nobreak >nul

REM ============================================================================
REM 3. SITL (WSL)
REM ============================================================================
echo [3/6] Iniciando SITL (WSL)...
for /f "usebackq tokens=*" %%a in (`wsl wslpath -u "%PROJECT_ROOT%\pipeline\run_sitl.sh"`) do set SITL_SCRIPT_PATH=%%a
start "ArduPilot SITL" cmd /k "wsl -e bash "%SITL_SCRIPT_PATH%""

REM ============================================================================
REM 4. FLIGHT CONTROLLER (Brain)
REM ============================================================================
echo [4/6] Iniciando FLIGHT CONTROLLER...
REM NOTA: Ejecucion nativa con API de observabilidad integrada
start "FLIGHT CONTROLLER %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200"

REM ============================================================================
REM 5. VISION SYSTEM (Eyes)
REM ============================================================================
echo [5/6] Iniciando VISION SYSTEM...
timeout /t 1 /nobreak >nul
start "VISION SYSTEM %WINDOW_TITLE_SUFFIX%" cmd /c "set PORCE_SYSTEM_MODE=%PORCE_SYSTEM_MODE% && call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200"

REM ============================================================================
REM 6. VIZ RECORDER (NUEVO)
REM ============================================================================
echo [6/6] Iniciando VIZ RECORDER...
start "VIZ RECORDER" cmd /c "call "%VENV_ACTIVATE%" && cd "%PROJECT_ROOT%\pipeline" && python -u viz_recorder.py"

echo.
echo [OK] Sistema Lanzado.
echo.
echo  - Ventana "MASTER LOG": Muestra todos los logs en tiempo real.
echo  - Archivo Maestro: pipeline\logs\SYSTEM_ALL.log
echo  - Visualizacion: pipeline\logs\viz_frames (frames PNG generados)
echo.
pause