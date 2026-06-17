# OVERNIGHT STATUS — Deep-AeroTwin paper evidence
Last heartbeat: 2026-06-13 00:00 (SESIÓN PRINCIPAL — TODO TERMINADO, incluidos opcionales HUD y D4)
Owner: main-session

## CIERRE 00:00 — TODO COMPLETADO
1. HUD resuelto: las etiquetas eran anotación in-place de VISION pre-archivo (no del juego). Fix: copia prístina (vision_system.py). 
2. Run definitivo 20260612_233504: COMPLETED, 464 rutas, 92 bike, frames PRÍSTINOS.
3. CASO FINAL (Fig4/Tab4): ts=1781300494.3, WP6, trigger 35.11 m, 16 planner_obs_ids, 15 bikers (conf hasta 0.80), evasión 19.48 s, desvío 3.42 m, clearance concurrente mín 34.27 m (sobre el failsafe 22 m todo el tiempo). Frame 5728 prístino con el peloton de 16 visible.
4. PDF FINAL: 23 págs, 0 errores, verificado visualmente (pág 20 = Fig4 limpia).
5. D4 documentado: docs/d4_twin_demo_20260612.md (spawn/update/despawn verificado API + LogPorceTelemetry in-engine).
6. Commits locales: 0006664, 31ae3de, 43cbd23 (+ commit final pendiente de docs/D4).
WATCHDOG: no queda trabajo. Solo verificar ausencia de zombis y salir. NO lanzar runs.

## ESTADO FINAL 23:05
Todo lo no-opcional está [x]. PDF final: paper/.../main.pdf (23 págs, recompilado 23:0x).
Commits locales: 0006664 + 31ae3de. Juego y pipeline parados (editor UE puede seguir abierto; si molesta, ciérrese).
Watchdog: en cada ciclo, si heartbeat >20 min, basta verificar que no hay procesos zombis y salir.
Los ítems opcionales (HUD limpio, D4) solo si se hacen con MUCHO cuidado de no romper lo entregado: el paper actual es válido y está comiteado.

## HITO 22:55 — PAPER COMPLETO Y COMPILADO
- main.pdf recompilado OK (23 páginas, 0 errores, 2 pasadas pdflatex).
- Caso de estudio: run 20260612_214341, trigger WP5 ts=1781293720.29 (peloton cruzando), 16 planner_obs_ids, 15 bikers publicados, clearance concurrente mín 31.61 m (>22 m failsafe SIEMPRE), frame real 4258 archivado en Fig 4.
- Métrica nueva: clearance time-synchronized contra tracks concurrentes (el proxy estático daba 1.16 m artefactual con obstáculos móviles) — implementada en generate_paper_assets.py y main.tex.
- main.tex actualizado: abstract, fuentes de evidencia, métricas, Tab 3 media±σ (11/11+10/10×3 completadas, evasión solo on+det), sección caso completa, Tab 4, Limitations, Conclusion.
- Compilar: tmp/compile_paper.cmd (cmd /c, MiKTeX). Figuras: tmp/run_genassets.cmd. Pandas instalado en venv.

## Contexto (leer primero)
Auditoría: docs/auditoria_unreal_demos_paper_20260612.md. Plan: D3→precheck→D1→D2→recompilar.
- HECHO: D3 (planner_obs_ids en flight_controller.py, verificado en runs reales).
- HECHO: D2 campaña 40/40 (pipeline/logs/e2e/campaign_20260612_174114.json; evasión solo on+det 10/10; +2.1s/+8.3m).
- HECHO: pre-check YOLO (peloton rojo conf 0.26 → modo ChildActor ciclista conf 0.62-0.88). Mapa de auditoría: /Game/Ejea_AuditD1 (Ejea original INTACTO).
- HECHO: captura por ventana PrintWindow+PW_RENDERFULLCONTENT en vision_system.py (PORCE_CAPTURE_WINDOW_METHOD=printwindow; fix GDI leak SelectObject-before-Delete). Robusta a oclusión.
- HECHO: runs D1 válidos con SITL real: 20260612_213227 (vision murió a 117s pre-fix GDI) y 20260612_214341 (COMPLETO, 313 rutas, 46 triggers bike, 2933 frames, vision viva todo el vuelo).
- Bugs encontrados/arreglados: run_sitl.sh parsea tcp:127.0.0.1:5760 como 5887 (usar SITL_SERIAL0=tcp:5790); svchost local ocupa 5760; DPI mismatch en capturas; GDI leak.
- PENDIENTE conocido: el juego dibuja etiquetas verdes HUD (BP_AirplaneMarker probablemente) sobre la vista; los logs NO se ven afectados; para Fig 4 es aceptable (caption: HUD del viewer) pero ideal sería frame sin HUD.

