# Figura 1 del paper - especificacion y trazabilidad Unreal/PORCE

Fecha: 2026-06-16

Este documento traduce las instrucciones recibidas para la Figura 1 en una especificacion operativa. No cierra decisiones que no estan explicitadas.

## Fuente textual

La especificacion esta insertada como comentario en:

- `paper/Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion/IEEE/TII-Articles-LaTeX-template/Main_formato_ieee.tex`, lineas 434-447.

La figura pedida es una composicion de seis paneles:

- Primera fila: `1A`, `1B`, `1C`.
- Segunda fila: `1D`, `1E`, `1F`.
- `1A` y `1D` son representaciones graficas.
- `1B`/`1E` son pareja del mismo estado: arriba Unreal, abajo grafica.
- `1C`/`1F` son pareja del estado de evasion: arriba Unreal, abajo grafica.

## Total de figuras y paneles a generar

El LaTeX actual contiene 8 entornos `figure`, pero la nueva decision editorial cambia esa estructura:

- `System Workflow`: figura existente del paper, no forma parte de las capturas Unreal nuevas.
- `Simulation Environment Diagram`: figura existente del paper, no forma parte de las capturas Unreal nuevas.
- Figuras actuales de estados de mision: deben reorganizarse en una unica Figura 1 multipanel.

Total confirmado para las nuevas figuras de resultados:

- `Figura 1`: caso estatico con torre, 6 paneles (`1A`-`1F`).
- `Figura 2`: caso de obstaculo en movimiento, probablemente 3 paneles, pendiente de cerrar si se numera como `2A`-`2C`.

Total operativo confirmado:

- 2 figuras compuestas nuevas para LaTeX: Figura 1 y Figura 2.
- 6 paneles confirmados para Figura 1.
- 3 paneles propuestos para Figura 2, todavia pendientes de confirmacion final.
- 9 paneles nuevos en total si Figura 2 queda con 3 paneles.

## Relacion con el paper actual

La fuente Overleaf actual aun mantiene figuras separadas despues del comentario:

- `Instante_inicial_del_recorrido.png`: estado nominal.
- `Obstaculo_detectado_pero_fuera_seguridad.png`: deteccion sin accion.
- `instante_durante_evasion.png`: evasion.
- `instante_durante_evasion_zoom.png`: evasion con zoom.
- `transcurso_de_mision_(nuevo_obs_detectado).png`: rejoin y nueva deteccion.
- `ruta_completada_ultimo_obs.png`: resumen/final.

Por tanto, la nueva Figura 1 parece compactar esas etapas en una unica figura multi-panel, pero esto debe confirmarse antes de editar LaTeX.

## Trazabilidad tecnica

### Mision nominal y waypoints

- Fuente de waypoints: `pipeline/ejea_default.waypoints`.
- Parametro de carga: `pipeline/constants.py`, `WAYPOINTS_FILE = "ejea_default.waypoints"`.
- Estado del controlador: `pipeline/flight_controller.py`, `state['waypoints']`, `state['current_wp_idx']`.
- API para graficas en vivo: `pipeline/flight_controller.py`, `/api/ui/data`, que entrega `waypoints`, `telemetry`, `obstacles`, `evasion` y `params`.

### Deteccion sin accion

En codigo, el estado existe cuando:

- Hay obstaculos activos publicados (`obs_fresh == True`).
- Existe obstaculo mas cercano (`nearest_eval is not None`).
- La distancia al obstaculo es mayor o igual a la distancia de reaccion evaluada.
- `decision_reason = "distance_above_reaction"`.
- `state['evasion_path']` esta vacio y `state['evasion_active']` es falso.

Referencia de codigo:

- `pipeline/flight_controller.py`, funcion `nearest_obstacle_info`.
- `pipeline/flight_controller.py`, funcion `adaptive_reaction_distance_m`.
- `pipeline/flight_controller.py`, bloque PORCE del `control_loop`, especialmente la rama `distance_above_reaction`.

### Evasion activa

En codigo, el estado existe cuando:

- La distancia al obstaculo cae por debajo de `reaction_distance_eval_m`.
- `planner_obstacle_subset()` selecciona los obstaculos relevantes y les asigna `safety_m`.
- `PorcePlanner.plan_route()` genera una ruta A*.
- Se actualiza `state['evasion_path']`, `state['evasion_grid_origin']`, `state['path_index'] = 0`, `state['evasion_active'] = True`.
- El evento auditable principal es `evasion_route_generated`.

