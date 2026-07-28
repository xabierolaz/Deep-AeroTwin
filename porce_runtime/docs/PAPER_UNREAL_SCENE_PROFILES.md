# Perfiles de escena Unreal para el paper

Fecha de preparacion y prueba: 2026-06-17
Ultima actualizacion operativa: 2026-06-20

Este documento define como preparar la escena `Ejea` de Unreal para cada experimento del paper, ocultando o mostrando los obstaculos que deben aparecer en camara y por tanto en YOLO.

## Archivos creados

- `LANZAR_TODO_PAPER.bat`: launcher canonico para paper. Ejecuta preparacion por commandlet, arranca Unreal/PIE y lanza la pipeline.
- `Unreal/Scripts/apply_cesium_paper_streaming_profile.py`: aplica cache/streaming Cesium para evitar que Google Photorealistic 3D Tiles se descargue y descarte con demasiada agresividad.
- `Unreal/Scripts/configure_cesium_ejea_route_precache.py`: guarda 28 camaras virtuales en el `CesiumCameraManager` siguiendo la ruta de Ejea para calentar tiles de la zona/ruta desde el arranque.
- `Unreal/Scripts/canonicalize_peloton_only.py`: reconstruye la escena con pelotones `APelotonSplineActor`, sin ciclistas legacy ni ghosts.
- `Unreal/Scripts/apply_paper_all_obstacles_profile_and_save.py`: perfil operativo actual con pelotones, torres y vacas activados para la ejecucion completa.
- `Unreal/Scripts/audit_paper_peloton_state.py`: auditoria de escena; falla si hay ghosts, ciclistas sueltos, rutas no perpendiculares o actores temporales.
- `tools/unreal_apply_paper_profile.py`: CLI historica/interactiva via MCP. Se conserva para inspeccion manual, pero no es el camino canonico de produccion.
- `tools/unreal_execute_python.py`: CLI generica para ejecutar Python dentro del Unreal Editor abierto via MCP.

El canal usado es el MCP nativo documentado en `UNREAL_CONEXIONES_PYTHON_MCP.md`.

## Grupos detectados en la escena viva

Comprobado contra Unreal Editor abierto, mundo `Ejea`:

| Grupo | Criterio principal | Actores |
| --- | --- | ---: |
| `towers` | carpeta `towers`, labels `t0`, `tower14`, etc. | 42 |
| `cows` | carpeta `cows`, labels `cowanimateduntitled...` | 8 |
| `bikers` | carpeta `bikers`, clases/labels `ciclista...`; debe quedar a cero para el paper | 0 |
| `peloton` | actores `BP_PelotonSpline_C` generados por `canonicalize_peloton_only.py` | 18 |

Importante: torres y vacas estan principalmente como `StaticMeshActor`, no como instancias directas `bp_tower` o `bp_cow`. Por eso el control se hace por carpeta/label/clase, no solo por Blueprint.

## Perfiles disponibles

| Perfil | Uso | Visible | Oculto | Target YOLO recomendado |
| --- | --- | --- | --- | --- |
| `paper_static_tower` | Figura 1, obstaculo estatico | `towers` | `cows`, `bikers`, `peloton` | `tower` |
| `paper_wp1_wp2_tower` | Figura 1 activa, torre unica colocada en WP1->WP2 | solo `t0` | resto de torres, `cows`, `bikers`, `peloton` | `tower` |
| `paper_moving_peloton` | Figura 2, obstaculos dinamicos con torres activas | `peloton`, `towers` | `cows`, `bikers` | `biker,tower` |
| `paper_all_obstacles` | Reset/debug | todo | nada | `biker,cow,tower` |
| `paper_no_obstacles` | Control/debug sin obstaculos | nada | todo | vacio |
| `paper_static_cow` | Control extra | `cows` | `towers`, `bikers`, `peloton` | `cow` |

## Comandos canonicos

Arranque completo para figuras/video del paper:

```powershell
.\LANZAR_TODO_PAPER.bat
```

Preparacion commandlet equivalente, usada por el launcher:

```powershell
& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\canonicalize_peloton_only.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\apply_paper_all_obstacles_profile_and_save.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\audit_paper_peloton_state.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput
```

## Comandos historicos MCP

Listar perfiles:

```powershell
python tools\unreal_apply_paper_profile.py --list-profiles
```

Ver resumen de la escena:

```powershell
python tools\unreal_apply_paper_profile.py --describe
```

Probar sin modificar la escena:

```powershell
python tools\unreal_apply_paper_profile.py --profile paper_static_tower --dry-run
python tools\unreal_apply_paper_profile.py --profile paper_moving_peloton --dry-run
```

Aplicar caso estatico de la Figura 1:

```powershell
python tools\unreal_apply_paper_profile.py --profile paper_wp1_wp2_tower
```

Aplicar caso movil/peloton:

