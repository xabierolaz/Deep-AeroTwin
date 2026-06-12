# Auditoría Unreal ↔ Paper PORCE — 2026-06-12

Alcance: `Unreal/` (AirTraffic, UE 5.7), `pipeline/`, `paper/Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion/`. Todo lo marcado como [V] está verificado leyendo código/logs/figuras; [I] es inferencia razonable.

## 1. Implementado

### Unreal (AirTraffic.uproject, UE 5.7)
- [V] Módulo C++ `AirTraffic` con `APelotonSplineActor`: peloton paramétrico sobre spline (RiderCount=14, formación por filas, velocidad, loop), ghosts forward/backward con heatmap de color y opacidad, 3 modos de render (StaticMesh/ISM/ChildActor). Compilado: `Binaries/Win64/UnrealEditor-AirTraffic.dll` existe.
- [V] `Content/Peloton/` (BP_PelotonSpline, M_PelotonRider, M_PelotonGhost) instanciado dentro de `Ejea.umap` (actor `Peloton_Ciclistas_EditableSpline`, confirmado por strings del .umap).
- [V] Plugin `PorceTelemetry` (PORCE Twin V2): poll a `GET /api/ui/data` (5 Hz), spawn/update/despawn por `entity_id`, clases mapeadas a `bp_biker`/`bp_cow`/`bp_tower`, smoothing tentative/confirmed, conversión NED/latlon→world, altura base Cesium.
- [V] `McpAutomationBridge` (ChiR24, MIT) instalado y operativo — los scripts `tmp/apply_peloton_*.py` se ejecutaron vía MCP contra el editor (sesiones en `tmp/ue57_postpatch_mcp_editor*`).
- [V] Mapa Ejea georreferenciado (CesiumForUnreal), VaRest, assets ciclista/cow/tower/airplane, RT_DroneCapture.

### Pipeline
- [V] Workflow SIMULATION completo (SITL WSL + Brain + Vision + Viz + log server). Vision captura la ventana PIE de Unreal por título y corre YOLO en el loop.
- [V] Workflow REAL_TWIN implementado (launcher pasivo, sin SITL).
- [V] Harness E2E con 17 runs (2026-02-17): on/off × det/no-det = 6/3/4/4 runs por escenario.
- [V] ~80 runs zero-trust; caso de estudio `20260220_092802` con 4028 frames de visión archivados.

### Paper
- [V] `main.tex` completo: 7 figuras + 3 tablas + pseudocódigo. Todas las figuras existen en `figures/` y son regenerables con `scripts/generate_paper_assets.py` desde logs del repo (6 regeneradas hoy 11:21).
- [V] Tab. SOTA y Tab. config son estáticas (no requieren demo). Figs. 1–2 son draw.io (estáticas).

## 2. Lo que falta (gaps respecto a lo que el paper promete o necesita)

1. **Captura real de Unreal en Fig. 4.** La figura actual imprime literalmente "Reconstructed from logged YOLO boxes; no Unreal window screenshot" y `paper_metrics.json` registra `clean_viewer_frame_archived: false`. La versión anterior con frames reales (tmp/pdfs/real_yolo_review) se descartó por calidad. **Este es el hueco que el peloton UE5.7 construido en junio debe llenar** [I: propósito inferido por cronología — peloton + ghosts creados jun-11/12, caso del paper es `biker`].
2. **Ningún run posterior al 2026-05-14.** Todo el trabajo de junio en Unreal (peloton, ghosts, heatmap) aún no ha producido ni un log ni una captura: la demo no se ha ejecutado.
3. **Sin estadística multi-run.** Limitations lo declara: Tab. 3 usa 1 run por escenario aunque hay 3–6 disponibles; no hay media±σ ni más semillas.
4. **`evasion_route_generated` no serializa IDs de obstáculos** (verificado en `flight_controller.py`: solo `planner_obs_count`). Todo el análisis de clearance es proxy — limitación declarada y aún cierta en el código.
5. **PDF desfasado:** figuras regeneradas 12-jun 11:21 > `main.pdf` compilado 11-jun 12:52. Recompilar.
6. **Sin medidas de runtime/latencia** en hardware representativo (future work declarado).
7. **REAL_TWIN sin evidencia auditada** para el paper (cadena spawn/update/despawn no demostrada en ningún run archivado).
8. Repo sin commit desde el 4-abr: `paper/`, `docs/` y todo el trabajo mayo-junio están sin versionar (riesgo de pérdida).

