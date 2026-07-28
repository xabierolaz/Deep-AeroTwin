# KIMI/CLAUDE - Guía Completa Pipeline B Unreal MCP

**Fecha**: 2026-07-27  
**Proyecto**: Deep-AeroTwin-UE57-Test - Pipeline B Digital Twin  
**Objetivo**: Sincronización video-Unreal + detección YOLO + spawn de torres

---

## 🎯 ESTADO ACTUAL DEL PROYECTO

### Nivel Unreal
- **Nivel activo**: `/Game/Pipeline_B` (NO usar `/Game/Ejea` que es Pipeline A)
- **Secuencia**: `/Game/Sequences/LS_VideoFinal_Twin_v2` (239 keys @10fps + hold 5s)
- **Cámara**: `Cam_VideoFinal_Twin` (CineCameraActor, filmback 24×18 = 4:3)

### Video de Referencia
- **Archivo**: `papers/pipeline_b_telemetry/data/video_final.mp4`
- **Formato**: 1280×960 @10fps, 239 frames, 23.9s
- **Frame 0**: Vista aérea campos, carretera arriba-derecha
- **Frame final**: Vista campos con torre eléctrica abajo-derecha

### Datos de Vuelo
- **6DOF**: `papers/pipeline_b_telemetry/_archivo/datos_intermedios/video_final_6dof.json`
- **GPS**: `papers/pipeline_b_telemetry/data/video_final_gps.csv`
- **Poses manuales validadas**:
  - Frame 0: UE loc(7808, -2580, 7194), rot(pitch:-77.2, yaw:-66.6, roll:-6.4)
  - Frame final: UE loc(3486, -20829, 4940), rot(pitch:-34.2, yaw:-59.8, roll:-6.4)

### Torres de Referencia (marcadas por usuario)
- **tower1_loc.aprox**: UE loc(9440, -9920, 510), lat=42.143355, lon=-1.587694, alt≈308.81m
- **tower2_loc.aprox**: Ubicación en Unreal (coordenadas geográficas pendientes)

---

## 🔌 COMUNICACIÓN MCP CON UNREAL

### Configuración
- **Puerto**: 3000 (Streamable HTTP)
- **URL**: `http://127.0.0.1:3000/mcp`
- **Config**: `.mcp.json` en raíz del proyecto
- **Cliente**: `papers/pipeline_b_telemetry/experimental_support/scripts/mcp_unreal.py`

### Verificar que MCP está disponible
```python
from mcp_unreal import list_tools
tools = list_tools()
print(f'Tools disponibles: {len(tools)}')  # Debería mostrar 22 tools
```

### Tools MCP Disponibles (22 total)
Los más importantes:
- **`system_control`**: Ejecutar código Python en Unreal
- **`control_editor`**: Play/Stop, screenshots, console commands
- **`manage_sequence`**: Control de Level Sequences

### Ejecutar código Python en Unreal
```python
from mcp_unreal import call

code = '''
import unreal
import json

out = {}
# Tu código aquí
out["result"] = "OK"

print("JSONOUT:" + json.dumps(out, default=str))
'''

result = call('system_control', {'action': 'execute_python', 'code': code})
```

### Parsear resultado MCP
```python
def parse_mcp_result(result):
    """Extrae el JSON de la respuesta MCP."""
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list) and len(content) > 0:
            text = content[0].get("text", "")
            
            if '"output":"JSONOUT:' in text:
                start_marker = '"output":"JSONOUT:'
                start_idx = text.find(start_marker) + len(start_marker)
                
                end_marker = '", "error"'
                end_idx = text.find(end_marker, start_idx)
                
                if end_idx == -1:
                    end_marker = ',"error"'
                    end_idx = text.find(end_marker, start_idx)
                
                if end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    json_str = json_str.replace('\\"', '"')
                    
                    # Limpiar caracteres extra al final
                    brace_count = 0
                    last_valid_idx = -1
                    for i, char in enumerate(json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                last_valid_idx = i
                                break
                    
                    if last_valid_idx > 0:
                        json_str = json_str[:last_valid_idx + 1]
                    
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
    
    return result
```

---

## 📜 SCRIPTS ÚTILES CREADOS

### 1. Diagnóstico completo
**Archivo**: `papers/pipeline_b_telemetry/experimental_support/scripts/sync_video_unreal.py`