Referencias de codigo:

- `pipeline/flight_controller.py`, `planner_obstacle_subset()`.
- `pipeline/flight_controller.py`, bloque `trigger_plan_route` / `route_generated`.
- `pipeline/porce_manager.py`, `PorcePlanner.plan_route()`.

### Grid A*

El grid real del planificador esta en:

- `pipeline/constants.py`: `GRID_CELL_SIZE_M = 6.0`, `PLANNER_GRID_RADIUS_CELLS`, `PLANNER_SAFETY_DISTANCE_M`.
- `pipeline/porce_manager.py`: conversion lat/lon a metros, cuantizacion a celdas, inflado de obstaculos, vecinos y reconstruccion de ruta.

La visualizacion grafica ya existe parcialmente en:

- `pipeline/viz_recorder.py`.

Ese script consume `/api/ui/data` y dibuja:

- mision global;
- obstaculos;
- historial de vuelo;
- dron;
- ruta de evasion;
- grid cuando `evasion.active == true` y existe `evasion.grid_origin`.

Importante: `viz_recorder.py` dibuja el grid en la grafica, no en Unreal.

### Unreal

El codigo Unreal localizado que se relaciona con el obstaculo humano/dinamico es:

- `Unreal/Source/AirTraffic/Public/PelotonSplineActor.h`
- `Unreal/Source/AirTraffic/Private/PelotonSplineActor.cpp`

Ese actor modela un peloton sobre spline, con riders, ghosts y heatmap. Es buen candidato para el obstaculo tipo `biker`/persona no involucrada, pero no he visto todavia un actor C++ especifico que dibuje en Unreal el grid A* o la ruta PORCE como overlay in-engine.

## Especificacion panel por panel

### 1A - Grafica de navegacion nominal

Debe mostrar:

- UAS siguiendo `Nominal Navigation`.
- Waypoints predefinidos.
- Ruta nominal sin cambios.
- Sin evasion activa.
- Sin ruta alternativa.

Datos necesarios:

- `pipeline/ejea_default.waypoints`.
- telemetria de un instante inicial antes de deteccion.

Estado tecnico asociado:

- `evasion.active = false`.
- `obstacles` vacio o no relevante.
- `decision_reason` compatible con navegacion normal.

Pendiente:

- Confirmar si `1A` debe ser una grafica tipo `viz_recorder.py` o una grafica mas limpia hecha especificamente para el paper.

### 1B - Unreal: deteccion sin accion

Debe mostrar:

- Escena Unreal.
- UAS en vuelo.
- Obstaculo detectado/visible.
- Todavia sin maniobra evasiva.
- Sin grid ni ruta A* activa.

Estado tecnico asociado:

- `obs_count > 0`.
- `evasion.active = false`.
- `decision_reason = "distance_above_reaction"`.

Pendiente:

- Confirmar como debe verse la "deteccion" en Unreal: solo obstaculo visible, bounding box YOLO, marcador, circulo de seguridad, o HUD.

### 1E - Grafica: deteccion sin accion

Debe mostrar el mismo instante que `1B`, pero como grafica:

- mission/global path;
- UAS;
- obstaculo detectado;
- distancia/radio relevante;
- sin ruta naranja de evasion;
- sin grid A* activo.

Base tecnica:

- `pipeline/viz_recorder.py` ya representa este estado como `OBSTACLE DETECTED` cuando hay obstaculos y `evasion.active` es falso.

Pendiente:

- Aclarar si la grafica debe mostrar la distancia de reaccion, el radio de seguridad `R_s`, o ambos. El texto recibido dice "distancia de seguridad como para ejecutar la accion", pero el codigo ejecuta la accion por distancia de reaccion, no por el radio duro de seguridad.

### 1C - Unreal: evasion activa con zoom

Debe mostrar:

- Escena Unreal.
- UAS ya ejecutando maniobra evasiva.
- Vista con zoom al esquive.
- Grid visible.
- Ruta alternativa/maniobra PORCE visible.

Estado tecnico asociado:

- `evasion.active = true`.
- `evasion.path` no vacio.
- `evasion.grid_origin` no nulo.
- evento `evasion_route_generated` ya producido.

Pendiente critico:

