# PROJECT MAP — Deep-AeroTwin / AirTraffic (ground truth)

> Leer ESTO primero. Resume hechos verificados (2026-06-13) para no confundir
> proyectos, motores, ni el método de conexión. Si algo aquí contradice una
> suposición, gana este documento (o reverificar).

## 1. Tres proyectos distintos — NO confundir

| Proyecto | Ruta | Motor | Rol | ¿Relevante para el dron? |
|---|---|---|---|---|
| **Deep-AeroTwin** (este) | `D:\Deep-AeroTwin-UE57-Test` | — | PORCE: software del dron (paper) | **SÍ, principal** |
| └ Unreal del dron | `D:\Deep-AeroTwin-UE57-Test\Unreal` → **`AirTraffic.uproject`** | Unreal 5.7 | Simulador visual (mapa **WorldSim**, Cesium) | **SÍ** |
| **RealSim** | `D:\INVESTIGACION_AI_WORLD\RealSim` | Unreal 5.7 | Crowd/tráfico Pamplona (framework **Mass**) | NO (proyecto aparte; sin vacas/ciclistas) |
| **Parkoff** | `D:\KAIOAENGINE\Parkoff-Unity` | Unity 6000.3 | Sin relación | NO — ignorar |

Aclaraciones clave que ya me confundieron una vez:
- El MCP de **Unity** conectado es de *Parkoff*, **no** del dron.
- **Mass** (entidades, ZoneGraph) es **solo de RealSim**. En el dron NO se usa Mass.
- En el dron, los obstáculos van **por ACTOR** (C++/Blueprint), no por Mass.

## 2. Simulador del dron = Unreal "AirTraffic"

- `.uproject`: `Unreal/AirTraffic.uproject`. Mapa abierto: **WorldSim** (`/Game/WorldSim`), mundo Cesium georreferenciado.
- Módulo C++: `Unreal/Source/AirTraffic/`.

Obstáculos (clases YOLO del dron: **biker, cow, tower**):

| Obstáculo | Implementación | Movimiento | Velocidad |
|---|---|---|---|
| **Ciclistas** | `APelotonSplineActor` (C++: `Source/AirTraffic/{Public,Private}/PelotonSplineActor.{h,cpp}`). Mallas `/Game/biker_mesh`, `/Game/bp_biker`. BP `/Game/Peloton/BP_PelotonSpline`. | SÍ — recorren un spline cerrado en `Tick` | `SpeedCmPerSecond` (default **850 cm/s = 30.6 km/h**). Paper usa 23 km/h → bajar a ~640 cm/s |
| **Vacas** | `/Game/bp_cow` (ya colocadas en el mundo). Movidas por `UCowHerdSubsystem` (C++, sin tocar el Blueprint). | SÍ — errático stop-and-go (wander) desde el subsystem | 0,8–1,2 m/s (80–120 cm/s) |
| **Torres** | `/Game/bp_tower` | NO (estático) | — |

Notas PelotonSplineActor: `RiderCount=14`, formación en filas, `bAnimateInGame=true`,
`bAnimateInEditor=false`, `ShouldTickIfViewportsOnly()=bAnimateInEditor`. La velocidad
real efectiva puede estar override en el BP `BP_PelotonSpline` o en la instancia del
nivel; editar solo el default C++ puede quedar sombreado → verificar en editor.

## 3. Conexión a Unreal desde Claude (IMPORTANTE)

- Las tools `mcp__unreal__*` = **runreal/unreal-mcp** sobre **Python Remote Execution (6766)**.
  NO usan el "MCP Automation Bridge" (8090/8091). Ref: `D:\INVESTIGACION_AI_WORLD\RealSim\GUIA_MCP_UNREAL.md`.
- Requisitos: editor del dron abierto, plugin Python + "Enable Remote Execution" ON
  (`Config/DefaultEngine.ini`: `bRemoteExecution=True`), foco en el viewport.
- **Regla de oro: un solo editor Unreal abierto a la vez** (dos compiten en 6766 y el canal cae).
- Error "No command channel open!" → fix: dejar un solo editor; **reiniciar el editor** y/o
  **cerrar y reabrir Claude Desktop** (respawnea el `node` del MCP); matar `node.exe` zombis.
- Mi sandbox bash **no** alcanza el multicast 6766 (TTL 0) → no puedo usar Remote Execution
  directo; o entro por runreal, o el usuario ejecuta mi Python en su consola de Unreal.

## 4. Software PORCE (sistema del paper) = `pipeline/`

- `flight_controller.py` (loop de control + evasión), `porce_manager.py` (A* local),
  `vision_system.py` (YOLO + geoposicionamiento), `constants.py`, `porce_defaults.env`.
- Ya implementado: **radio de seguridad por clase `R_s(clase)`** derivado del SORA Ground
  Risk Buffer (regla 1:1): persona `clip(altura,15,40) m`, vaca 12 m, torre 8 m.
- Artefactos en `docs/`: `auditoria_porce_loop_evasion_paper_20260613.md`,
  `porce_formulacion_matematica.tex`, `porce_trazabilidad_easa.tex`,
  `unreal_conexion_mcp_python.md`, `unreal_drone_scene_inspect.py`.

## 5. Velocidades realistas objetivo
- **Ciclista**: 23 km/h = **639 cm/s** (consistente con el paper; rango real 18–25 km/h).
- **Vaca**: pastoreo errático, **0.8–1.2 m/s** en ráfagas (mover 2–6 s, parar 4–12 s, giro aleatorio).

## 6. Estado (actualizado 2026-06-13)
- [x] **Ciclista**: `SpeedCmPerSecond` 850 → **640 cm/s** (~23 km/h) en `PelotonSplineActor.h`.
- [x] **Vaca**: **World Subsystem C++** `UCowHerdSubsystem` (`Source/AirTraffic/{Public,Private}/CowHerdSubsystem.{h,cpp}`). Sin Blueprint y sin colocar nada: al arrancar el juego encuentra las `bp_cow` **ya colocadas** (`IsA(/Game/bp_cow.bp_cow_C)`, fallback por nombre) y las mueve con wander errático stop-and-go (0,8–1,2 m/s), seed por instancia. Lógica verificada con test g++ (dentro de radio, alterna move/pause, velocidad en rango).
- [x] **Paper EASA cerrado**: `docs/Main_formato_ieee_corregido.tex` (R_s(clase)+GRB, budget reactivo, tabla de trazabilidad, métrica no-overflight; erratas corregidas). **Compila** (pdflatex+bibtex, 0 refs/citas rotas) → `docs/Main_formato_ieee_preview.pdf`.
- [ ] **Recompilar AirTraffic** (Live Coding / VS) para que entren el ciclista y `UCowHerdSubsystem`. Yo no puedo compilar C++ de UE aquí.
- [ ] Las vacas se mueven solas al dar a **Play** (el subsystem las descubre). Cero Blueprint, cero colocar. Verificar en el log: "CowHerdSubsystem: driving N cow(s)".
- [ ] Verificar que el override de velocidad del ciclista en `BP_PelotonSpline`/instancia no sombrea el default 640 — requiere el editor.
- [ ] Subir el `.tex` corregido a Overleaf.
- [ ] Re-ejecutar runs si se quieren números nuevos del caso auditado (radio persona 12→23 m).
- [!] Conexión runreal inestable ("No command channel open"); reactivar según §3 (reiniciar editor / Claude Desktop).