**Uso**:
```bash
cd papers/pipeline_b_telemetry/experimental_support/scripts
python sync_video_unreal.py
```

**Qué hace**:
- Busca torres de referencia en el nivel
- Obtiene poses de cámara de la secuencia (frame 0 y final)
- Calcula proyección de torres en pantalla
- Valida sincronización

### 2. Buscar torres en el nivel
```python
def find_towers_in_level():
    code = '''
import unreal
import json

out = {"towers": []}

world = unreal.EditorLevelLibrary.get_editor_world()
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor)

for actor in actors:
    label = actor.get_actor_label()
    if "tower" in label.lower() and "loc" in label.lower():
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        tower_data = {
            "name": actor.get_name(),
            "label": label,
            "location": {"x": loc.x, "y": loc.y, "z": loc.z},
            "rotation": {"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll}
        }
        out["towers"].append(tower_data)

out["count"] = len(out["towers"])
print("JSONOUT:" + json.dumps(out, default=str))
'''
    
    result = call('system_control', {'action': 'execute_python', 'code': code})
    return parse_mcp_result(result)
```

### 3. Obtener pose de cámara en un frame
```python
def get_camera_pose_at_frame(frame_num):
    code = f'''
import unreal
import json

out = {{}}

seq = unreal.load_asset("/Game/Sequences/LS_VideoFinal_Twin_v2")

# Buscar binding de cámara
cam_binding = None
for b in seq.get_bindings():
    if "Cam_VideoFinal_Twin" in str(b.get_name()):
        cam_binding = b
        break

if cam_binding:
    for track in cam_binding.get_tracks():
        if isinstance(track, unreal.MovieScene3DTransformTrack):
            secs = track.get_sections()
            if secs:
                sec = secs[0]
                chans = sec.get_all_channels()
                
                # Canales: 0-2=Loc XYZ, 3=Roll, 4=Pitch, 5=Yaw, 6-8=Scale
                def get_value_at_frame(channel, target_frame):
                    keys = channel.get_keys()
                    if not keys:
                        return 0.0
                    
                    closest_key = None
                    min_diff = float('inf')
                    
                    for key in keys:
                        key_frame = key.get_time().frame_number.value
                        diff = abs(key_frame - target_frame)
                        if diff < min_diff:
                            min_diff = diff
                            closest_key = key
                    
                    if closest_key:
                        try:
                            return closest_key.get_value()
                        except:
                            return 0.0
                    return 0.0
                
                loc_x = get_value_at_frame(chans[0], {frame_num})
                loc_y = get_value_at_frame(chans[1], {frame_num})
                loc_z = get_value_at_frame(chans[2], {frame_num})
                roll = get_value_at_frame(chans[3], {frame_num})
                pitch = get_value_at_frame(chans[4], {frame_num})
                yaw = get_value_at_frame(chans[5], {frame_num})
                
                out["frame"] = {frame_num}
                out["location"] = {{"x": loc_x, "y": loc_y, "z": loc_z}}
                out["rotation"] = {{"roll": roll, "pitch": pitch, "yaw": yaw}}
            break

print("JSONOUT:" + json.dumps(out, default=str))
'''
    
    result = call('system_control', {'action': 'execute_python', 'code': code})
    return parse_mcp_result(result)
```

### 4. Capturar screenshot
```python
def take_screenshot(filename):
    result = call('control_editor', {
        'action': 'take_screenshot',
        'filename': filename
    })
    return result

# Las screenshots se guardan en: Unreal/Saved/Screenshots/
```

---

## 🔧 CONVERSIONES Y FÓRMULAS CLAVE

### Coordenadas GPS → Unreal
```python
# Sumar geoid N a alturas GPS antes de pasar a Unreal
geoid_N = 50.37  # metros
alt_ellipsoid = alt_gps_msl + geoid_N

# Convertir LLH → UE
ue_loc = cesium_georeference.transform_longitude_latitude_height_to_unreal(
    unreal.Vector(lon, lat, alt_ellipsoid)
)
```

### Actitud ArduPilot → UE Rotator
```python
# ATT del log de ArduPilot → Rotator de Unreal
pitch_ue = att_pitch - 70  # tilt de montaje
yaw_ue = att_yaw - 90
roll_ue = att_roll

# IMPORTANTE: unreal.Rotator(a,b,c) posicional = (roll, pitch, yaw)
# Usar siempre kwargs: unreal.Rotator(pitch=p, yaw=y, roll=r)
```

