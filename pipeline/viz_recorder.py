#/usr/bin/env python3 
import matplotlib 
matplotlib.use('Agg') 
import matplotlib.pyplot as plt 
from matplotlib.patches import Circle, Rectangle 
from matplotlib.lines import Line2D 
import requests, math, time, os, shutil 
from constants import MAVLINK_HUB_HTTP_PORT, EARTH_RADIUS_M 
API_URL = f"http://127.0.0.1:{MAVLINK_HUB_HTTP_PORT}/api/ui/data" 
OUTPUT_DIR = os.path.join("logs", "viz_frames") 
def latlon_to_meters(lat, lon, home_lat, home_lon): 
    dlat = math.radians(lat - home_lat) 
    dlon = math.radians(lon - home_lon) 
    return dlon * EARTH_RADIUS_M * math.cos(math.radians(home_lat)), dlat * EARTH_RADIUS_M 
def main(): 
    if os.path.exists(OUTPUT_DIR): 
        try: shutil.rmtree(OUTPUT_DIR) 
        except: pass 
    os.makedirs(OUTPUT_DIR, exist_ok=True) 
    plt.style.use('seaborn-v0_8-whitegrid') 
    # RESOLUCION AUMENTADA (16x16 pulgadas a 150 DPI) 
    fig, ax = plt.subplots(figsize=(16, 16)) 
    frame = 0; hx, hy = [], [] 
    print(f"[VIZ] Iniciando motor grafico...") 
    while True: 
        st = time.time() 
        try:  
            r = requests.get(API_URL, timeout=0.5) 
            data = r.json() if r.status_code==200 else None 
        except: data = None 
        if not data or not data.get('home'): 
            time.sleep(1); continue 
        h, t, obs, ev, wps = data['home'], data['telemetry'], data['obstacles'], data['evasion'], data['waypoints'] 
        # Conversiones 
        dx, dy = latlon_to_meters(t['lat'], t['lon'], h['lat'], h['lon']) 
        hx.append(dx); hy.append(dy) 
        if len(hx)>2000: hx.pop(0); hy.pop(0) 
        ax.clear() 
        # 1. RUTA MISION (Global Plan) 
        mx, my = [0], [0] # Home 
        ax.text(0, 0, 'HOME', fontsize=10, fontweight='bold', color='#4C72B0') 
        for i, wp in enumerate(wps): 
            wx, wy = latlon_to_meters(wp['lat'], wp['lon'], h['lat'], h['lon']) 
            mx.append(wx); my.append(wy) 
            if i > 0: ax.text(wx+5, wy+5, f'WP{i}', fontsize=10, color='#4C72B0') 
        ax.plot(mx, my, '--', color='#4C72B0', linewidth=1.5, label='Global Mission', zorder=1) 
        ax.scatter(mx, my, marker='', color='#4C72B0', s=80, zorder=2) 
        # 2. OBSTACULOS 
        for o in obs: 
            ox, oy = latlon_to_meters(o['lat'], o['lon'], h['lat'], h['lon']) 
            ax.add_patch(Circle((ox, oy), data['params']['safety_dist'], color='#C44E52', alpha=0.3)) 
            ax.plot(ox, oy, 'x', color='#C44E52') 
        if ev['active'] and ev['path'] and ev.get('grid_origin'): 
            # Calcular origen del grid en metros 
            gox, goy = latlon_to_meters(ev['grid_origin']['lat'], ev['grid_origin']['lon'], h['lat'], h['lon']) 
            # DIBUJAR GRID (400m x 400m alrededor del origen) 
            grid_sz = 10 # 10 metros 
            radius = 150 # Radio visual del grid 
            # Lineas verticales 
            for gx in range(int(gox)-radius, int(gox)+radius, grid_sz): 
                # Alinear al origen del grid 
                offset = (gx - gox) % grid_sz 
                line_x = gx - offset 
                ax.plot([line_x, line_x], [goy-radius, goy+radius], '-', color='#DDDDDD', linewidth=0.5, zorder=0) 
            # Lineas horizontales 
            for gy in range(int(goy)-radius, int(goy)+radius, grid_sz): 
                offset = (gy - goy) % grid_sz 
                line_y = gy - offset 
                ax.plot([gox-radius, gox+radius], [line_y, line_y], '-', color='#DDDDDD', linewidth=0.5, zorder=0) 
            # DIBUJAR RUTA COMO CELDAS 
            ex = [dx] + [latlon_to_meters(p['lat'], p['lon'], h['lat'], h['lon'])[0] for p in ev['path']] 
            ey = [dy] + [latlon_to_meters(p['lat'], p['lon'], h['lat'], h['lon'])[1] for p in ev['path']] 
            ax.plot(ex, ey, '-', color='#E67E22', linewidth=1.5, label='Evasion Path', zorder=5) 
            # Dibujar celdas ocupadas por la ruta 
            for i in range(len(ex)): 
                rect = Rectangle((ex[i]-5, ey[i]-5), 10, 10, color='#E67E22', alpha=0.3, zorder=4) 
                ax.add_patch(rect) 
        # 4. TRAYECTORIA REAL (History) 
        ax.plot(hx, hy, '-', color='#555555', linewidth=1.5, alpha=0.7, label='Flown Path', zorder=3) 
        # 5. DRON (GPS Style Pointer - WIDER) 
        angle_rad = math.radians(90 - t['heading']) 
        d_size = 12 # Mas grande 
        # Mas ancho: angulo +/- 2.3 rad (aprox 130 grados) 
        p1 = (dx + d_size*math.cos(angle_rad), dy + d_size*math.sin(angle_rad)) 
        p2 = (dx + d_size*0.7*math.cos(angle_rad + 2.3), dy + d_size*0.7*math.sin(angle_rad + 2.3)) 
        p3 = (dx + d_size*0.7*math.cos(angle_rad - 2.3), dy + d_size*0.7*math.sin(angle_rad - 2.3)) 
        ax.fill([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color='black', zorder=10, label='Drone') 
        # INFO BOX 
        status = "NAVIGATING" 
        if ev['active']: status = "EVADING (A*)" 
        elif len(obs) > 0: status = "OBSTACLE DETECTED" 
        info = f"STATUS: {status}\nGPS: {t['lat']:.5f}, {t['lon']:.5f}\nALT: {t['alt']:.1f}m ^| HDG: {t['heading']}deg\nOBS: {len(obs)}" 
        props = dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#333333') 
        # INFO BOX: Abajo al Centro (Bottom Center) 
        ax.text(0.5, 0.03, info, transform=ax.transAxes, fontsize=16, horizontalalignment='center', verticalalignment='bottom', bbox=props, fontfamily='monospace') 
        # ESTILOS FUENTES Y EJES 
        # LEYENDA ESTATICA (FIXED) 
        legend_elements = [ 
            Line2D([0], [0], color='#4C72B0', lw=1.5, ls='--', label='Global Mission'), 
            Line2D([0], [0], color='#555555', lw=1.5, label='Flown Path'), 
            Line2D([0], [0], color='#E67E22', lw=1.5, label='Evasion Path'), 
            Line2D([0], [0], marker='', color='w', markerfacecolor='black', markersize=10, label='Drone'), 
            Line2D([0], [0], marker='x', color='#C44E52', label='Obstacles', linestyle='None') 
        ] 
        ax.legend(handles=legend_elements, loc='upper right', fontsize=14, framealpha=0.9) 
        ax.tick_params(axis='both', which='major', labelsize=14) 
        ax.set_xlabel("East (m)", fontsize=16, fontweight='bold'); ax.set_ylabel("North (m)", fontsize=16, fontweight='bold') 
        # --- ENCUADRE ESTATICO (CINEMA MODE) --- 
        # Calculamos limites SOLO con la mision para congelar la camara 
        if len(mx) > 1: 
            min_x, max_x = min(mx), max(mx) 
            min_y, max_y = min(my), max(my) 
            # Margen fijo generoso 
            pad = 150 
            ax.set_xlim(min_x - pad, max_x + pad) 
            ax.set_ylim(min_y - pad, max_y + pad) 
            ax.set_aspect('equal', adjustable='datalim') 
        ax.grid(True, linestyle=':', alpha=0.6) 
        # IMPORTANTE: Sin bbox_inches='tight' para evitar saltos entre frames 
        fig.savefig(os.path.join(OUTPUT_DIR, f"frame_{frame:04d}.png"), dpi=150) 
        if frame % 10 == 0: print(f"[REC] Guardado Frame {frame}") 
        frame += 1; time.sleep(max(0, 1.0 - (time.time() - st))) 
if __name__ == '__main__':  
    try: main() 
    except Exception as e: print(e) 