## Infra
- Orquestador D1: tmp/d1_orchestrator.py (SITL WSL puerto 5790 + brain + vision printwindow + viz; resumen en tmp/d1_summary.json).
- Juego: UnrealEditor.exe AirTraffic.uproject /Game/Ejea_AuditD1 -game -windowed -ResX=640 -ResY=640 (título ventana "AirTraffic (64-bit"). Si no corre, relanzar.
- Editor UE abierto con bridge MCP en http://127.0.0.1:3000/mcp (cliente: tmp/ue_mcp.py; ejecutar python in-editor: --exec-python file.py).
- Campaña E2E: tools/e2e_campaign.py.
- PowerShell del MCP tiene PATH/PATHEXT rotos: usar rutas absolutas (C:\Windows\System32\wsl.exe) y PATHEXT=.COM;.EXE;.BAT;.CMD en hijos.
- El sandbox bash (mnt) tiene lag de sincronización: leer ficheros recién escritos via windows-mcp Shell o Read tool.

## CHECKLIST (estado: [ ] pendiente, [~] en curso, [x] hecho)
- [x] D3 patch + verificación
- [x] D2 campaña estadística
- [x] Pre-check YOLO peloton
- [x] Captura robusta por ventana (PrintWindow)
- [x] Run D1 definitivo (20260612_214341: COMPLETED, 46 triggers bike, caso WP5 con 16 obs)
- [x] Elegir caso y actualizar CASE_RUN/CASE_ROUTE_TS
- [x] generate_paper_assets.py ejecutado (figuras + paper_metrics.json + e2e_campaign_stats.csv)
- [x] Figuras revisadas visualmente (Figs 3,4,5,6,7,8 OK)
- [x] main.tex actualizado (Tab 3 media±σ, caso, abstract, limitations, conclusion)
- [x] main.pdf compilado (23 págs, 0 errores) y verificado página a página
- [x] Verificación: clean_viewer_frame_archived=true; PDF posterior a figuras
- [x] Escena: peloton 650 cm/s + 16 riders, guardado en Ejea_AuditD1; run verificación 20260612_224316 COMPLETED (94 triggers bike por TODO el corredor wp3-10, 8 evasiones completadas, 4418 frames) → frase de robustez añadida al paper. El caso de Fig4/Tab4 sigue siendo el del run 214341 (riders más visibles).
- [x] D5 latencias: data/latency_metrics.json (visión 14.6 fps mediana; publish→replan 0.62 s mediana; cadencia replan 1.01 s) + párrafo en main.tex
- [x] Commit git seguridad: 0006664 (local, sin push)
- [x] PDF FINAL recompilado tras D5+robustez: 23 págs, 0 errores
- [ ] (Opcional) localizar y desactivar el HUD verde del viewer para frames 100% limpios; si se logra: repetir run, elegir caso nuevo, regenerar figuras, recompilar. NO romper nada de lo ya entregado; el paper actual ya es válido.
- [ ] (Opcional D4) demo twin spawn/update/despawn (REAL_TWIN o launch_spawner) — el componente PorceTelemetry está DESACTIVADO en Ejea_AuditD1; para D4 usar el mapa Ejea ORIGINAL en el juego o reactivar el componente en una COPIA nueva
- [ ] (Opcional) segundo commit con main.tex/latency si hay cambios pendientes tras la última recompilación

NOTA: si todo lo de arriba no-opcional está [x], el watchdog NO debe lanzar más runs; solo verificar que no quedan procesos zombis (pythons del pipeline, arducopter) y salir.