### Canales de Transform Track en Secuencia
```python
# get_all_channels() devuelve:
# 0-2: Location XYZ
# 3: Rotation.X = ROLL
# 4: Rotation.Y = PITCH
# 5: Rotation.Z = YAW
# 6-8: Scale XYZ

# BUG COMÚN: Escribir pitch/yaw/roll en X/Y/Z causa vistas al cielo
```

### Proyección de punto 3D a pixel 2D
```python
def project_3d_to_2d(cam_loc, cam_rot, point_3d, focal_mm=16.0, 
                     sensor_w_mm=24.0, sensor_h_mm=18.0,
                     img_w_px=1280, img_h_px=960):
    """
    Proyecta un punto 3D de Unreal a coordenadas de pixel.
    
    Returns:
        (pixel_x, pixel_y, visible, distance)
    """
    import math
    
    # Vector cámara → punto
    dx = point_3d["x"] - cam_loc["x"]
    dy = point_3d["y"] - cam_loc["y"]
    dz = point_3d["z"] - cam_loc["z"]
    
    distance = math.sqrt(dx*dx + dy*dy + dz*dz)
    
    # Rotaciones a radianes
    roll_rad = math.radians(cam_rot["roll"])
    pitch_rad = math.radians(cam_rot["pitch"])
    yaw_rad = math.radians(cam_rot["yaw"])
    
    # Aplicar rotaciones (orden: yaw, pitch, roll)
    cos_yaw, sin_yaw = math.cos(yaw_rad), math.sin(yaw_rad)
    x1 = dx * cos_yaw - dy * sin_yaw
    y1 = dx * sin_yaw + dy * cos_yaw
    z1 = dz
    
    cos_pitch, sin_pitch = math.cos(pitch_rad), math.sin(pitch_rad)
    x2 = x1
    y2 = y1 * cos_pitch - z1 * sin_pitch
    z2 = y1 * sin_pitch + z1 * cos_pitch
    
    cos_roll, sin_roll = math.cos(roll_rad), math.sin(roll_rad)
    x3 = x2 * cos_roll + z2 * sin_roll
    y3 = y2
    z3 = -x2 * sin_roll + z2 * cos_roll
    
    # Espacio de cámara: X=derecha, Y=adelante, Z=arriba
    cam_x = x3
    cam_y = z3
    cam_z = y3
    
    # Verificar si está delante
    if cam_z <= 0:
        return None, None, False, distance
    
    # Proyección perspectiva
    focal_px_x = (focal_mm / sensor_w_mm) * img_w_px
    focal_px_y = (focal_mm / sensor_h_mm) * img_h_px
    
    center_x = img_w_px / 2.0
    center_y = img_h_px / 2.0
    
    pixel_x = center_x + (cam_x / cam_z) * focal_px_x
    pixel_y = center_y - (cam_y / cam_z) * focal_px_y
    
    visible = (0 <= pixel_x < img_w_px) and (0 <= pixel_y < img_h_px)
    
    return pixel_x, pixel_y, visible, distance
```

---

## 🎬 ESTRUCTURA DE LA SECUENCIA

### LS_VideoFinal_Twin_v2
- **Total frames**: 288 (239 reales + 50 de hold al inicio)
- **Hold**: Frames 0-50 estáticos en pose de frame 0 (5s para que Cesium cargue)
- **Vuelo real**: Frames 50-288 (239 frames @10fps = 23.9s)
- **Fórmula híbrida**: 
  ```
  pose(i) = lerp(manual0, manualFinal, w) + (log(i) - lerp(log0, log238, w))
  ```

### Camera Cut Track
- Extendido hasta frame 288 (fix aplicado con `fix_cut_and_cleanup.py`)
- Sin esto, los últimos 5s se veía el pawn en origen

---

## 🐛 PROBLEMAS CONOCIDOS Y SOLUCIONES

### 1. "Cielo al dar Play"
**Causa**: Latencia de streaming de Cesium al arrancar PIE  
**Solución**: 
- Hold de 5s en frames 0-50
- Tileset configurado: `forbid_holes=true`, `maximum_simultaneous_tile_loads=40`
- Warmup de caché con `warmup_fly.py`

