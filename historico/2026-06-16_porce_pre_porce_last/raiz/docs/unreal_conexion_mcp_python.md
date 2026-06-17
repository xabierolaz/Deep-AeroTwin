# Conexión a Unreal: Automation Bridge (MCP) y Python Remote Execution

Proyecto Unreal abierto: mapa **WorldSim** (`/Game/WorldSim`), mundo Cesium georreferenciado.
Obstáculos (vacas/ciclistas/peatones/vehículos) implementados con el framework **Mass**
(`/Game/RealSim/Mass/...`), no como actores individuales.

Dos vías para automatizar Unreal desde fuera. Ambas confirmadas por el usuario (2026-06-13).

> **IMPORTANTE (transporte que usa Claude):** las herramientas `mcp__unreal__*`
> van EXCLUSIVAMENTE por el **MCP Automation Bridge** (puertos 8090/8091), que
> requiere **"Always Listen" = ON**. El **"Enable Remote Execution"** (multicast
> 239.0.0.1:6766) es un canal SEPARADO que las tools de Claude **NO** usan.
> Con solo Remote Execution activo, Claude no conecta ("No command channel open!").
> Para que Claude controle Unreal: mantener "Always Listen" marcado y el editor
> con foco en el viewport del nivel.

## 1. MCP Automation Bridge (lo que usa Claude con `mcp__unreal__*`)

Plugin "MCP Automation Bridge" → Settings (se guardan en `DefaultGame.ini`).

| Ajuste | Valor |
|---|---|
| Always Listen | ✅ |
| Listen Host | 127.0.0.1 |
| Listen Ports | 8090, 8091 |
| Multi Listen | ✅ |
| Listen Backlog | 10 |
| Accept Sleep Seconds | 0.01 |
| Require Capability Token | ❌ (sin token) |
| Allow Non Loopback | ❌ |
| Enable TLS | ❌ |

Uso: herramientas `mcp__unreal__editor_run_python`, `editor_get_world_outliner`,
`editor_search_assets`, `editor_update_object`, etc.

**Nota de fiabilidad observada:** el canal se cae ("No command channel open!") si el
editor de Unreal pierde foco, está en el panel de Settings, compilando, o en transición
de Play mode. Solución: volver a hacer foco en el **viewport del nivel**. El bridge sigue
escuchando (Always Listen), solo hay que reactivar el canal de comandos.

## 2. Python Remote Execution (built-in de Unreal, alternativa)

Plugin "Python" → sección **Python Remote Execution**. Más robusto para scripting directo.

| Ajuste | Valor |
|---|---|
| Enable Remote Execution? | ✅ |
| Multicast Group Endpoint | 239.0.0.1:6766 |
| Multicast Bind Address | 0.0.0.0 |
| Send Buffer Size | 2 MiB |
| Receive Buffer Size | 2 MiB |
| Multicast Time-To-Live | 0 |

Uso: protocolo de descubrimiento por multicast UDP de Unreal. Cliente oficial
`remote_execution.py` (de `Engine/Plugins/Experimental/PythonScriptPlugin/.../remote_execution.py`)
o equivalente: descubre el nodo por multicast 239.0.0.1:6766, abre un comando, y ejecuta
Python en el editor. Bind 0.0.0.0 = escucha en todas las interfaces. TTL 0 = solo host
local (subir TTL si cliente en otra máquina/subred).

Comparativa: el Remote Execution nativo no depende del plugin MCP y suele ser más estable
para lotes de Python; el MCP Bridge da herramientas estructuradas (outliner, assets,
screenshots) además de Python. Para mover/ajustar entidades Mass sirve cualquiera de los dos.

## Notas de uso para este proyecto
- Todo Python debe empezar con `import unreal`.
- Las entidades Mass se configuran vía sus `MassEntityConfigAsset`
  (`DA_RealSimCrowdPedestrian`, `DA_RealSimRoadVehicle`) y traits de movimiento / ZoneGraph,
  no por actor. La velocidad realista se fija ahí.
