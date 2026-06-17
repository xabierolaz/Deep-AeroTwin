# Auditoría PORCE: loop, recorrido, evasión dinámica y paper (Overleaf)

Fecha: 2026-06-13 · Alcance: `pipeline/flight_controller.py`, `pipeline/porce_manager.py`, `pipeline/vision_system.py`, `pipeline/constants.py`, `pipeline/porce_defaults.env`, `pipeline/ejea_default.waypoints` y el zip de Overleaf (`Main_formato_ieee.tex`).

Convención: **[V]** verificado leyendo código/config · **[I]** inferencia razonada · **[?]** no verificado / abierto.

---

## 0. Veredicto rápido

- **¿El loop funciona?** Sí, la máquina de estados es coherente y completa (arm→takeoff→nav→evasión→failsafe→land). Tiene **un agujero**: no hay timeout de evasión activa (posible enganche) y con telemetría stale el loop solo hace `continue` (sin acción de seguridad). **[V]**
- **¿El recorrido funciona?** Sí, para el fichero de misión concreto. Pero el loader **asume** que el waypoint de índice 1 es el takeoff; los comandos QGC (16/22/21) se ignoran salvo ese caso especial. Frágil ante otros ficheros. **[V]**
- **¿El "script de PORCE" (evasión dinámica) funciona?** Funciona como **replanificador reactivo A\* re-sembrado** (sin predicción de trayectoria del obstáculo). **Decisión tomada (2026-06-13): el método es reactivo por diseño y el paper manda — no se añade predicción.** Por tanto el trabajo no es inventar capacidades, sino: (1) que el lazo reactivo esté bien implementado, (2) robusto, y (3) **bien justificado**. El término "moving obstacle avoidance" es defendible para un reactivo *si* el paper declara explícitamente que no predice y aporta la **condición de holgura** (ver `porce_formulacion_matematica.tex`, ec. ★). El hallazgo crítico se traslada de "sobre-promesa" a **"robustez del lazo reactivo"** (latencia de detección vs velocidad de cierre). **[V]**

---

## 1. El loop de control (`control_loop`, líneas 1855–2809)

### Estructura (correcta)
`while True: sleep(0.1)` → snapshot de estado bajo lock → status/audit → gate de telemetría stale → failsafe activo → máquina arm/takeoff (idx==1) → cálculo de bloqueo de waypoint → **bloque PORCE** (decisión + A\*) → ejecución de evasión → navegación estándar → land/disarm. El uso de `state_lock` y de snapshots (`tel`, `obs`) es consistente; el A\* trabaja sobre una foto coherente de obstáculos. **[V]**

La lógica de decisión (líneas 2157–2206) está bien ordenada y es auditable: `failsafe_hold` → `wp_blocked` → `no_obstacles` → `evasion_disabled` → `distance_above_reaction` → trigger. Cada rama emite evento de auditoría. Buen diseño para un contexto safety-critical. **[V]**

### Problemas del loop

1. **[ALTA] Sin timeout de evasión activa → posible enganche (livelock).** El `wp_block` tiene timeout de 6 s (`EVASION_WP_BLOCK_MAX_HOLD_S`), pero **una ruta de evasión activa no tiene duración máxima**. Si el dron no alcanza el siguiente sub-punto (tolerancia 3 m, línea 2611) —p.ej. el obstáculo se metió en la ruta y el replan está bloqueado por distancia/intervalo— se queda navegando sub-puntos indefinidamente mientras la telemetría sea fresca. La escalera de failsafe (líneas 2295–2530) **solo se dispara si el A\* falla**, no si el A\* tiene éxito pero no hay progreso. En SITL con copter casi holonómico es improbable, pero es un hueco real. **[I]**

2. **[MEDIA] Telemetría stale = inacción.** Línea 1942: `if (now - tel['last_update']) > CONTROL_LOOP_STALE_TELEMETRY_S (2.0): continue`. Si MAVLink se cae >2 s, el loop no hace **nada** — ni evasión ni hold ni RTL. El dron sigue con el último setpoint enviado. No hay failsafe de pérdida de telemetría dentro de este loop. (Puede existir en ArduPilot/`mavlink_loop`, no auditado.) **[V] / [?]**

