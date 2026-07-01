# Deep-AeroTwin (PORCE)

Repositorio para ejecutar PORCE en Windows + WSL2 con dos workflows distintos:

- `SIMULATION`: SITL + Brain + Vision + Viz + twin Unreal opcional. Es el flujo autónomo con misión, waypoints y evasión.
- `DIGITAL TWIN` / `REAL_TWIN`: vuelo real con piloto humano usando Unreal como interfaz principal. No hay misión ni waypoints; Unreal representa entidades reales con `spawn/update/despawn`.

## Workflows del repo

Resumen corto:

| Workflow | Propósito | Control del dron | Papel de Unreal | Estado actual |
|---|---|---|---|---|
| `SIMULATION` | Validar pipeline completo en entorno simulado | Autónomo, con misión y evasión PORCE | Consumidor opcional de `GET /api/ui/data` | Cerrado y validado |
| `DIGITAL TWIN` / `REAL_TWIN` | Soporte visual al piloto en vuelo real | Piloto humano, sin ruta automática | Interfaz operativa principal; representa entidades reales | Implementado con launcher y runtime pasivo dedicados |

Documento dedicado en raíz: [`WORKFLOWS.md`](WORKFLOWS.md)

## Lanzadores

- `LANZAR_TODO_PAPER.bat`: arranque completo para paper: prepara Unreal, abre PIE y lanza la pipeline.
- `tools\launch_workflow.bat SIMULATION`: arranque directo del workflow `SIMULATION` si Unreal/PIE ya esta preparado.
- `tools\launch_workflow.bat REAL_TWIN`: arranque directo del workflow `DIGITAL TWIN` / `REAL_TWIN`.
- Stop global: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\stop_pipeline.ps1`

Nota:

- Hoy el launcher de raíz validado para el paper es `LANZAR_TODO_PAPER.bat`.
- Los wrappers historicos de raiz estan archivados en `tools\legacy_root_bats\`.
- `tools\launch_workflow.bat REAL_TWIN` levanta el perfil pasivo `REAL_TWIN` sin SITL ni `vision_system.py` local.

## Bootstrap reproducible (zero-trust)

Preparación recomendada para clonado limpio:

1. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\bootstrap.ps1`
2. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\preflight_zero_trust.ps1`
3. Si falta SITL: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_sitl_wsl.ps1`
4. Arranque completo paper: `LANZAR_TODO_PAPER.bat`

Notas:

- Dependencias Python fijadas en `pipeline\requirements.lock.txt`.
- `tools\launch_workflow.bat` no persiste token por defecto (`PORCE_OBSTACLE_TOKEN_PERSIST=0`).
- El proyecto Unreal requiere `CesiumForUnreal` y `VaRest` (plugins externos a este repo).
- Las herramientas Unreal resuelven UE 5.7 desde `PORCE_UNREAL_ENGINE_ROOT` o `UE_ENGINE_ROOT`; si no estan definidos, prueban las rutas Epic Games habituales.

## Workflow 1: SIMULATION (flujo validado)

`tools\launch_workflow.bat SIMULATION` carga defaults y levanta:

1. `pipeline\log_server.py` (MASTER LOG)
2. `pipeline\run_sitl.sh` (SITL en WSL)
3. `pipeline\flight_controller.py` (BRAIN)
4. `pipeline\vision_system.py` (EYES)
5. `pipeline\viz_recorder.py` (VIZ)

Fuente de verdad runtime: `pipeline\porce_defaults.env` + `pipeline\constants.py`.

## Workflow 2: DIGITAL TWIN / REAL_TWIN

Objetivo operativo:

- No hay ruta automática, waypoints ni evasión como centro del sistema.
- El dron vuela en entorno real con piloto humano.
- Unreal es la interfaz visual principal del piloto.
- El sistema recibe detecciones reales y publica entidades hacia Unreal con identidad estable y posición georreferenciada.
- Unreal hace `spawn/update/despawn` de actores para que el piloto vea en escena los objetos reales aunque no dependa del vídeo del dron.

Cadena funcional esperada:

