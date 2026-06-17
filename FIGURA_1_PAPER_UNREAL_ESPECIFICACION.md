# Figura 1 del paper - especificacion y trazabilidad Unreal/PORCE

Fecha: 2026-06-16

Este documento traduce las instrucciones recibidas para la Figura 1 en una especificacion operativa. No cierra decisiones que no estan explicitadas.

## Fuente textual

La especificacion esta insertada como comentario en:

- `paper/Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion/IEEE/TII-Articles-LaTeX-template/Main_formato_ieee.tex`, lineas 434-447.

La figura pedida es una composicion de seis paneles:

- Primera fila: `1A`, `1B`, `1C`.
- Segunda fila: `1D`, `1E`, `1F`.
- Los seis paneles `1A`-`1F` deben ser representaciones cenitales/top-down.
- Los seis paneles deben llevar superpuesto el grid real del planificador: `81 x 81` celdas, `6 m` por celda, radio `40` celdas.
- La deteccion/obstaculo de la Figura 1 debe ser unica y de tipo torre. No deben aparecer ciclistas, peloton, vacas ni multiples torres detectadas.
- Los seis paneles deben tener el mismo aspect ratio, los mismos valores en los ejes y las mismas etiquetas de ejes. El encuadre/camara no se mueve entre paneles: la Figura 1 se lee como una secuencia temporal sobre un mismo mapa fijo.
- Para las figuras generadas actuales, el encuadre fijo activo queda documentado como eje X `[-40, 160]` m y eje Y `[-165, 35]` m, con etiquetas `East (m)` y `North (m)`. Es un encuadre cuadrado `1:1` de 200 m x 200 m, centrado en el tramo WP1->WP2 para maximizar claridad, con mas aire por encima de WP1 y menos espacio muerto bajo WP2.
- La version amplia anterior y la version cercana anterior quedan preservadas como contexto, pero no son la version activa para componer la Figura 1.
- Los paneles `1B` y `1C` deben ser continuidad del mismo encuentro. La version corregida usa el run `pipeline/logs/paper_wp1_wp2_tower/paper_wp1_wp2_tower_p0.56_l+8.0_20260617_120539`; ambos corresponden a la misma torre `vision:101`.
- La lectura activa queda fijada como secuencia temporal `1A -> 1B -> 1C -> 1D -> 1E -> 1F`.
- La instruccion original agrupaba `1B/1E` como deteccion y `1C/1F` como evasion, pero eso solo funcionaba como matriz por columnas. Al exigir seis paneles cenitales con mismo encuadre, la figura se entiende mejor como secuencia; por tanto `1B` es deteccion sin accion cerca del umbral, `1C` la ultima deteccion sin accion con radios, `1D` el inicio de evasion A*, `1E` la evasion en curso y `1F` el resumen final.

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

## Run activo para generar Figura 1

- Run: `pipeline/logs/paper_wp1_wp2_tower/paper_wp1_wp2_tower_p0.56_l+8.0_20260617_120539`.
- Tipo de ejecucion: `pipeline/flight_controller.py` real con `PORCE_MOCK_MAVLINK=1`, obstaculo estatico inyectado por `/api/obstacles` con `source=vision`, `type=tower`.
- No es un mockup manual de la logica: los eventos `decision_snapshot`, `evasion_route_generated`, `evasion_completed` y la trayectoria salen del Brain real.
- No es todavia captura real Unreal/YOLO: la deteccion se inyecta de forma determinista para aislar el comportamiento PORCE y generar la figura reproducible.
- Torre: `lat=42.22904865463611`, `lon=-1.234404232738992`, progreso `0.56` en WP1->WP2, lateral `+8 m`.
- Validacion: `accepted_types=["tower"]`, `clean_detection_count=9`, `valid_plan_count=1`, `valid_completion_count=1`, `failure_count=0`.
- Evasion activa: comienza en progreso `0.2085` del tramo WP1->WP2 y termina en `0.9412`, antes de llegar a WP2.
- Evento de planificacion: `planner_obs_count=1`, por tanto la torre `vision:101` si fue incluida por el planner.
- Panel `1B`: deteccion sin accion a `67.1 m`.
- Panel `1C`: ultima deteccion sin accion a `63.1 m`, justo antes de generar evasion al cruzar `reaction_distance_eval_m = 61 m`.
- La torre se muestra en `1B` porque ya existe como obstaculo activo detectado (`obs_fresh=True`, `obs_count=1`). No estamos dibujando el rango fisico/sensorial de deteccion de YOLO; los circulos de `1C` son distancias de reaccion/control, no el alcance de la camara.

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