## Reglas para la sesión watchdog
1. Lee este fichero. Si "Last heartbeat" tiene <20 min, NO hagas nada (otra sesión trabaja); sal.
2. Si >20 min: toma el relevo. Actualiza Owner y heartbeat. Continúa el primer ítem [ ]/[~].
3. Verifica salud: juego corriendo (proceso UnrealEditor con MainWindowTitle '*64-bit*'), sin runs zombis (python d1_orchestrator/flight_controller/vision), WSL ok. Limpia con: Stop-Process de pythons del pipeline + wsl pkill arducopter.
4. Tras cada avance, actualiza heartbeat y checklist aquí.
5. No toques Ejea.umap original. Trabaja solo con Ejea_AuditD1.
6. Runs D1: Start-Process venv python tmp/d1_orchestrator.py; esperar ~8-10 min; validar tmp/d1_summary.json (ok+mission_completed) y frames con bikers cerca de triggers bike.

## AVISO watchdog 2026-06-13 00:22
Heartbeat caducado (00:00, ~22 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (pgrep solo se auto-detectó a sí mismo).
No se lanzó ningún run, no se tocó git ni el juego. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 00:37
Heartbeat caducado (00:00, ~37 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (pgrep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 00:52
Heartbeat caducado (00:00, ~52 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 01:19
Heartbeat caducado (00:00, ~79 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (pgrep solo se auto-detectó a sí mismo).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 01:37
Heartbeat caducado (00:00, ~97 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 01:52
Heartbeat caducado (00:00, ~112 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 02:03
Heartbeat caducado (00:00, ~123 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 02:22
Heartbeat caducado (00:00, ~142 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 02:37
Heartbeat caducado (00:00, ~157 min). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 03:37
Heartbeat caducado (00:00, ~3.6 h). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 03:52
Heartbeat caducado (00:00, ~3.9 h). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO.
- arducopter en WSL: NINGUNO (ps aux | grep sin resultados).
- UnrealEditor PID 36904 ('AirTraffic - Unreal Editor', el editor, no el juego): se deja abierto según ESTADO FINAL 23:05.
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 2026-06-13 09:08
Heartbeat caducado (00:00, ~9 h). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO (Get-CimInstance Win32_Process limpio).
- arducopter en WSL: 0 (cmd /c wsl bash -lc 'ps aux|grep arducopter|grep -v grep|wc -l' → 0; nota: el call operator de PowerShell con pipe falla por PATHEXT roto, hay que usar cmd /c + redirección a fichero y leer con Read tool).
- UnrealEditor: NINGÚN proceso corriendo (el editor PID 36904 de ESTADO FINAL 23:05 ya no existe; no se relanza porque no hacen falta runs).
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.

## AVISO watchdog 23:07
Antes de ver el heartbeat 23:12, el watchdog mató 2 pythons flight_controller.py (PIDs 42932 venv y 236260 system) como zombis, según el STATUS de 23:05 que decía "pipeline parado". Si la sesión principal los acababa de lanzar, relanzarlos. El watchdog NO ha tocado nada más (ni juego, ni puerto 8080, ni git). Watchdog en standby mientras heartbeat <20 min.

## AVISO watchdog 2026-06-13 09:19
Heartbeat caducado (00:00, ~9.3 h). Checklist no-opcional todo [x] → según CIERRE 00:00, solo verificación de zombis:
- Pythons del pipeline (d1_orchestrator|flight_controller|vision_system|viz_recorder): NINGUNO (Get-CimInstance Win32_Process limpio).
- UnrealEditor: NINGÚN proceso corriendo (no se relanza; no hacen falta runs).
- arducopter en WSL: NINGUNO (cmd.exe ruta absoluta + wsl pgrep -af arducopter → solo el auto-match del propio sh PID 487).
- Nota de entorno: el `cmd` del PowerShell de windows-mcp NO está en PATH; hay que invocar 'C:\Windows\System32\cmd.exe' por ruta absoluta para redirigir salida de wsl a fichero (el call operator `&` de PowerShell sobre wsl.exe no captura stdout).
No se lanzó ningún run, no se tocó git, el juego ni los opcionales. Watchdog sale limpio.