3. **[BAJA] `obs_fresh` no comprueba frescura.** Línea 2118: `obs_fresh = bool(obs)` — solo mira si la lista está vacía. El nombre engaña; la frescura real la da el TTL en `_prune_obstacle_tracks_locked`. No es un bug, pero invita a errores futuros. **[V]**

4. **[BAJA] Limpieza de evasión con un ciclo de retraso.** Al alcanzar el último sub-punto, `path_idx==len` cae a navegación estándar sin limpiar `evasion_path`; se limpia en la iteración siguiente (rama `else`, línea 2642). Inocuo (0.1 s), pero confuso. **[V]**

---

## 2. El recorrido / waypoints (`load_mission` 1325, nav 2653–2809)

- `ejea_default.waypoints`: 12 entradas. seq0 = home (cmd16, 500 m), seq1 = takeoff (cmd22, 523 m, misma lat/lon que home), seq2–10 = inspección (cmd16, 523 m), seq11 = land (cmd21). `current_wp_idx` inicia en **1** en SIM (constants.py:289). Coincide con el paper ("12 waypoints"). **[V]**
- Navegación nominal: a cada WP se envía `set_position_target_global_int` directo (vuelo recto en GUIDED, `WPNAV_SPEED`=8 m/s). Llegada por `haversine < WP_TOLERANCE_M`. Correcto. **[V]**

### Problemas del recorrido

5. **[MEDIA] El loader asume estructura fija de misión.** El takeoff está *hardcodeado* al `current_idx==1` (líneas 1980–2035) y la altitud objetivo es `wps[1]['alt']`. Los comandos QGC reales (16 waypoint / 22 takeoff / 21 land) **no se interpretan**: solo se usan lat/lon/alt. Si el fichero de misión no tiene el takeoff en el índice 1, o intercala comandos no posicionales, el recorrido se rompe silenciosamente. Funciona para *este* fichero, no en general. **[V]**

6. **[BAJA] `WP_TOLERANCE_M` no está en `constants.py`.** El grep no lo encontró ahí; se importa/define en otro punto. Verificar su valor y origen (afecta directamente a cuándo se avanza de waypoint). **[?]**

7. **[BAJA] Salto de waypoint por bloqueo.** Con `EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE=1` y `MAX_HOLD_S=6`, un obstáculo persistente a ≤22 m y dentro del corredor de 12 m hace que tras 6 s se **salte** el waypoint (línea 2671). Para inspección, eso es saltarse un punto de inspección. Aceptable si es intencionado; conviene documentarlo. **[V]**

---

## 3. La evasión dinámica — núcleo PORCE (lo más importante)

### Qué hace realmente el código
1. Visión (YOLO) detecta y **proyecta** cada caja 2D a lat/lon asumiendo **suelo plano** e intrínsecos aproximados solo a partir del VFOV (sin calibración). Estima distancia por intersección del rayo con el plano a `alt_agl`. **No estima velocidad ni predice** posición futura: solo suavizado EMA entre frames. **[V]**
2. El Brain ingiere tracks, los asocia, aplica TTL (dinámico 3 s, estático 30 s en el `.env`) y mezcla posición con EMA (α=0.65 dinámico). **[V]**
3. Si el más cercano entra en `D_react = clip(45 + 2·v, 45, 80)` y ha pasado el intervalo de replan (≥1 s), llama a `PorcePlanner.plan_route`. **[V]**
4. El A\* (`porce_manager.py`) **infla cada obstáculo como un cuadrado** de ±2 celdas (Chebyshev, no círculo) sobre una rejilla local 81×81 de 6 m, y busca ruta hasta el **waypoint actual**. Devuelve sub-puntos. **[V]**
5. El dron sigue los sub-puntos a altitud constante (2D) y re-engancha la misión al terminar. **[V]**

### El problema central: "moving obstacle avoidance" no se sostiene algorítmicamente

**No hay modelo de movimiento del obstáculo en ninguna capa.** Ni velocidad, ni extrapolación, ni time-to-collision, ni velocity obstacles / ORCA, ni separación por velocidad relativa. El obstáculo móvil se trata como un **punto estático en su posición instantánea** (encima suavizada por EMA y potencialmente *stale* hasta el TTL). El método es **replanificación reactiva A\* re-sembrada cada ≥1 s**. Eso es legítimo y defendible — pero **no es** "evitación de obstáculos en movimiento" en el sentido que un revisor de IEEE TII esperará al leer el título. **[V]**

