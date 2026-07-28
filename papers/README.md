# Papers del proyecto Deep-AeroTwin

Tres publicaciones derivadas del mismo sistema (digital twin UAV en Unreal Engine 5.7 + pipeline de percepción YOLO). Cada carpeta es un repo git independiente con su propio `README.md` que detalla manuscrito canónico y compilación.

| Carpeta | Paper | Venue | Rol |
|---|---|---|---|
| `pipeline_a_telemetry/` | *A VR-Headset Visual Pipeline for UAV Pilot Situational Awareness: Combining Geospatial Priors and Semantic Object State in an Unreal Engine Digital Twin* | VRIH | **Paper principal** |
| `porce_collision_evasion/` | *Regulatory Compliant Moving Obstacle Avoidance Navigation Algorithm for Drone-Based Power Line Inspection* | IEEE TII | Evasión de obstáculos (PORCE) |
| `semantic_proxy_3d/` | *Instant Semantic Proxy Reconstruction for UAV Digital Twins under Degraded Sensing (SPPA-MVFit)* | JGSA | Generación 3D (SPPA) |

## Aportación de cada uno

- **pipeline_a_telemetry** — Pipeline visual de digital twin para teleoperación UAV con casco VR: un prior geoespacial (Unreal + Cesium) aporta el contexto estático y la telemetría semántica de objetos se reconstruye como actores con incertidumbre en la escena del piloto. Validado con replay de vuelo real: 0.24 m de fidelidad de trayectoria, −84 % de ancho de banda frente a H.264, 38 ms de latencia detección→display.
- **porce_collision_evasion** — Replanificador local determinista en tiempo real que preserva waypoints e **operacionaliza la lógica EASA/SORA** (no sobrevolar personas no involucradas) dentro del planner online: las detecciones de civiles se convierten en regiones protegidas temporales con radios por clase (regla 1:1 del Ground Risk Buffer) que fuerzan desvíos conservadores y auditables.
- **semantic_proxy_3d** — Reconstrucción instantánea de proxies semánticos 3D por detección para mantener el twin cuando el video se degrada: cada track YOLO se compila en un actor de 8 primitivas (grafo de partes condicionado por familia) en 9.4 ms de CPU con un descriptor de 1.45 kB, sin GPU. Evidencia preregistrada en 240 actores held-out: +0.190 IoU de vóxel frente al grafo genérico.

## Convención de limpieza

En cada paper: el manuscrito canónico y sus ficheros de submission están en la raíz de la carpeta, `figures/` contiene solo las figuras referenciadas por el `.tex`, y las versiones antiguas, auditorías y notas de sesión viven en `_archive/` (o `_source_archives/` en el caso de PORCE). El material experimental pesado de SPPA (`generators/`, `experiments_root/`, `model_cache/`) es soporte regenerable, no parte del manuscrito.