## 3. Demostraciones a ejecutar → asset del paper que generan

| # | Demo | Genera | Prioridad |
|---|------|--------|-----------|
| D1 | **Run SIMULATION en Ejea con el peloton cruzando el corredor** (launch.bat, vision sobre PIE, PORCE on). Archivar: frame PIE limpio + frame con boxes YOLO en el instante de trigger | Fig. 4 con captura real (elimina el disclaimer), `clean_viewer_frame_archived=true`; nuevos `events.jsonl`/`trajectory.csv` → regenerar Figs. 5–8 y Tab. 4 con el caso peloton; GIF para suplementario (`tmp/make_latest_run_viz_gif.bat`) | **Alta — es lo que el paper espera** |
| D2 | **Campaña estadística E2E**: ≥10 runs × 4 escenarios con el harness existente | Tab. 3 con media±σ y "mission completed N/N"; banda de variabilidad en Fig. 3. Cierra la limitación "not yet statistical" | Alta |
| D3 | **Patch de auditoría**: añadir `planner_obs_ids` al evento `evasion_route_generated` | Elimina el caveat "proxy" en todos los runs nuevos (D1/D2); simplifica el texto de Limitations | Alta (≈30 min, hacer ANTES de D1/D2) |
| D4 | **Demo twin**: PorceTelemetry spawneando `bp_biker` desde detecciones (launch_spawner.bat o REAL_TWIN pasivo) | Figura nueva opcional de la cadena spawn/update/despawn; respalda la sección de integración y el plan REAL_TWIN de future work | Media |
| D5 | **Medición de latencias** detección→track→replan desde logs zero-trust | Tabla de runtime opcional (responde al future work) | Baja |

### Orden recomendado
D3 (patch) → verificación previa: confirmar que el YOLO actual detecta `biker` sobre el render del peloton UE5.7 (un PIE corto con vision en marcha, sin misión) → D1 → D2 → recompilar `main.tex` → D4/D5 si hay tiempo.

### Riesgos concretos antes de D1
- El modelo YOLO se validó sobre los assets antiguos; los riders del peloton son mesh `ciclista` con material rojo nuevo — hay que confirmar detección y confidence ≥0.65 (umbral de confirmed del twin) antes de lanzar la campaña.
- Los ghosts/heatmap son visualización: si entran en el FOV de la cámara del dron pueden generar falsos positivos o contaminar la captura "limpia". Plantear `bShowForwardLeaderGhosts=false` durante runs de evidencia.
- Trayectoria del spline del peloton debe cruzar el corredor de inspección a tiempo (sincronizar `StartDistance`/`SpeedCmPerSecond` con la misión `ejea_default.waypoints`).

## 4. Estado de cada asset del paper

| Asset | Fuente | Estado |
|---|---|---|
| Fig 1 arquitectura | draw.io | OK, estática |
| Fig 2 method flow | draw.io | OK, estática |
| Tab 1 SOTA | literatura | OK, estática |
| Tab 2 config | constants.py | OK, estática |
| Fig 3 ablación E2E | logs e2e feb-17 | Generada; mejorable con D2 (multi-run) |
| Tab 3 métricas E2E | logs e2e feb-17 | Generada; 1 run/escenario → D2 |
| Fig 4 YOLO overlay | run 20260220_092802 | Generada pero **esquemática, sin captura Unreal** → D1 |
| Fig 5 six-stage | run 20260220_092802 | Generada (matplotlib); D1 da versión con caso peloton |
| Fig 6 detection montage | run 20260220_092802 | Generada |
| Fig 7 case trajectory | run 20260220_092802 | Generada |
| Fig 8 case timeseries | run 20260220_092802 | Generada |
| Tab 4 métricas caso | run 20260220_092802 | Generada; D1+D3 darían caso sin proxy |
| PDF compilado | main.tex | **Desfasado** respecto a figuras de hoy → recompilar |