```powershell
python tools\unreal_apply_paper_profile.py --profile paper_moving_peloton
```

Restaurar todos los obstaculos visibles:

```powershell
python tools\unreal_apply_paper_profile.py --profile paper_all_obstacles
```

Para inspeccion detallada por actor:

```powershell
python tools\unreal_apply_paper_profile.py --describe --actors
python tools\unreal_apply_paper_profile.py --profile paper_static_tower --dry-run --actors
python tools\unreal_apply_paper_profile.py --profile paper_static_tower --details
```

## Resultado de validacion

`paper_wp1_wp2_tower` aplicado correctamente:

```text
towers: 1 visible, 41 ocultas
cows: 0 visibles, 8 ocultas
bikers: 0 visibles, 10 ocultos
peloton: 0 visibles, 1 oculto
t0: lat=42.229048654636124, lon=-1.2344042327389924
```

Este perfil mueve `t0` a la posicion validada para la Figura 1 activa:

```text
progress_wp1_wp2 = 0.56
lateral_m = +8.0
east_m = 56.05096609440895
north_m = -71.87032532501878
```

`paper_moving_peloton` aplicado correctamente:

```text
towers: 42 visibles, 0 ocultas
cows: 0 visibles, 8 ocultas
bikers: 0 visibles
peloton: 18 visibles
```

Despues de las pruebas se restauro `paper_all_obstacles`:

```text
towers: 42 visibles
cows: 8 visibles
bikers: 0 visibles
peloton: 18 visibles
```

## Que cambia exactamente

Cada perfil hace tres cosas sobre los actores controlados:

- `set_actor_hidden_in_game(...)`, para afectar a juego/render.
- `set_is_temporarily_hidden_in_editor(...)`, para reflejarlo tambien en el editor.
- `set_visibility(...)` y `set_hidden_in_game(...)` en componentes cuando la API lo permite.

No guarda el nivel automaticamente. La intencion es preparar la escena para una captura/simulacion concreta sin dejar un cambio irreversible.

## Relacion con YOLO y el pipeline

Esto controla que se renderiza en Unreal. Para que el experimento sea consistente, el pipeline de vision tambien debe filtrar las clases esperadas:

- Figura 1 / torre estatica: `PORCE_VISION_TARGET_CLASS_NAMES=tower`.
- Figura 2 / peloton con torres activas: `PORCE_VISION_TARGET_CLASS_NAMES=biker,tower`.
- Debug completo: `PORCE_VISION_TARGET_CLASS_NAMES=biker,cow,tower`.

Ocultar un actor del Outliner no es suficiente si sigue renderizando en la camara. Estos perfiles actuan sobre visibilidad de actor y componentes para que YOLO no vea los grupos ocultos. Para la ejecucion final completa ya no son el camino principal; se conservan para inspeccion interactiva.

Para las capturas finales, la ventana YOLO debe ejecutarse con `PORCE_VISION_OVERLAY_MODE=paper`. Ese modo muestra solo evidencia visual util para el paper: cajas, clase, id de track, confianza, distancia, estado `published/tracking/held`, obstaculo mas cercano y estado resumido del planner. El modo `debug` conserva contadores internos, coordenadas, rechazos y mascaras de header/footer para diagnostico, pero no debe usarse en figuras finales.

## Cache y precarga Cesium / Google Tiles

El mapa de Ejea usa `Google Photorealistic 3D Tiles` via `CesiumForUnreal` (`IonAssetID=2275207`). No es un mesh local cocinado en el proyecto: Cesium decide tiles por camaras activas y los descarga/cachea bajo demanda. Por eso una apertura fria tarda: no solo carga el `.umap`, tambien resuelve tiles remotos y mallas/texturas de Google.

El launcher canonico aplica ahora dos pasos antes del perfil de obstaculos:

- `apply_cesium_paper_streaming_profile.py`: `MaximumCachedBytes=8589934592`, `MaximumSimultaneousTileLoads=96`, `MaximumScreenSpaceError=8`, `PreloadAncestors=True`, `PreloadSiblings=True`, `ForbidHoles=True`, `EnableFrustumCulling=False`, `EnableFogCulling=False`, `UpdateInEditor=True`, `UnloadEditorTilesInPlayMode=False`; ademas aumenta la cache SQLite de Cesium a `MaxCacheItems=200000` y `RequestsPerCachePrune=50000`.
- `configure_cesium_ejea_route_precache.py`: anade 28 `AdditionalCameras` virtuales al `CesiumCameraManager`, a 523 m MSL, FOV 82 deg y pitch -58 deg, muestreadas sobre la ruta. No renderizan ni aparecen en las capturas; solo fuerzan seleccion/precarga/cache de tiles en la banda de vuelo.

