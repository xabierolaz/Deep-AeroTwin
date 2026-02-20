# Deep-AeroTwin (PORCE)

Repositorio para ejecutar PORCE en Windows + WSL2 con dos flujos:

- **Pipeline A (SIMULATION):** SITL + Brain + Vision + Viz.
- **Pipeline B (REAL_TWIN):** Brain + Vision por video + consumo en Unreal.

## Lanzadores

- **A:** `launch.bat`
- **B:** `b_launch_pipeline.bat`
- **Stop global:** `powershell -NoProfile -ExecutionPolicy Bypass -File tools\stop_pipeline.ps1`

## Pipeline A (flujo real)

`launch.bat` carga defaults y levanta:

- `pipeline\log_server.py` (MASTER LOG)
- `pipeline\run_sitl.sh` (SITL en WSL)
- `pipeline\flight_controller.py` (BRAIN)
- `pipeline\vision_system.py` (EYES)
- `pipeline\viz_recorder.py` (VIZ)

Fuente de verdad runtime: `pipeline\porce_defaults.env` + `pipeline\constants.py`.

## Pipeline A (valores vigentes clave)

- `PORCE_BRAIN_APP_BIND_HOST=127.0.0.1`
- `PORCE_OBSTACLE_TOKEN_REQUIRED=1`
- `PORCE_GRID_CELL_SIZE_M=6`
- `PORCE_SAFETY_DISTANCE_M=12`
- `PORCE_OBS_TRACK_TTL_STATIC_S=30.0`
- `PORCE_OBS_TRACK_TTL_DYNAMIC_S=4.0`
- `PORCE_EVASION_REPLAN_MIN_INTERVAL_S=1.0`
- `PORCE_EVASION_ALLOW_REPLAN_WHEN_ACTIVE=0`
- `PORCE_EVASION_ACTIVE_REPLAN_DISTANCE_M=35.0`
- `PORCE_EVASION_PLANNER_OBS_MAX_DISTANCE_M=55.0`
- `PORCE_EVASION_PLANNER_OBS_MAX_COUNT=16`
- `PORCE_EVASION_FAILSAFE_MIN_DIST_M=22.0`
- `PORCE_EVASION_FAILSAFE_HOLD_S=2.5`
- `PORCE_EVASION_FAILSAFE_ESCALATE_ENABLE=0`
- `PORCE_EVASION_FAILSAFE_ESCALATE_ACTION=LAND`
- `PORCE_VISION_DET_CONF=0.10`
- `PORCE_VISION_PUBLISH_CONF=0.35`
- `PORCE_VISION_MIN_SEEN_TO_PUBLISH_BIKER=2`
- `PORCE_VISION_MIN_SEEN_TO_PUBLISH_COW=3`
- `PORCE_VISION_MIN_SEEN_TO_PUBLISH_TOWER=4`
- `PORCE_VISION_IGNORE_TOP_PX=50`
- `PORCE_VISION_IGNORE_BOTTOM_PX=40`

## Auditoria zero-trust (estado real de codigo)

### Confirmado

- Source filter activo en Brain (`OBS_SOURCE_FILTER_ENABLE=1`, allowed `vision`).
- Token obligatorio en `/api/obstacles`.
- Bind local del Brain (`127.0.0.1`).
- Tracking estatico/dinamico diferenciado en Vision y Brain.
- Ruta de mision cargada desde `pipeline\ejea_default.waypoints`.

### Hallazgos importantes

- `WP_TOLERANCE_M` viene de `ARRIVAL_TOLERANCE_M` y en SIM es `5.5m` (no `5.0m`).
- La ruta 0->11 es principalmente hacia el **SE** (lat baja, lon sube), no NE->SW.
- Replan en evasion activa ya esta conectado a `EVASION_ALLOW_REPLAN_WHEN_ACTIVE` + `EVASION_ACTIVE_REPLAN_DISTANCE_M`.
- Escalado de failsafe por etapas ya esta conectado: `HOLD -> REPLAN_LATERAL -> LAND/RTL`.
- Con `PORCE_EVASION_FAILSAFE_ESCALATE_ENABLE=0` (default actual), el comportamiento sigue siendo **hold-only por configuracion**.
- El rechazo por source se reporta en `obstacle_ingest` como `rejected_by_source` (no como evento separado).

## Logs y auditoria

Cada sesion escribe en `pipeline\logs\zero_trust\<timestamp>\`:

- `SYSTEM_ALL.log`
- `brain\events.jsonl`
- `brain\trajectory.csv`
- `vision\events.jsonl`
- `vision\frames\*.jpg` (si esta activo)

`LATEST_RUN.txt` apunta a la ultima sesion.

## Runbook rapido (A)

- Cargar y arrancar: `launch.bat`
- Parar todo: `powershell -NoProfile -ExecutionPolicy Bypass -File tools\stop_pipeline.ps1`
- Smoke local sin SITL real (mock MAVLink):
  - `set PORCE_MOCK_MAVLINK=1`
  - `cd pipeline`
  - `python flight_controller.py`

## Pipeline B (flujo real)

`b_launch_pipeline.bat` usa `pipeline\b_porce_defaults.env` y levanta:

- `pipeline\log_server.py`
- `pipeline\flight_controller.py` (`REAL_TWIN`)
- `pipeline\vision_system.py` (video/mock)
- `pipeline\viz_recorder.py`

## Unreal Twin C++ (estado actual)

- Plugin runtime: `Unreal\Plugins\PorceTelemetry`
- Componente: `UPorceTelemetryComponent`
- Modo actual: consume entidades del Brain por `GET /api/ui/data` y hace `spawn/update/despawn`.
- Ya no publica telemetria del dron.

Config minima en Unreal:

- `bEnabled=true`
- `EndpointUrl=http://127.0.0.1:8080/api/ui/data`
- `PollRateHz=5`
- `DespawnAfterS=3`
- `ConfirmedConfidenceThreshold=0.65`
- Asignar clases: `TowerActorClass`, `CowActorClass`, `BikerActorClass` (opcional `DefaultObstacleActorClass`)

Auth/flags:

- Activar twin: `PORCE_UNREAL_TWIN_ENABLE=1`
- Token por prioridad: `AuthToken` (componente) -> `PORCE_UNREAL_TWIN_TOKEN` -> `PORCE_OBSTACLE_TOKEN`

Georreferenciacion (componente):

- `HomeLatDeg`, `HomeLonDeg`
- ENU->Local: `EastFromLocalX`, `EastFromLocalY`, `NorthFromLocalX`, `NorthFromLocalY`
- `CmToMScale`
- `OriginActor`

## Peso YOLO canonico

Peso unico del repo:

- `yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`

Default:

- `PORCE_YOLO_MODEL=%PROJECT_ROOT%\yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`

## Scripts retirados del runtime

No forman parte del flujo principal:

- `tools\check_status.py`
- `tools\validate_latest_run.bat`
- `tools\validate_zero_trust_run.py`

Documentacion historica: `docs/archive/`.