1. Detección real.
2. Normalización de entidad con `entity_id` estable, `type`, `confidence` y `lat/lon` y/o `world_m`.
3. Publicación del estado al Brain.
4. Exposición por `GET /api/ui/data`.
5. Consumo desde Unreal por `UPorceTelemetryComponent`.
6. `spawn/update/despawn` en la escena.

Conjunto de entidades objetivo del workflow `DIGITAL TWIN`:

- `bike`
- `cow`
- `tower`

Estado actual del repo para este workflow:

- El perfil `REAL_TWIN` arranca sin misión y sin `control_loop()` autónomo.
- El launcher directo dedicado es `tools\launch_workflow.bat REAL_TWIN`.
- En este workflow no se levanta `vision_system.py`; el YOLO real del dron publica a `POST /api/obstacles`.
- `GET /api/ui/data` mantiene el mismo shape que en `SIMULATION`, pero en `REAL_TWIN` devuelve `waypoints: []` y un bloque `evasion` inerte.
- El Brain normaliza `biker` / `person` / `bicycle` a `bike` y reemite solo tipos canónicos.
- El consumidor Unreal resuelve `bike`, `cow` y `tower`; `bike` reutiliza el actor actual de biker.

## TL;DR rápido del workflow SIMULATION

1. Vision detecta objetos, los proyecta a GPS y los envía al Brain por `POST /api/obstacles`.
2. Brain decide con el obstáculo más cercano: si entra en distancia de reacción, intenta evasión con A*.
3. A* usa grid local (`6m` por celda, `81x81`, diagonales permitidas) y burbuja de seguridad (`12m`).
4. El objetivo de evasión es siempre el waypoint actual: `wps[current_wp_idx]`.
5. Si A* falla cerca (`<=22m`), activa failsafe por etapas: `HOLD -> REPLAN_LATERAL -> LAND/RTL`.
6. El dron vuela subpuntos `lat/lon` (no celdas), y vuelve a misión normal al terminar evasión.

## Cómo funciona PORCE en SIMULATION (detalle completo, paso a paso)

### 1) Entradas y salidas exactas

| Emisor | Canal / endpoint | Receptor | Datos | Uso |
|---|---|---|---|---|
| ArduPilot/SITL | MAVLink (`GLOBAL_POSITION_INT`, `ATTITUDE`, `HEARTBEAT`, `VFR_HUD`) | Brain | `lat/lon/alt/rel_alt/yaw/mode/armed/groundspeed` | Estado real del vuelo |
| Brain | `GET /api/state/latest` | Vision | Telemetría fusionada (`mavlink` o `unreal_truth`) | Proyección píxel -> GPS |
| Vision | `POST /api/obstacles` | Brain | `obstacles[]` (`lat/lon/distance/type/confidence/source`) | Ingesta de obstáculos |
| Unreal (opcional) | `POST /api/unreal/telemetry` | Brain | Telemetría de escena | Sustitución temporal para Vision |
| Brain | MAVLink (`set_position_target_global_int_send`, `set_mode`) | ArduPilot/SITL | Objetivo geográfico o `LAND/RTL` | Navegación normal/evasión/failsafe |
| Unreal/Viz | `GET /api/ui/data` | Brain | Consulta | Estado para visualización |

### 2) Parámetros activos clave (defaults del repo)

