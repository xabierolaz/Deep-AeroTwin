# Perfiles de escena Unreal para el paper

Fecha de preparacion y prueba: 2026-06-17

Este documento define como preparar la escena `Ejea` de Unreal para cada experimento del paper, ocultando o mostrando los obstaculos que deben aparecer en camara y por tanto en YOLO.

## Archivos creados

- `Unreal/Scripts/paper_scenario_visibility.py`: logica que se ejecuta dentro de Unreal Editor.
- `tools/unreal_apply_paper_profile.py`: CLI externa que llama al MCP Automation Bridge y aplica los perfiles.
- `tools/unreal_execute_python.py`: CLI generica para ejecutar Python dentro del Unreal Editor abierto via MCP.

El canal usado es el MCP nativo documentado en `UNREAL_CONEXIONES_PYTHON_MCP.md`.

## Grupos detectados en la escena viva

Comprobado contra Unreal Editor abierto, mundo `Ejea`:

| Grupo | Criterio principal | Actores |
| --- | --- | ---: |
| `towers` | carpeta `towers`, labels `t0`, `tower14`, etc. | 42 |
| `cows` | carpeta `cows`, labels `cowanimateduntitled...` | 8 |
| `bikers` | carpeta `bikers`, clases/labels `ciclista...` | 10 |
| `peloton` | actor `Peloton_Ciclistas_EditableSpline` / `BP_PelotonSpline_C` | 1 |

Importante: torres y vacas estan principalmente como `StaticMeshActor`, no como instancias directas `bp_tower` o `bp_cow`. Por eso el control se hace por carpeta/label/clase, no solo por Blueprint.

## Perfiles disponibles

| Perfil | Uso | Visible | Oculto | Target YOLO recomendado |
| --- | --- | --- | --- | --- |
| `paper_static_tower` | Figura 1, obstaculo estatico | `towers` | `cows`, `bikers`, `peloton` | `tower` |
| `paper_wp1_wp2_tower` | Figura 1 activa, torre unica colocada en WP1->WP2 | solo `t0` | resto de torres, `cows`, `bikers`, `peloton` | `tower` |
| `paper_moving_peloton` | Figura 2, obstaculo en movimiento | `bikers`, `peloton` | `towers`, `cows` | `biker` |
| `paper_all_obstacles` | Reset/debug | todo | nada | `biker,cow,tower` |
| `paper_no_obstacles` | Control/debug sin obstaculos | nada | todo | vacio |
| `paper_static_cow` | Control extra | `cows` | `towers`, `bikers`, `peloton` | `cow` |

## Comandos

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
towers: 0 visibles, 42 ocultas
cows: 0 visibles, 8 ocultas
bikers: 10 visibles, 0 ocultos
peloton: 1 visible, 0 ocultos
```

Despues de las pruebas se restauro `paper_all_obstacles`:

```text
towers: 42 visibles
cows: 8 visibles
bikers: 10 visibles
peloton: 1 visible
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
- Figura 2 / peloton o ciclistas: `PORCE_VISION_TARGET_CLASS_NAMES=biker`.
- Debug completo: `PORCE_VISION_TARGET_CLASS_NAMES=biker,cow,tower`.

Ocultar un actor del Outliner no es suficiente si sigue renderizando en la camara. Estos perfiles actuan sobre visibilidad de actor y componentes para que YOLO no vea los grupos ocultos.