Evidencia de que el manejo de móviles es **marginal**, no robusto:
- **Disparo tardío.** En el caso auditado del paper (`tab:case`), el trigger ocurre a **19.47 m**, cuando `D_react` es 45–61 m. Es decir, el obstáculo *no* disparó la evasión hasta estar **ya dentro del umbral de failsafe (22 m)**. Coherente con latencia de percepción (gate `MIN_SEEN_TO_PUBLISH_BIKER=3`, publish conf 0.35, TTL, EMA) → el biker se "consolida" tarde. Contra un móvil rápido, reaccionar a 19 m con margen final de **1.48 m** sobre el radio duro es muy ajustado. **[I, fuerte]**
- **Cadena de latencia acumulable.** Visión postea con timeout **0.1 s sin reintentos** (`.env` 148) → a 14.6 fps con el Brain ocupado, se pierden actualizaciones. TTL dinámico 3 s mantiene "fantasmas". A 6.4 m/s (≈23 km/h, el caso del paper) un track de 3 s puede estar ~19 m desfasado. **[I]**

### Otros puntos de la evasión
8. **[MEDIA] Inflado cuadrado (Chebyshev), no circular.** `plan_route` añade `(ox±dx, oy±dy)` para dx,dy∈[-2,2] (líneas 146–148). El obstáculo pasa a ser un bloque 5×5 celdas (30 m de lado): la separación garantizada es 12 m lateral pero ~17 m en diagonal. Es conservador (a favor de seguridad), pero no es el "radio de 12 m" que dice el paper; es un **cuadrado de semilado 12 m**. Conviene reflejarlo. **[V]**
9. **[BAJA] Corner-cutting diagonal.** `_get_neighbors` permite moverse en diagonal aunque las dos celdas cardinales adyacentes estén ocupadas. Con inflado de 2 celdas no llega a rozar el obstáculo real, así que en la práctica es seguro aquí. **[V]**
10. **[BAJA] `D_min == D_base == 45`.** El clip inferior de `D_react` es redundante. Cosmético. **[V]**

---

## 4. El paper (Overleaf `Main_formato_ieee.tex`)

### 4.1 ¿Está bien reflejada la aportación regulatoria (la principal)?

**Parcialmente, y sobre todo como *framing*, no como algoritmo.** El paper construye un marco regulatorio rico y bien citado (2019/947, 2019/945, SORA 2.5, AMC/GM, mitigación M1(C) "ground observation", *uninvolved person*, *Ground Risk Buffer*, energía cinética/altura de Annex F). Pero lo que el **código realmente implementa** de todo eso es estrecho:

- Un *uninvolved person* (clases person/bicycle/biker canonizadas a familia "dinámica") se trata en la evasión **exactamente igual** que cualquier obstáculo: **mismo radio de 12 m, mismo inflado, mismo A\***. La única dependencia de clase está en TTL y distancias de asociación de *tracking* (operativo), **no** en la seguridad. **[V]**
- **No hay** Ground Risk Buffer calculado a partir de v/m/h, **ni** campo de riesgo dinámico por *uninvolved person*, **ni** envolvente de seguridad dependiente de clase, **ni** razonamiento de sobrevuelo/altitud. "No-overflight" en el código = "no pasar a <12 m en horizontal" — un *proxy* geométrico fijo, idéntico para una torre y para una persona. **[V]**

Conclusión honesta: la aportación regulatoria es hoy **motivacional/de encuadre** + un *proxy* débil (un desvío de 12 m disparado por detección civil). El paper **lo reconoce** explícitamente (líneas 89, 131, 390, y limitación 610: "operational rather than juridically complete"), lo cual es correcto y honesto. Pero el *gap* entre el marco (página y media de SORA) y la implementación (una inflación fija + un `if clase in {person,bicycle,biker}` para el *naming*) es **grande**, y un revisor lo señalará. Para sostener "operationalizes part of the European ground-risk logic" hace falta **al menos** una de estas dos cosas:
  - (a) Implementar algo *class-dependent*: radios/envolventes distintos para persona vs activo, o un coste de exposición/sobrevuelo en el A\*; o
  - (b) Rebajar la afirmación a "primer paso operativo / prueba de concepto a nivel de controlador" y apoyar el peso del paper en lo que sí está sólido (integración auditable, determinismo, waypoint-preserving).