### 2. Frame 0 demasiado cerca
**Causa**: Pose inicial no coincide con video  
**Solución**: 
- Usar pose manual validada (`twin_frame0_pose.json`)
- Ajuste interactivo: Play → F8 → volar → capturar nueva pose

### 3. Tiles no cargan en viewport del EDITOR
**Causa**: "cesium.com not connected", preview azul/negro  
**Solución**: En PIE sí cargan. Hacer ajustes en PIE con F8, no en editor.

### 4. Editor viewport se congela
**Causa**: "Use Less CPU when in Background"  
**Solución**: `use_less_cpu_when_in_background=False` en `EditorPerProjectUserSettings.ini`

### 5. MCP se desenruta
**Causa**: Llamadas salen como Playwright  
**Solución**: Reiniciar sesión de chat/VSCode

---

## 📂 ARCHIVOS IMPORTANTES

### Scripts Python (fuera de Unreal)
- `papers/pipeline_b_telemetry/experimental_support/scripts/mcp_unreal.py` - Cliente MCP
- `papers/pipeline_b_telemetry/experimental_support/scripts/sync_video_unreal.py` - Diagnóstico completo
- `papers/pipeline_b_telemetry/experimental_support/scripts/capture_validation_frames.py` - Capturas

### Scripts Python (dentro de Unreal, commandlet)
- `Unreal/Scripts/inspect_ls_videofinal_v2.py` - Inspeccionar secuencia
- `Unreal/Scripts/fix_cut_and_cleanup.py` - Fix camera cut + limpieza

### Datos
- `papers/pipeline_b_telemetry/data/video_final.mp4` - Video de referencia
- `papers/pipeline_b_telemetry/data/video_final.json` - Sync AUTORITATIVO (offset +12.9s)
- `papers/pipeline_b_telemetry/_archivo/datos_intermedios/video_final_6dof.json` - 6DOF por frame
- `papers/pipeline_b_telemetry/_archivo/datos_intermedios/twin_frame0_pose.json` - Pose manual frame 0
- `papers/pipeline_b_telemetry/_archivo/datos_intermedios/twin_frame_final_pose.json` - Pose manual frame final

### Assets Unreal
- `/Game/Pipeline_B` - Nivel del gemelo
- `/Game/Sequences/LS_VideoFinal_Twin_v2` - Secuencia de vuelo
- `/Game/M_tower.uasset` - Material de torre
- `/Game/tower_mesh.uasset` - Mesh de torre

---

## 🚀 WORKFLOW TÍPICO

### 1. Lanzar Unreal con el proyecto
```powershell
& "D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe" "D:\Deep-AeroTwin-UE57-Test\Unreal\AirTraffic.uproject"
```

### 2. Esperar a que MCP esté disponible (~30s)
```python
from mcp_unreal import list_tools
tools = list_tools()  # Debería devolver 22 tools
```

### 3. Ejecutar diagnóstico
```bash
cd papers/pipeline_b_telemetry/experimental_support/scripts
python sync_video_unreal.py
```

### 4. Capturar screenshots para validación
```python
from mcp_unreal import call
result = call('control_editor', {'action': 'take_screenshot', 'filename': 'test.png'})
# Se guarda en: Unreal/Saved/Screenshots/
```

---

## 📝 NOTAS IMPORTANTES

1. **SIEMPRE usar el nivel `/Game/Pipeline_B`**, NO `/Game/Ejea` (que es Pipeline A)
2. **La secuencia correcta es `LS_VideoFinal_Twin_v2`**, las demás son residuales
3. **El hold de 5s es CRÍTICO** para que Cesium cargue antes del vuelo
4. **Las poses manuales del usuario son AUTORITATIVAS**, no las del log
5. **Sumar geoid N=+50.37m** a todas las alturas GPS antes de pasar a Unreal
6. **Canales de rotación**: X=roll, Y=pitch, Z=yaw (NO pitch/yaw/roll)
7. **unreal.Rotator() posicional** = (roll, pitch, yaw), usar kwargs siempre
8. **El video_final_sync.json es INCORRECTO** (+15.985s), usar video_final.json (+12.9s)

---

## 🎯 PRÓXIMOS PASOS

