# Unreal: Python Remote Execution y MCP Automation Bridge

Fecha de comprobacion: 2026-06-17

Este documento deja registradas las dos vias activas para controlar el Unreal Editor abierto del proyecto `AirTraffic`.

## Capturas guardadas

- `unreal_python_remote_execution_settings.png`: configuracion del plugin Python.
- `unreal_mcp_automation_bridge_settings.png`: configuracion del plugin MCP Automation Bridge.

## 1. Python Remote Execution

Configuracion observada:

- `Enable Remote Execution`: activado.
- `Multicast Group Endpoint`: `239.0.0.1:6766`.
- `Multicast Bind Address`: `0.0.0.0`.
- `Send Buffer Size`: `2 MiB`.
- `Receive Buffer Size`: `2 MiB`.
- `Multicast Time-To-Live`: `0`.

Tambien esta persistido en `Unreal/Config/DefaultEngine.ini`:

```ini
[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
bRemoteExecution=True
RemoteExecutionMulticastBindAddress=0.0.0.0
```

Prueba ejecutada desde Python externo usando el cliente oficial de Unreal:

```python
remote_execution.py
config.multicast_group_endpoint = ("239.0.0.1", 6766)
config.multicast_bind_address = "0.0.0.0"
```

Resultado real:

- Nodo descubierto: `DESKTOP-LJLDLEA`.
- Unreal Engine: `5.7.4-51494982+++UE5+Release-5.7`.
- Engine root: `D:/Epic Games/UE_5.7/Engine/`.
- Project root: `D:/Deep-AeroTwin-UE57-Test/Unreal/`.
- Project name: `AirTraffic`.
- Mundo activo leido desde Unreal: `Ejea`.
- Actores en nivel: `74`.
- Ejecucion remota: correcta.

Este canal es util para pruebas Python directas contra el editor, especialmente cuando queremos usar el mecanismo oficial del `PythonScriptPlugin`.

## 2. MCP Automation Bridge

Configuracion observada:

- `Always Listen`: activado.
- `Listen Host`: `127.0.0.1`.
- `Listen Ports`: `8090,8091`.
- `Multi Listen`: activado.
- `Require Capability Token`: desactivado.
- `Allow Non Loopback`: desactivado.
- `Enable TLS`: desactivado.

Tambien esta persistido en `Unreal/Config/DefaultGame.ini`:

```ini
[/Script/McpAutomationBridge.McpAutomationBridgeSettings]
bAlwaysListen=True
ListenHost=127.0.0.1
ListenPorts=8090,8091
bMultiListen=True
bAllowNonLoopback=False
bRequireCapabilityToken=False
bEnableTls=False
bEnableNativeMCP=True
NativeMCPPort=3000
```

Prueba ejecutada:

- `POST http://127.0.0.1:3000/mcp` con `initialize`.
- `tools/call` sobre `system_control`.
- Accion `execute_python`.

Resultado real:

- MCP inicializa sesion correctamente.
- `system_control.execute_python` ejecuta Python dentro del editor.
- Mundo activo leido desde Unreal: `Ejea`.
- Actores en nivel: `74`.
- Ejecucion remota: correcta.

Este canal es el mas comodo para automatizaciones desde Codex porque da un endpoint estable HTTP/MCP y permite ejecutar Python sin depender del descubrimiento multicast.

## Recomendacion para el proyecto

Para tareas de produccion del paper y control de escenarios, usar preferentemente el MCP Automation Bridge:

- Es local (`127.0.0.1`), reproducible y ya expone `execute_python`.
- Permite escribir herramientas de auditoria y control de actores sin abrir conexiones multicast.
- Encaja mejor con Codex y con documentacion reproducible.

Mantener Python Remote Execution activado como segunda via de diagnostico:

- Sirve para validar que el `PythonScriptPlugin` esta operativo.
- Permite usar el cliente oficial `remote_execution.py` de Unreal.
- Es util si el MCP Bridge esta caido pero el editor sigue aceptando Python remoto.

Para evitar que YOLO detecte actores, no basta con cambiar un outline visual. El actor debe dejar de renderizar en la vista/captura usada por vision:

- ocultar actor/componentes en juego;
- desactivar visibilidad de componentes;
- opcionalmente desactivar colision/tick;
- si se usa `SceneCaptureComponent2D`, meter actores en `HiddenActors` o usar `ShowOnlyActors`.

Para nuestro caso conviene controlar por carpetas/labels/clases/tags, porque en el nivel vivo las torres y vacas aparecen principalmente como `StaticMeshActor` dentro de carpetas (`towers`, `cows`), no necesariamente como instancias directas `bp_tower` o `bp_cow`.