### 1B - Cenital: deteccion sin accion

Debe mostrar:

- Vista cenital/top-down.
- Grid real del planificador superpuesto.
- UAS en vuelo.
- Deteccion unica de torre.
- Todavia sin maniobra evasiva.
- Con grid visible, pero sin ruta A* activa.

Estado tecnico asociado:

- `obs_count > 0`.
- `evasion.active = false`.
- `decision_reason = "distance_above_reaction"`.

Decision cerrada:

- No se usa captura oblicua/camara Unreal para este panel.
- No se dibujan ciclistas, peloton, vacas ni multiples torres.

### 1C - Grafica: deteccion sin accion

Debe mostrar un instante posterior a `1B`, todavia sin accion, pero mas cerca del umbral de planificacion:

- mission/global path;
- UAS;
- obstaculo detectado;
- distancia/radio relevante;
- sin ruta naranja de evasion;
- sin grid A* activo.

Base tecnica:

- `pipeline/viz_recorder.py` ya representa este estado como `OBSTACLE DETECTED` cuando hay obstaculos y `evasion.active` es falso.

Decision activa:

- Se muestran `Base reaction distance` y `Reaction distance`; el radio duro `R_s` sigue representado alrededor de la torre.

### 1D - Cenital: evasion activa

Debe mostrar:

- Vista cenital/top-down.
- UAS ya ejecutando maniobra evasiva.
- Grid real del planificador superpuesto.
- Ruta alternativa/maniobra PORCE visible.
- Deteccion unica de torre.

Estado tecnico asociado:

- `evasion.active = true`.
- `evasion.path` no vacio.
- `evasion.grid_origin` no nulo.
- evento `evasion_route_generated` ya producido.

Decision cerrada:

- No se usa captura oblicua/camara Unreal para este panel.
- No se dibujan ciclistas, peloton, vacas ni multiples torres.
- Mantiene el mismo encuadre que el resto de paneles; el zoom local queda resuelto por el detalle de `1E`, no por mover la camara.

### 1E - Grafica: evasion activa con grid

Debe mostrar el mismo instante que `1D`, enfatizando:

- grid A*;
- celdas/ruta de evasion;
- UAS;
- obstaculo;
- ruta local del esquive.

Base tecnica:

- `pipeline/viz_recorder.py` ya dibuja grid y ruta de evasion cuando `evasion.active` y `evasion.grid_origin` existen.
- `pipeline/porce_manager.py` define la geometria real del grid.

Decision activa:

- Como todos los paneles deben compartir encuadre y ejes, no se hace zoom moviendo la camara. Se mantiene el grid real y se resalta la ruta A*.

### 1F - Grafica resumen de ruta completa

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
3. `1B` y `1C` muestran el obstaculo ya detectado, pero todavia fuera de `reaction_distance_eval_m`, por eso no hay accion. Si `Reaction Range` se usa en el paper como rango sensorial/de deteccion, la torre esta dentro porque `obs_fresh=True`; si se usa como `reaction_distance_eval_m`, entonces debe estar fuera para que el estado "No Safety Action" sea correcto.
4. El `81 x 81 occupancy grid` basta en la representacion grafica `1F`; no hace falta dentro de Unreal.
5. El resumen final del caso estatico de la torre queda como `1F` para que la lectura `1A -> 1F` sea temporal. La etiqueta original `1D` solo se conserva como antecedente historico de la instruccion recibida.

Preguntas que quedan:

1. Cuando el paper habla de preservar la separacion, quieres que la grafica marque visualmente el `hard safety radius R_s = 12 m`, la `Base reaction distance = 45 m`, o ambas cosas?
2. Para la Figura 2, confirmamos peloton en vez de ciclista individual?

Decision cerrada posteriormente:

- Los seis paneles de la Figura 1 deben ser cenitales/top-down.
- El grid real `81 x 81` debe aparecer superpuesto en los seis paneles.
- La deteccion debe ser unica y de torre.