1. ✅ Verificar que torres de referencia están en el nivel
2. ✅ Validar sincronización visual (capturas vs video)
3. ⚠️ **PROBLEMA IDENTIFICADO**: Pitch de cámara demasiado negativo (-77° en frame 0)
   - Video muestra vista aérea con horizonte visible (pitch ~-45° a -60°)
   - Unreal tiene pitch casi vertical (-77°), vista muy cerrada sin horizonte
   - **Solución**: Ajustar pitch inicial a ~-50° y regenerar secuencia
4. ⏳ Ajustar pose inicial si es necesario
5. ⏳ Implementar pipeline YOLO para detección de torre
6. ⏳ Triangulación YOLO→3D usando torres de referencia
7. ⏳ Spawn de torre detectada en Unreal

---

## 🔍 DIAGNÓSTICO COMPLETADO (2026-07-27)

### Estado de la secuencia
- ✅ Secuencia `LS_VideoFinal_Twin_v2` tiene 240 keyframes (239 + hold)
- ✅ Poses coinciden con datos manuales validados
- ✅ Interpolación suave, sin cambios bruscos
- ✅ Torres de referencia encontradas: tower1 (9440, -9920, 510) y tower2 (6610, -23600, 250)

### Problema identificado y RESUELTO
- ❌ **Pitch demasiado negativo**: Frame 0 tiene pitch=-77.2° (casi vertical hacia abajo)
- ❌ **Vista muy cerrada**: No se ve horizonte ni carretera como en el video
- ❌ **Comparación con video**:
  - Video frame 0: Vista amplia, carretera arriba-derecha, horizonte visible
  - Unreal frame 0: Vista cenital cerrada, solo suelo, sin contexto
- ❌ **Yaw daba vuelta completa**: Interpolación lineal cruzaba 0°/360° causando rotación de 360°

### Causa raíz
1. La pose manual validada (`twin_frame0_pose.json`) tiene pitch=-77.2°, que es correcta para la posición GPS,
pero **no coincide con el encuadre del video**. El video fue grabado con una cámara menos inclinada.

2. **Problema de interpolación angular**: El yaw del log cruza el límite 0°/360° (ej: frame 0 yaw=9.6°, frame 7 yaw=358.8°).
La interpolación lineal simple hace +349° (vuelta completa) en lugar de -11° (camino corto).

### Solución APLICADA (2026-07-27 14:30)

**1. Nueva pose inicial capturada del usuario:**
- **Ubicación**: (10571.53, -4176.89, 5409.50)
- **Rotación**: pitch=-39.81°, yaw=-54.99°, roll=-7.07°
- **Focal**: 16mm, HFOV=73.74°, VFOV=58.72°
- **Sensor**: 24×18mm (4:3)

**2. Corrección de interpolación angular:**
```python
def lerp_angle(a, b, t):
    """Interpolación de ángulos que toma el camino corto."""
    a = a % 360
    b = b % 360
    diff = b - a
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    result = a + diff * t
    return result % 360
```

**Cambios respecto a la pose anterior:**
- Pitch: -77.2° → **-39.8°** (37° menos inclinado)
- Yaw: -66.6° → **-55.0°** (11° de ajuste)
- Altura: 7194.6 → **5409.5** (más bajo, mejor perspectiva)

**Resultado visual:**
- ✅ Se ve la carretera claramente (arriba, cruzando horizontalmente)
- ✅ Se ve el horizonte (no es vista cenital cerrada)
- ✅ Contexto amplio: campos verdes, campos blancos, carretera
- ✅ Incluso se ve una torre eléctrica (abajo-izquierda)
- ✅ Perspectiva aérea natural
- ✅ **Sin vuelta completa de yaw** (interpolación angular corregida)

**Archivos actualizados:**
- `_archivo/datos_intermedios/twin_frame0_pose_user_adjusted.json` - Nueva pose inicial
- `experimental_support/scripts/regenerate_sequence.py` - Con lerp_angle() para yaw
- Secuencia `LS_VideoFinal_Twin_v2` regenerada con 289 keyframes

**Próximo paso**: Validar sincronización completa y proceder con pipeline YOLO

---

**Última actualización**: 2026-07-27 13:45  
**Autor**: Kimi Code CLI  
**Estado**: En progreso - Fase de diagnóstico y sincronización