Esto no elimina la primera descarga si la cache esta vacia o si Google invalida contenido, pero evita descartar miles de requests entre aperturas y reduce el popping/carga durante vuelos repetidos. La auditoria operativa queda en `pipeline/logs/cesium_streaming_state_latest.json`.

## Criterio visual para el peloton

Para el paper, el perfil de peloton debe mostrar ciclistas actuales controlados por `APelotonSplineActor` y las torres reactivadas para el contexto de obstaculos estaticos.

- No deben verse vacas ni ciclistas sueltos heredados.
- No deben verse meshes fantasma de ciclista delante o detras del peloton, porque YOLO puede detectarlos como ciclistas reales y ademas confunden la lectura.
- No deben existir ghosts, predicciones, duplicados rojos ni actores temporales persistentes para torres o vacas. Las torres del paper son solo las torres reales del mapa; las vacas permanecen ocultas en `paper_moving_peloton`.
- Todo actor temporal `DAT_*` debe borrarse al preparar perfiles o al terminar una captura. La auditoria `audit_paper_peloton_state.py` falla si queda algun `DAT_*` persistente o si detecta ghosts/predicciones no ciclistas.
- Si se necesita mostrar prediccion o historia de movimiento, hacerlo en paneles graficos/logs o como anotacion editorial posterior a YOLO. Si se hace dentro de Unreal, debe ser geometria no-ciclista claramente no detectable como biker, por ejemplo una linea/flecha fina o disco bajo en el suelo, no copias transparentes del rider mesh.
- La ruta visual del peloton debe cruzar la ruta del dron de forma perpendicular, de izquierda a derecha o derecha a izquierda, para que el caso sea legible en camara.
- El degradado de color solo es aceptable como ayuda visual si no crea clases detectables por YOLO. En Unreal deben quedar ciclistas reales actuales y, como mucho, marcas de suelo no-ciclistas o overlays post-YOLO para explicar prediccion.

## Estado operativo 2026-06-18

Se canonicalizo la escena hacia 18 pelotones controlados por codigo, dos por cada tramo util `WP01` a `WP09`.

- Etiquetado: `Peloton_Route_WP##_T##_Cross`.
- Cada peloton usa una spline cerrada de 2 puntos, con linea transversal de 96 m y loop de ida/vuelta de 192 m.
- No hay tramos de retorno paralelos a la ruta del dron.
- Las alturas de spline se fijan a la cota real del simulador/Cesium usada por el vuelo: 500.08 m MSL (500 m de terreno + 8 cm de margen). El DEM externo 429-444 m MSL queda descartado porque dejaba los pelotones unos 60 m bajo el terreno renderizado.
- Los materiales de `biker_mesh` se asignan por slot con una paleta mate no azul/blanca y sin emissive: radios graphite, piel muted, cuadro charcoal, cadena negra, detalles umber, figura olive y sillin negro.
- Los ciclistas se mueven desde el arranque de la escena: incluso cuando la sincronizacion usa `PlayerCameraManager`, el avance incluye un termino autonomo de bucle para que no esperen a que el dron se desplace.

Validaciones ya realizadas:

- `Unreal/Source/AirTraffic/Public/PelotonSplineActor.h` y `Private/PelotonSplineActor.cpp` compilan tras anadir materiales por slot, desactivar ghosts por defecto y anadir sincronizacion de movimiento.
- `Unreal/Scripts/audit_paper_peloton_state.py` confirma 0 loose bikers, 18 pelotones, 0 ghost components, materiales sin blanco/azul heredado, rutas perpendiculares y splines en 500.08 m MSL +/- 3 m.
- `Unreal/Scripts/apply_paper_all_obstacles_profile_and_save.py` deja pelotones, torres y vacas activados para la ejecucion completa actual, sin ghosts ni actores temporales.
- La ventana debug de OpenCV debe mantenerse apagada para grabacion final: `PORCE_VISION_DEBUG_WINDOW=0`, `PORCE_VISION_RECORD_ENABLE=1`.

Hallazgo critico resuelto:

- `BP_AirplaneMarker` no se mueve durante el runtime real que captura Vision. La camara de la ventana `AirTraffic` si se mueve, pero el actor etiquetado queda fijo, por eso los pelotones sincronizados contra `BP_AirplaneMarker` no entraban en camara.
- La correccion activa sincroniza `APelotonSplineActor` contra `PlayerCameraManager` en game world (`bSyncToPlayerCamera=true`) y deja `BP_AirplaneMarker` solo como fallback de editor.

Siguiente validacion obligatoria antes de generar figuras finales:

```powershell
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\canonicalize_peloton_only.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\canonicalize_peloton_only_latest.log'; exit `$LASTEXITCODE"
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\apply_paper_all_obstacles_profile_and_save.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\apply_paper_all_obstacles_profile_latest.log'; exit `$LASTEXITCODE"
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\audit_paper_peloton_state.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\audit_paper_peloton_state.log'; exit `$LASTEXITCODE"
```