- Modo: `PORCE_SYSTEM_MODE=SIMULATION`
- Celda de grid A*: `PORCE_GRID_CELL_SIZE_M=6`
- Radio de seguridad planner: `PORCE_PLANNER_SAFETY_DISTANCE_M=12`
- Radio del grid: `PORCE_PLANNER_GRID_RADIUS_CELLS=40` (grid total `81x81`)
- Diagonal en grid: `PORCE_PLANNER_ALLOW_DIAGONAL=1`
- Distancia de reacción base: `PORCE_EVASION_REACTION_BASE_M=45`
- Ganancia por velocidad: `PORCE_EVASION_REACTION_SPEED_GAIN_S=2.0`
- Reacción mínima/máxima: `45m` / `80m`
- Replan mínimo entre intentos: `PORCE_EVASION_REPLAN_MIN_INTERVAL_S=1.0`
- Replan con evasión activa: `PORCE_EVASION_ALLOW_REPLAN_WHEN_ACTIVE=1`
- Distancia máxima para replan activo: `PORCE_EVASION_ACTIVE_REPLAN_DISTANCE_M=60`
- Subconjunto para planner: `<=55m` y máximo `16` obstáculos
- Zona crítica failsafe: `PORCE_EVASION_FAILSAFE_MIN_DIST_M=22`
- Hold de seguridad: `PORCE_EVASION_FAILSAFE_HOLD_S=2.5`
- Escalado failsafe: `PORCE_EVASION_FAILSAFE_ESCALATE_ENABLE=1`
- Acción terminal: `PORCE_EVASION_FAILSAFE_ESCALATE_ACTION=LAND`
- Rango de detección de Vision en SIM (si no override): `DETECTION_RANGE_M=80m`
- Umbral detección/publicación Vision: `0.10` / `0.35`
- Mínimo de vistas para publicar: `biker=3`, `cow=3`, `tower=3`
- Máscara imagen: `top=0px`, `bottom=40px`

### 3) Qué waypoint usa como referencia

1. La misión se carga desde `pipeline\ejea_default.waypoints`.
2. `wps[0]` es `home`.
3. El índice inicial de navegación es `current_wp_idx=1`.
4. PORCE siempre planifica hacia `wps[current_wp_idx]`.
5. No usa por defecto `siguiente + x`.
6. Solo avanza de waypoint cuando:
7. Entra en tolerancia y no está bloqueado.
8. O se fuerza avance por bloqueo prolongado (`PORCE_EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE=1`).

### 4) Ciclo de decisión real del Brain (orden exacto)

1. Lee telemetría y tracks de obstáculos activos.
2. Si telemetría está stale, no decide navegación en ese ciclo.
3. Si hay `failsafe_action_active` (`HOLD/LAND/RTL`), esa acción manda y se ejecuta primero.
4. Gestiona estado de arm/takeoff cuando está en WP1.
5. Calcula distancia al waypoint actual.
6. Si está dentro de tolerancia de waypoint, evalúa si el waypoint está bloqueado por obstáculos.
7. Calcula distancia de reacción dinámica:
8. `reaction_m = clamp(base + groundspeed * gain, min, max)`.
9. Busca obstáculo más cercano.
10. Si no hay obstáculo o está fuera de reacción, no dispara A*.
11. Si está dentro de reacción, evalúa permisos de replan:
12. Respeta intervalo mínimo (`1.0s`).
13. Si ya hay evasión activa, además exige `distancia_obstáculo <= 60m`.
14. Si procede, lanza A* hacia el waypoint actual.
15. Si A* devuelve ruta válida (mínimo `2` puntos), activa evasión.
16. Si A* falla y está en zona crítica (`<=22m`), activa cadena failsafe por etapas.
17. Si A* falla fuera de zona crítica, aplica hold preventivo (si está configurado).
18. Si no hay evasión activa, navega normal al waypoint.

### 5) ¿Cuándo considera peligro?

Se considera situación de peligro operativo cuando el obstáculo más cercano entra en la distancia de reacción:

- Condición de disparo: `distancia_obstáculo_más_cercano < reaction_m`
- Con defaults actuales en SIM:
- Reacción mínima: `45m`
- Reacción máxima: `80m`
- A mayor velocidad, mayor distancia de reacción dentro de ese rango.

### 6) Grid, diagonales y por dónde “viaja” realmente

1. El planner usa A* sobre grid local centrado en el dron.
2. Tamaño de celda: `6m`.
3. Radio de grid: `40` celdas (`240m` aprox de radio local).
4. Total: `81 x 81` celdas.
5. Movimiento permitido en A*: cardinal y diagonal (8 vecinos).
6. Coste cardinal: `1.0`.
7. Coste diagonal: `1.41421356`.
8. El dron no vuela “por celdas” directamente.
9. A* calcula celdas, luego se convierten a subpuntos `lat/lon`.
10. El Brain envía esos subpuntos geográficos por MAVLink al autopiloto.

### 7) Burbuja de seguridad (mínimo de separación)

