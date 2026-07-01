# Deep-AeroTwin Workflows

Este repo contiene dos workflows distintos. No deben mezclarse porque resuelven problemas operativos diferentes.

## 1. SIMULATION

Proposito:

- Validar PORCE de extremo a extremo en entorno simulado.
- Probar mision, waypoints, reaccion a obstaculos, evasion y failsafe.

Como funciona:

- `SITL` publica telemetria MAVLink.
- `Brain` sigue mision y decide navegacion.
- `Vision` detecta objetos y publica obstaculos.
- `Viz` consume `GET /api/ui/data`.
- Unreal puede actuar como consumidor visual opcional.

Caracteristicas clave:

- Hay mision cargada desde `pipeline\ejea_default.waypoints`.
- El dron sigue ruta.
- Hay logica de evasion, replan, hold, lateral replan y `LAND/RTL`.
- El launcher raiz validado es LANZAR_TODO_PAPER.bat, que prepara Unreal/PIE y lanza el workflow SIMULATION completo.

## 2. DIGITAL TWIN / REAL_TWIN

Proposito:

- Soportar vuelo real con piloto humano usando Unreal como interfaz visual principal.
- Representar en Unreal los objetos reales detectados alrededor del dron.

Como funciona:

- El dron no sigue mision ni ruta automatica como idea central del flujo.
- El piloto humano controla el vuelo.
- La telemetria real entra por MAVLink al Brain.
- El YOLO real del dron publica detecciones a `POST /api/obstacles`.
- El Brain publica entidades para Unreal.
- Unreal hace `spawn/update/despawn` de actores en la escena.

Cadena funcional:

1. Entrada de detecciones reales.
2. Normalizacion de `entity_id`, `type`, `confidence` y posicion (`lat/lon` y/o `world_m`).
3. Publicacion en el estado que sirve `GET /api/ui/data`.
4. Consumo por `UPorceTelemetryComponent` en Unreal.
5. Representacion visual para el piloto.

Entidades objetivo:

- `bike`
- `cow`
- `tower`

## Diferencia operativa clave

`SIMULATION`:

- El problema central es navegacion autonoma.
- Unreal es auxiliar.

`DIGITAL TWIN`:

- El problema central es visualizacion operacional para el piloto.
- Unreal es principal.

## Estado actual del repo

- LANZAR_TODO_PAPER.bat fuerza el arranque operativo completo en SIMULATION.
- tools\legacy_root_bats\launch_digital_twin.bat conserva el wrapper historico para REAL_TWIN.
- El runtime `REAL_TWIN` no carga mision y no arranca control autonomo.
- `REAL_TWIN` reutiliza el mismo backend y los mismos endpoints que `SIMULATION`.
- REAL_TWIN no levanta vision_system.py local en su wrapper archivado.

## Notas de implementacion relevantes

- El consumidor Unreal actual usa `GET /api/ui/data`.
- El plugin Unreal resuelve de forma directa `tower`, `cow`, `bike` y los aliases `biker`, `person`, `bicycle`.
- El componente `UPorceTelemetryComponent` puede alternar entre `UnrealAssets` y `SemanticProxy` sin cambiar el input.
- El Brain normaliza los aliases legacy a `bike` y reemite solo tipos canonicos en `GET /api/ui/data`.

## Papers y baremo AYTE Doctor

- `tools\sync_papers_to_ayte_doctor.ps1` sincroniza las carpetas de paper hacia `D:\ayte_reclamacion\AYTE_DOCTOR\papers`.
- La copia es no destructiva y queda auditada con `COPY_MANIFEST.md`.
- El script falla si el destino no coincide en recuento de archivos y suma de bytes con el origen.
