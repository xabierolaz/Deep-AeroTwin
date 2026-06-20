# Handoff Unreal/YOLO Paper Figures

Fecha: 2026-06-18

Objetivo pendiente: terminar las figuras y el video final del paper usando ejecucion real Unreal + ArduPilot + Vision/YOLO, con pelotones de ciclistas controlados por script y sin vacas, ghosts, ciclistas sueltos ni materiales rojos.

## Estado actual

- Unreal fue detenido por el usuario. No hay nada que guardar desde la ventana runtime: los cambios persistentes se hacen por C++ y scripts commandlet.
- El pipeline PORCE fue parado con `tools\stop_pipeline.ps1`.
- El build C++ `AirTrafficEditor Win64 Development` paso correctamente despues de anadir sincronizacion a `APelotonSplineActor`.
- Queda pendiente regenerar el mapa con `canonicalize_peloton_only.py` despues del ultimo cambio `bSyncToPlayerCamera`.

## Diagnostico clave

El problema actual no es YOLO. En los runs reales los ciclistas no entraban de forma legible en la ventana `AirTraffic`.

Hallazgo confirmado por logs:

- `BP_AirplaneMarker` queda fijo durante runtime.
- La camara que Vision captura si se mueve.
- Los pelotones sincronizados contra `BP_AirplaneMarker` calculaban siempre la misma distancia firmada, por eso no cruzaban cuando el dron pasaba.
- Se cambio `APelotonSplineActor` para sincronizarse contra `PlayerCameraManager` en game world y usar `BP_AirplaneMarker` solo como fallback.

Log de referencia observado antes del fix:

```text
[PelotonSync] ... target=BP_AirplaneMarker signed_cm=... constante durante todo el vuelo
```

El siguiente run debe mostrar:

```text
[PelotonSync] ... target=PlayerCameraManager signed_cm=... cambiando con el vuelo
```

## Archivos principales tocados

- `Unreal/Source/AirTraffic/Public/PelotonSplineActor.h`
- `Unreal/Source/AirTraffic/Private/PelotonSplineActor.cpp`
- `Unreal/Scripts/canonicalize_peloton_only.py`
- `Unreal/Scripts/audit_paper_peloton_state.py`
- `Unreal/Scripts/apply_paper_moving_peloton_profile_and_save.py`
- `Unreal/Scripts/apply_paper_runtime_camera_profile.py`
- `pipeline/porce_defaults.env`
- `PAPER_UNREAL_SCENE_PROFILES.md`

## Checks ya conocidos

- `rtk venv\Scripts\python.exe -m compileall -q Unreal\Scripts figuras_paper_unreal_generadas pipeline tools` paso antes del ultimo handoff.
- `audit_paper_peloton_state.py` antes del ultimo cambio confirmaba:
  - 4 pelotones.
  - 0 loose bikers.
  - 0 ghost components.
  - materiales por slot no rojos.
  - rutas perpendiculares.
- Runs reales anteriores generaron MP4 y frames, pero los pelotones no fueron suficientemente visibles/detectables.

## Proximo bloque recomendado

1. Compilar si hay duda:

```powershell
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat' AirTrafficEditor Win64 Development -Project='D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -WaitMutex -FromMsBuild *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\build_airtraffic_editor_latest.log'; exit `$LASTEXITCODE"
```

2. Regenerar/guardar pelotones y auditar:

```powershell
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\canonicalize_peloton_only.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\canonicalize_peloton_only_latest.log'; exit `$LASTEXITCODE"
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\apply_paper_moving_peloton_profile_and_save.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\apply_paper_moving_peloton_profile_latest.log'; exit `$LASTEXITCODE"
rtk proxy powershell -NoProfile -Command "& 'D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject' -run=pythonscript -script='D:\Deep-AeroTwin-UE57-Test\Unreal\Scripts\audit_paper_peloton_state.py' -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput *> 'D:\Deep-AeroTwin-UE57-Test\pipeline\logs\audit_paper_peloton_state.log'; exit `$LASTEXITCODE"
```

3. Abrir Unreal real, lanzar pipeline con `launch.bat`, y verificar en `Unreal\Saved\Logs\AirTraffic.log` que `[PelotonSync]` usa `PlayerCameraManager`.

4. Solo si los ciclistas entran en camara y YOLO detecta, copiar frames/video a `figuras_paper_unreal_generadas/final_artifacts` y regenerar LaTeX con `generate_final_latex_figures.py`.

## Prompt sugerido para hilo nuevo

Continua desde `D:\Deep-AeroTwin-UE57-Test\HANDOFF_UNREAL_YOLO_PAPER_2026-06-18.md`. Objetivo: terminar las figuras y video finales del paper desde ejecucion real Unreal + ArduPilot + YOLO. Primero lee el handoff y `PAPER_UNREAL_SCENE_PROFILES.md`, confirma que el build con `APelotonSplineActor` pasa, rerun `canonicalize_peloton_only.py`, `apply_paper_moving_peloton_profile_and_save.py` y `audit_paper_peloton_state.py`, despues lanza Unreal y el pipeline. Verifica que `[PelotonSync]` use `PlayerCameraManager` y que los pelotones crucen en camara. No uses ghosts de ciclistas ni vacas; cualquier degradado/prediccion debe ser no detectable por YOLO o postprocesado.