1. Burbuja del planner: `12m` (`PORCE_PLANNER_SAFETY_DISTANCE_M`).
2. Con celda `6m`, esto infla obstáculos en `ceil(12/6)=2` celdas alrededor.
3. Distancia crítica para failsafe fuerte: `22m` (`PORCE_EVASION_FAILSAFE_MIN_DIST_M`).

### 8) Bloqueo de waypoint y deadlock

1. Tolerancia de llegada en SIM: `5.5m` (`ARRIVAL_TOLERANCE_M`).
2. Dentro de tolerancia, se comprueba bloqueo de corredor al waypoint:
3. Semiancho de corredor: `12m`.
4. Umbral de obstáculo cercano para bloquear avance: `22m`.
5. Si el bloqueo dura `>=6s`:
6. Con `FORCE_ADVANCE=1`: avanza al siguiente waypoint.
7. Con `FORCE_ADVANCE=0`: activa `LAND` en sitio.

### 9) Movimiento lateral: si existe, cómo se calcula

Sí existe, en etapa failsafe `REPLAN_LATERAL`.

1. Toma el vector de avance al waypoint actual.
2. Calcula un vector lateral perpendicular.
3. Genera dos lados posibles (`+lateral` y `-lateral`).
4. Añade componente forward (`PORCE_EVASION_FAILSAFE_LATERAL_FORWARD_GAIN=0.5`).
5. Usa offset lateral base `22m`.
6. Prioriza el lado que deje más separación al obstáculo cercano.
7. Ese objetivo lateral también pasa por A* (con diagonales habilitadas).

### 10) Failsafe por etapas (actual)

- Ventana de conteo: `12s`
- Cooldown de escalado: `20s`
- Etapa 1: `3` fallos -> `HOLD`
- Etapa 2: `5` fallos -> `REPLAN_LATERAL`
- Etapa 3: `6` fallos -> `LAND` (o `RTL` si se configura)

### 11) Pseudocódigo corto

```python
while True:
    refresh_telemetry_and_obstacles()
    if telemetry_stale:
        continue

    if failsafe_action_active:
        execute_failsafe_action()
        continue

    wp = waypoints[current_wp_idx]
    reaction = clamp(base + groundspeed * gain, min_r, max_r)
    nearest = nearest_obstacle()

    if nearest and nearest.dist < reaction and replan_allowed_now():
        route = astar_local(drone_pos, wp, planner_subset_obstacles())
        if valid(route):
            activate_evasion(route)
        else:
            apply_failsafe_escalation(nearest.dist)

    if evasion_active:
        follow_evasion_subpoints()
    else:
        follow_mission_waypoint(wp)
```

## Auditoría zero-trust (estado de código)

### Confirmado

- Source filter activo en Brain (`OBS_SOURCE_FILTER_ENABLE=1`, allowed `vision`).
- Token obligatorio en `/api/obstacles`.
- Bind local del Brain (`127.0.0.1`).
- Tracking estático/dinámico diferenciado en Vision y Brain.
- Ruta de misión cargada desde `pipeline\ejea_default.waypoints`.

### Hallazgos importantes

- `WP_TOLERANCE_M` viene de `ARRIVAL_TOLERANCE_M` y en SIM es `5.5m`.
- La ruta `0 -> 11` es principalmente hacia el SE (lat baja, lon sube).
- Replan en evasión activa conectado a `EVASION_ALLOW_REPLAN_WHEN_ACTIVE` + `EVASION_ACTIVE_REPLAN_DISTANCE_M`.
- Escalado de failsafe por etapas conectado: `HOLD -> REPLAN_LATERAL -> LAND/RTL`.
- Con `PORCE_EVASION_FAILSAFE_ESCALATE_ENABLE=1`, el escalado por etapas está activo.
- El rechazo por source se reporta en `obstacle_ingest` como `rejected_by_source`.

## Logs y auditoría

