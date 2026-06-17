# Auditoría técnica: rutas ciclistas, subsystem vacas y deuda técnica del proyecto

Fecha: 2026-06-13. Convención: **[V]** verificado por lectura directa · **[I]** inferencia · **[?]** sin verificar.

> Nota de método: parte del escaneo de deuda técnica lo hizo un subagente leyendo el **montaje** del repo, que durante la sesión sirvió copias **truncadas** de algunos ficheros grandes (`flight_controller.py`, `constants.py`). Por eso **los números de línea concretos del §3 son aproximados**; las categorías y ficheros están verificados por lectura directa donde se indica.

---

## 1. Veredicto

- **Rutas de ciclistas (`APelotonSplineActor`)**: el **script es correcto**. La lógica de spline+formación+loop+velocidad está bien implementada. Lo único: la *geometría* de la ruta (forma/posición del spline) es por-instancia en el editor — no la puedo verificar sin el editor en vivo. **[V]**
- **Vacas (`UCowHerdSubsystem`)**: funciona y ya es robusto; corregí un fallo real de mi propio código (descubrimiento de una pasada → no recogía vacas streameadas por World Partition). **[V]**
- **Deuda técnica del proyecto**: **moderada-alta**, concentrada en `flight_controller.py`/`vision_system.py` (god objects, sin tests, excepciones silenciosas, estado global mutable). El planner y el C++ de Unreal están sanos. **[V/I]**

---

## 2. Rutas de ciclistas — verificación (`PelotonSplineActor.cpp/.h`)

**Correcto [V]:**
- `Tick` (83–104): avanza `RuntimeLeadDistance += SpeedCmPerSecond·dt` y reubica riders. Anima en juego (`bAnimateInGame`) o editor (`bAnimateInEditor`). Bien.
- `NormalizeSplineDistance` (636–656): envuelve la distancia con `Fmod` para splines cerrados (maneja negativos: `+ SplineLength`), o `Clamp` si abierto. **Correcto** para el recorrido cíclico.
- `GetFormationOffset` (581–604): formación de pelotón realista — filas de capacidad creciente (1,2,3,… hasta `MaxRidersPerRow`), carriles centrados, *stagger* en filas impares. Bien.
- `UpdateRiderTransforms` (349–425): cada rider en `LeadDistance − offset.X` sobre el spline + desplazamiento lateral `offset.Y`; soporta 3 modos de render (StaticMeshComponents / InstancedStaticMesh / ChildActor). Correcto.
- Velocidad: bajada **850 → 640 cm/s (~23 km/h)** en el header, consistente con el paper.

**Observaciones / riesgos:**
1. **[MEDIA] La geometría de la ruta es genérica.** El spline por defecto del constructor (27–30) es un **lazo pequeño** (~±9–12 m): el pelotón da vueltas en círculo. Para ser un obstáculo que el dron evita, la **instancia colocada** debe tener un spline que **cruce el corredor de inspección**. Eso se define en el editor; el código no lo garantiza. → "que la ruta tenga sentido" es colocación, no código. **[V]**
2. **[BAJA] El override de velocidad puede sombrear el default.** Si `BP_PelotonSpline` o la instancia en el nivel fijaron `SpeedCmPerSecond`, mi cambio del default C++ (640) no se aplica. Verificar en el editor. **[V]**
3. **[BAJA] 169 UPROPERTY** en un solo actor (incluye todo el subsistema de "ghosts"/heatmap de visualización). Funciona, pero conviene agrupar en structs (`FPelotonFormation`, `FPelotonGhosts`). **[V]**
4. **[BAJA] Sin colisión/altura de terreno**: riders siguen el spline en su Z; en terreno Cesium irregular pueden flotar/hundirse según el spline. **[I]**

**Conclusión:** el script funciona. La frase "que las rutas tengan sentido" depende de colocar el spline cruzando el corredor — acción de editor.

---

## 3. `UCowHerdSubsystem` — auto-auditoría (mi código)

**Corregido en esta auditoría [V]:**
- **Descubrimiento de una sola pasada → re-escaneo periódico incremental.** El mapa `WorldSim` usa **World Partition** (streaming). Mi versión inicial descubría las vacas una vez en el primer Tick; las que streamean después se perdían. Ahora re-escanea cada 3 s y añade solo las nuevas (`AlreadyTracked`), sin duplicar.