### 4.2 Otras aportaciones reales (que conviene destacar más)

La aportación más fuerte y *verdaderamente sustanciada por el código* no es la regulatoria, sino la **de sistema**:
- **Integración closed-loop auditable y determinista**: contrato percepción→Brain→planner→autopiloto→auditoría zero-trust, todo observando la misma cadena de decisión. Reproducible desde artefactos del repo. Esto es lo más publicable y diferencial frente a políticas end-to-end "caja negra" (encaja con el EASA AI Roadmap que ya citas). **[V]**
- **Replanificación local *waypoint-preserving*** (el A\* no redefine la misión global; ancla en el WP activo). Decisión de diseño limpia y defendible. **[V]**
- **Escalera de failsafe explícita** (hold → replan lateral → LAND/RTL) que acota el comportamiento bajo fallo del planner. **[V]**
- **Geoposicionamiento monocular** de detecciones (aunque depende de suelo plano + intrínsecos aproximados — debilidad a declarar). **[V]**

Recomendación: reposicionar el paper para que la **auditabilidad + determinismo + integración** carguen el peso de la contribución, y la regulación sea el *encuadre/motivación* (no la prueba técnica). Hoy el título y el abstract apuntan al punto más débil (regulatorio + "moving").

### 4.3 La arquitectura ("Pipeline A" / Simulation Workflow)

La arquitectura descrita (misión QGC → SITL/MAVLink → Brain → visión `/api/obstacles` → A\* → setpoints → UI/audit) **coincide con el código**. **[V]** Observaciones:
- Nomenclatura inconsistente: "Pipeline A" vs "Simulation Workflow" vs "Simulated Environment" se mezclan (p.ej. tabla SOTA comentada y conclusión usan "Pipeline A"; el cuerpo usa "Simulation Workflow"). Unificar. **[V]**
- La lista de roles (líneas 371–381) tiene entradas **vacías**: `SITL:` y `MAVLINK Telemetry:` sin texto. **[V]**
- En el `.env` validado, `UNREAL_TELEMETRY_INGEST_ENABLE=0`: la verdad-terreno de Unreal está **desactivada**; los obstáculos vienen solo de visión. Coherente con el paper, pero conviene decirlo (no hay *ground truth* de obstáculos en la métrica). **[V]**

---

## 5. Discrepancias concretas paper ↔ código/config

| # | Paper dice | Código/config | Severidad |
|---|------------|---------------|-----------|
| D1 | "Moving obstacle avoidance" (título, abstract, método) | No hay velocidad/predicción; replan reactivo a posición instantánea | **ALTA** (sobre-promesa) |
| D2 | "`tower` and `cow` are treated as static" (línea 390) | `.env` 43: `OBS_STATIC_CLASS_NAMES=tower` → **cow es dinámico** | MEDIA (error factual) |
| D3 | Radio de seguridad = círculo de 12 m | Inflado **cuadrado** (Chebyshev) semilado 12 m → ~17 m en diagonal | MEDIA (impreciso) |
| D4 | Caso auditado run `20260220_092802`, sep mín **13.48 m**, margen 1.48 m | La versión en `paper/main.tex` del repo usaba run `20260612_233504` con sep **34.27 m** | MEDIA (números no estables entre versiones; elegir uno) |
| D5 | Regulación "operacionalizada" a nivel controlador | Trato idéntico persona/torre; sin GRB, sin coste de riesgo | MEDIA (encuadre > implementación) |
| D6 | Disparo "well inside the reaction horizon" | Trigger a 19.47 m con `D_react`=45–61 m → en realidad disparo **tardío**, ya dentro de los 22 m de failsafe | MEDIA (explicar la latencia) |

## 6. Erratas del manuscrito (rápidas)

- **Figura 2 ("Detection Stage")** usa la **misma imagen** que la Figura 1 (`Instante_inicial_del_recorrido.png`, líneas 435 y 445). Copia-pega: falta la imagen real de detección. **[V]**
- **`\label{deteccion dentro del margen}` duplicado** (líneas 458 y 469) → referencias ambiguas. **[V]**
- **`ov\end{document}`** (línea 631): un "ov" suelto se imprimirá al final. **[V]**
- Roles `SITL:` y `MAVLINK Telemetry:` vacíos (371–381). **[V]**
- Solapamiento de secciones: "Results" (4) + "Experimental Methodology" (5) + "Experimental Validation" (6) repiten misión/métricas; el propio comentario de PdP (línea 498) sugiere recortar la parte de auditoría. **[V]**