Cada sesión escribe en `pipeline\logs\zero_trust\<timestamp>\`:

- `SYSTEM_ALL.log`
- `brain\events.jsonl`
- `brain\trajectory.csv`
- `vision\events.jsonl`
- `vision\frames\*.jpg` (si está activo)

`LATEST_RUN.txt` apunta a la última sesión.

## Runbook rapido del workflow SIMULATION

- Cargar y arrancar paper completo: `LANZAR_TODO_PAPER.bat`
- Arranque directo sin preparar Unreal: `tools\launch_workflow.bat SIMULATION`
- Parar todo: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\stop_pipeline.ps1`
- Smoke local sin SITL real (mock MAVLink):
- `set PORCE_MOCK_MAVLINK=1`
- `cd pipeline`
- `python flight_controller.py`

## Unreal Twin C++ (estado actual, compartido y crítico para DIGITAL TWIN)

- Plugin runtime: `Unreal\Plugins\PorceTelemetry`
- Componente C++: `UPorceTelemetryComponent` (en Unreal se muestra como `PORCE Twin V2 Component`)
- Modo actual: consume entidades del Brain por `GET /api/ui/data` y hace `spawn/update/despawn`.
- Ya no publica telemetría del dron.

Contrato de payload:

- `telemetry`: posición del dron (`lat`, `lon`, `alt`, `rel_alt`) y `world_m` (`north`, `east`, `up`) relativo a `home`.
- `obstacles[]`: incluye `entity_id`, `object_id`, `type/object_type`, `confidence`, `lat`, `lon`, `world_m`.
- El componente C++ prioriza `world_m`; si no existe, usa `lat/lon`.

Config mínima en Unreal:

- `bEnabled=true`
- `EndpointUrl=http://127.0.0.1:8080/api/ui/data`
- `PollRateHz=5`
- `DespawnAfterS=3`
- `ConfirmedConfidenceThreshold=0.65`
- Blueprints en `/Game`: `BP_Tower`, `BP_Cow`, `BP_Biker`
- Asignar clases: `TowerActorClass=BP_Tower`, `CowActorClass=BP_Cow`, `BikerActorClass=BP_Biker`

Auth/flags:

- Activar twin: `bEnabled=true`
- Override por entorno: `PORCE_UNREAL_TWIN_ENABLE=0/1`
- Prioridad token: `AuthToken` (componente) -> `PORCE_UNREAL_TWIN_TOKEN` -> `PORCE_OBSTACLE_TOKEN`

Georreferenciación (componente):

- `HomeLatDeg`, `HomeLonDeg`
- ENU->Local: `EastFromLocalX`, `EastFromLocalY`, `NorthFromLocalX`, `NorthFromLocalY`
- `CmToMScale`
- `OriginActor`

Spawn sintético antiguo:

- El wrapper `launch_spawner.bat` se retiró del flujo operativo porque dependía de scripts temporales bajo `tmp\`.
- Para pruebas reproducibles de obstáculos se usa la pipeline normal con logs/auditoría zero-trust, o el harness documentado en `tools\run_paper_wp1_wp2_tower.py` para la Figura 1.


### Backend SPPA opcional

`UPorceTelemetryComponent` puede alternar dos backends de spawn que consumen el mismo `GET /api/ui/data`:

- `UnrealAssets`: modo por defecto; spawnea los Blueprints/actores existentes (`BikerActorClass`, `CowActorClass`, `TowerActorClass`, `DefaultObstacleActorClass`).
- `SemanticProxy`: backend SPPA; genera proxies 3D ligeros con primitivas runtime.

El switch en viewport y la API Blueprint se documentan en `Unreal\Plugins\PorceTelemetry\README_SPPA_BACKEND.md`.

Smoke de reflexión y generación del backend SPPA:

- `powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1`
- Incluido por defecto en `powershell -NoProfile -ExecutionPolicy Bypass -File tools\audit_zero_trust_e2e.ps1`.
- Para una instalación no estándar de UE 5.7: `$env:PORCE_UNREAL_ENGINE_ROOT="D:\Ruta\UE_5.7"`.

## Peso YOLO canónico

Peso único del repo:

- `yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`

Default:

- `PORCE_YOLO_MODEL=%PROJECT_ROOT%\yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`

## Scripts retirados del runtime

No forman parte del flujo principal:

- `tools\check_status.py`
- `tools\validate_latest_run.bat`
- `tools\validate_zero_trust_run.py`

Documentación histórica: `docs/archive/`.