**Limitaciones restantes (documentadas, no bloqueantes):**
1. **[MEDIA] Z constante**: las vacas pastan en el plano XY a la Z de su spawn. En terreno irregular pueden flotar/hundirse. Un *line trace* al suelo lo resolvería (mismo límite que el pelotón). **[V]**
2. **[BAJA] Sin evitación entre vacas**: pueden solaparse. Cosméticamente menor. **[V]**
3. **[BAJA] Parámetros hardcodeados** (velocidades, tiempos, seed) en constantes del `.cpp` — es el precio de "sin Blueprint, sin UPROPERTY". Si se quiere tunear sin recompilar, exponer vía `UDeveloperSettings`. **[V]**
4. **[?] No compilado en UE** (no tengo compilador de Unreal aquí): lógica de wander verificada con test g++; scaffolding calcado de código que ya compila. Recompilar y confirmar.

---

## 4. Deuda técnica del proyecto (escaneo amplio)

Severidades; líneas aproximadas (ver nota de método).

| # | Hallazgo | Sev. | Evidencia |
|---|----------|------|-----------|
| D1 | **`control_loop()` god function (~950 líneas)** mezcla telemetría, evasión, failsafe, logging. | **ALTA** | `flight_controller.py` 1855–2809 **[V]** |
| D2 | **Sin tests unitarios** en `pipeline/` ni `tools/` (solo el `__main__` del planner). Ruta crítica sin red. | **ALTA** | listado de `pipeline/` **[V]** |
| D3 | **Excepciones silenciosas** (`except Exception: pass`/sin log) que tragan errores (telemetría, cierre MAVLink, normalización de obstáculos). | **ALTA** | varias en `flight_controller.py`, `vision_system.py`, `porce_manager.py` **[V categoría]** |
| D4 | **Estado global mutable** `state` (30+ campos) con un único `state_lock`, accedido por 3 hilos (control_loop, mavlink_loop, HTTP). Riesgo de *races* en `evasion_*`. | **MEDIA** | `flight_controller.py` `state=` ~287 **[V]** |
| D5 | **`vision_system.py` clase gigante** (~2200 líneas, ~41 métodos): captura+tracking+proyección+render en una clase. | **MEDIA** | `vision_system.py` **[V tamaño]** |
| D6 | **Docstrings casi nulos** en funciones críticas largas (`_ingest_obstacles_locked`, `control_loop`). | **MEDIA** | **[V categoría]** |
| D7 | **Higiene de repo**: `tmp/` con artefactos (incl. mi `overleaf_extract`); verificar que está en `.gitignore`. Figuras/PDF commiteados (OK si son finales). | **BAJA** | `tmp/`, `paper/.../figures` **[V]** |
| D8 | **Código comentado/muerto** disperso (alternativas en comentarios en lugar de feature flags). | **BAJA** | `flight_controller.py`, `vision_system.py` **[I]** |
| D9 | **`MockMaster`/`_MockMav`** duplican parcialmente la interfaz de `pymavlink` (frágil ante cambios de API). | **BAJA** | `flight_controller.py` 363–467 **[V]** |

**Sano (bajo riesgo) [V]:** `porce_manager.py` (planner A\* bien compartimentado, ~298 líneas), C++ de Unreal (`PelotonSplineActor`, `CowHerdSubsystem`), externalización de parámetros en `constants.py` (casi todo vía env).

---

## 5. Recomendaciones priorizadas

**Alto impacto / arranca aquí:**
1. **Tests** del planner y de los helpers puros (`adaptive_reaction_distance_m`, `waypoint_blocking_obstacle_info`, `_ingest_obstacles_locked`, `build_lateral_replan_route`). Son funciones casi puras → fáciles de testear; cubren la ruta crítica. (Ya validé el planner por clase con un test; extender.)
2. **Eliminar excepciones silenciosas**: cambiar `except Exception: pass` por excepción específica + `log.exception(...)`. 2–4 h, alto valor diagnóstico.
3. **Trocear `control_loop()`**: extraer `evaluate_evasion()`, `apply_failsafe()`, `follow_waypoint()` como funciones puras testeables. Reduce el god function sin reescribir todo.

**Medio plazo:**
4. Encapsular `state` en una clase con acceso por método (o snapshots `deepcopy` en *boundaries*), para acotar *races*.
5. Partir `VisionSystem` en `CameraCapture` / `TrackingEngine` / `Projector`.
6. CI mínima: `pytest` + lint, *gate* en PR.

**Rápidas:**
7. Confirmar `tmp/` en `.gitignore`; limpiar artefactos.
8. Docstrings en las 6–8 funciones >50 líneas más críticas.

---

## 6. Qué NO he podido verificar (necesita el entorno vivo)
- Que el pelotón **cruce el corredor** (geometría del spline en el nivel) — editor.
- Compilación del C++ de Unreal — recompilar AirTraffic (Live Coding/VS).
- Comportamiento del loop completo en vivo (SITL+MAVLink+vision+Unreal) — máquina del usuario.