---

## 7. Recomendaciones priorizadas

**Código (si se quiere que "dinámico" sea real):**
1. Decidir el encuadre: o (a) añadir un mínimo modelo de movimiento (estimar velocidad del track por diferencias de posición + inflar en la dirección del movimiento / adelantar el seed), o (b) dejar de llamarlo "moving" y venderlo como *reactive replanning*. (a) cerraría D1/D6 de raíz.
2. Añadir **timeout de evasión activa** (análogo a `WP_BLOCK_MAX_HOLD_S`) para evitar enganche (hallazgo #1).
3. Añadir **failsafe de telemetría stale** (hold/RTL) en vez de solo `continue` (hallazgo #2).
4. Subir el `VISION_POST_TIMEOUT_S=0.1` o añadir 1 reintento; mitiga pérdida de detecciones.

**Paper:**
5. Corregir D2 (cow), D3 (cuadrado vs círculo), las erratas de §6, y fijar **un** run auditado (D4).
6. Reposicionar la contribución: peso en **integración auditable + determinismo + waypoint-preserving**; regulación como motivación honesta ("primer paso operativo"), no como prueba algorítmica.
7. Explicar el disparo a 19.47 m (latencia de percepción) en lugar de presentarlo como holgado; o mostrar que con detección temprana el margen crece.

---

## 8. Estado de implementación (2026-06-13): R_s(clase) EASA

**Hecho — la regulación ya está EN el algoritmo, no solo en la intro.** El radio de inflado pasa a depender de la clase, derivado del SORA Ground Risk Buffer:

- `constants.py` / `porce_defaults.env`: nuevas `SAFETY_GRB_RATIO=1.0`, `SAFETY_DISTANCE_PERSON_FLOOR_M=15`, `_PERSON_MAX_M=40`, `_COW_M=12`, `_TOWER_M=8`.
- `flight_controller.py`: `_obs_safety_radius_m(clase, alt_agl)` → persona `clip(1·h, 15, 40)` (regla 1:1), vaca 12, torre 8, desconocido→persona. `planner_obstacle_subset` etiqueta cada obstáculo con `safety_m`.
- `porce_manager.py`: `plan_route` infla **por-obstáculo** con su `safety_m` (fallback al radio global si falta).

**Verificado** (test aislado, `porce_manager` reconstruido fielmente porque el montaje bash servía copias truncadas): persona desvía 30 m vs torre 18 m; orden persona(23)>vaca(12)>torre(8); regla 1:1 (suelo 15 @5 m, techo 40 @100 m); fallback sin clase rutea. **No verificado por ejecución**: `flight_controller.py` completo (depende de Flask/mavutil/SITL). → correr en tu máquina: `python -m py_compile pipeline/flight_controller.py`.

**Artefactos paper**: `docs/porce_formulacion_matematica.tex` (ahora con `R_s(clase)` + ec. GRB) y `docs/porce_trazabilidad_easa.tex` (tabla clase→radio, tabla de trazabilidad EASA→mecanismo→código, métrica de no-overflight).

### Qué hay que RE-EJECUTAR (no fabrico números)
1. **Caso auditado** (run biker): cambia el radio persona 12→~23 m, así que la ruta, el detour y la separación mínima **cambiarán**. Hay que re-correr el run zero-trust y regenerar `tab:case`. Previsible (no garantizado): separación mínima sube y deja de caer bajo los 22 m de failsafe.
2. **Ablación E2E**: re-correr con los radios por clase y, además, calcular la **métrica de no-overflight** `E_tot` (def. en el .tex) con replanner ON vs OFF.
3. **Coherencia paper**: cambiar "tower and cow are treated as static" → en la config validada **solo `tower` es estático** (cow es dinámica); y "radio de 12 m" → `R_s(clase)`.
4. Re-derivar el techo `R_max=40 m` si la altura operativa real difiere; el suelo 15 m y el ratio 1.0 son conservadores y citables.