- Confirmar como debe verse la captura Unreal: escena limpia, bounding box YOLO, marcador, circulo de seguridad, HUD o etiqueta de estado.

### 1F - Grafica: evasion activa con zoom

Debe mostrar el mismo instante que `1C`, pero como grafica:

- grid A*;
- celdas/ruta de evasion;
- UAS;
- obstaculo;
- zoom local del esquive.

Base tecnica:

- `pipeline/viz_recorder.py` ya dibuja grid y ruta de evasion cuando `evasion.active` y `evasion.grid_origin` existen.
- `pipeline/porce_manager.py` define la geometria real del grid.

Pendiente:

- Confirmar si el zoom debe centrarse en `evasion.grid_origin`, en el obstaculo, o en el UAS.
- Confirmar si deben verse celdas ocupadas por inflado de obstaculo, porque `viz_recorder.py` actualmente muestra grid y ruta, pero no reconstruye explicitamente todas las celdas ocupadas del planificador.

### 1D - Grafica resumen de ruta completa

Debe mostrar:

- ruta nominal original;
- ruta realmente seguida;
- todas las evasiones realizadas;
- resumen del comportamiento completo.

Datos necesarios:

- `trajectory.csv` de un run completo.
- eventos `evasion_route_generated`, `evasion_progress`, `evasion_completed`.
- waypoints originales.

Estado tecnico asociado:

- logs de `ZeroTrustAudit`: `trajectory.csv` y `events.jsonl`.
- tambien puede usarse `/api/ui/data` durante ejecucion, pero para resumen final conviene trabajar desde logs cerrados.

Confirmado:

- `1D` resume solo el caso estatico de la torre dentro de la Figura 1.
- No debe mezclar obstaculos en movimiento.
- El caso de ciclista/peloton queda reservado para la Figura 2.

Pendiente:

- Confirmar si debe incluir landing/final de mision.
- Confirmar si se deben colorear evasiones individualmente o solo mostrar nominal vs flown path.

## Informacion que si tenemos

- Sabemos donde esta la especificacion en Overleaf.
- Sabemos que la mision nominal sale de `pipeline/ejea_default.waypoints`.
- Sabemos como el codigo diferencia deteccion sin accion de evasion activa.
- Sabemos donde se genera la ruta A*.
- Sabemos que `/api/ui/data` expone los datos necesarios para graficas en vivo.
- Sabemos que `viz_recorder.py` ya puede producir una base grafica para `1E` y `1F`.
- Sabemos que `PelotonSplineActor` es el candidato mas directo para el obstaculo tipo biker/persona.

## Informacion que falta o no conviene inferir

1. Si la deteccion Unreal de `1B` debe mostrar bounding boxes YOLO/HUD o una escena limpia con el obstaculo visible.
2. Que run concreto usaremos para `1D` y si debe contener todas las evasiones de una mision completa nueva.
3. Si la segunda figura del obstaculo en movimiento debe numerarse como Figura 2A-2C.
4. Si el obstaculo movil debe ser un ciclista individual o un peloton.

## Preguntas para cerrar antes de producir figuras

Nota terminologica: `R_s` si aparece en el paper actual como hard safety radius, en la formulacion donde cada obstaculo se infla por un radio duro de seguridad. En el texto vigente se define como `R_s = 12 m`. La version `R_s(clase)` esta documentada en los anexos EASA preservados, pero todavia no esta integrada en el paper actual.

Preguntas reformuladas con terminos del paper:

Respuestas ya cerradas:

1. Figura 1 usa obstaculo estatico: torre.
2. Figura 2 queda para obstaculo en movimiento: ciclista o peloton.
3. `1B` y `1E` muestran el obstaculo dentro del `Reaction Range`, pero fuera de la `Base reaction distance`.
4. El `81 x 81 occupancy grid` basta en la representacion grafica `1F`; no hace falta dentro de Unreal.
5. `1D` es `Final Stage. Route Summary` solo del caso estatico de la torre.

Preguntas que quedan:

1. Cuando el paper habla de preservar la separacion, quieres que la grafica marque visualmente el `hard safety radius R_s = 12 m`, la `Base reaction distance = 45 m`, o ambas cosas?
2. Para la Figura 2, confirmamos peloton en vez de ciclista individual?

Decision cerrada posteriormente:

- En las capturas Unreal (`1B` y `1C`) deben aparecer bounding boxes/HUD de deteccion.
