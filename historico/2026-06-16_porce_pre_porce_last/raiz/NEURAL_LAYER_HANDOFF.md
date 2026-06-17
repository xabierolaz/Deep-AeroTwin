# Capa de visualización neural (sim→fotorrealista) — Handoff para continuar

**Fecha:** 2026-06-13 · **Proyecto:** Deep-AeroTwin-UE57-Test
**Objetivo:** capa SOBRE Unreal (independiente del lazo de percepción) que coge el frame de la
ventana de Unreal y lo convierte en imagen fotorrealista en tiempo real, preservando geometría.
**Decisión del usuario:** SOLO visualización. El dron sigue viendo el frame CRUDO de Unreal para
detectar (YOLO intacto). Esta capa no toca `vision_system.py` ni el pipeline. FPS no bloqueante.

---

## ESTADO ACTUAL (qué funciona ya)

### Toolchain (verificado en la RTX 5090) — HECHO
- GPU: RTX 5090, 32 GB, driver 596.36, **sm_120 (Blackwell)**.
- El venv del proyecto (`D:\Deep-AeroTwin-UE57-Test\venv`) tiene torch CPU-only → NO tocar (ahí corre YOLO).
- **WSL2 (Ubuntu)** es el entorno de la capa neural: passthrough de la 5090 OK, CUDA 12.8 instalado.
- venv neural en WSL: `~/sdv2_venv` (torch 2.11.0+cu128, arch incluye sm_120, matmul OK).

### StreamDiffusionV2 (el modelo SOTA elegido) — INSTALADO Y PROBADO
- Repo clonado: `D:\Deep-AeroTwin-UE57-Test\neural\StreamDiffusionV2` (MLSys 2026 Best Paper, arxiv 2511.07399).
- Es video2video streaming, training-free, base Wan2.1-T2V-1.3B. Preserva estructura/movimiento, cambia estilo por prompt.
- Modelos descargados en `D:\Deep-AeroTwin-UE57-Test\neural\`:
  - `wan_models/Wan2.1-T2V-1.3B/` (17 GB: DiT, T5 umt5-xxl, VAE, tokenizer)
  - `ckpts/wan_causal_dmd_v2v/model.pt` (5.3 GB, checkpoint causal v2v)
- Deps instaladas con `--no-deps` + versiones py3.12-compatibles (numpy2, transformers 4.54, diffusers 0.35.1).
  flash_attn NO instalado → usa fallback `scaled_dot_product_attention` (funciona, más lento).

### Rendimiento medido (sin flash_attn ni TensorRT, arranque frío)
- 480×832, 81 frames: DiT 22.6 fps, end-to-end 8.3 fps.
- **480×480 (nuestra res cuadrada): DiT 28.8 fps, end-to-end 12.8 fps, estado estable ~17-18 fps.**
- Palancas sin usar para subir FPS: `--use_taehv` (VAE ligero), `--use_tensorrt`, `--fast`, flash_attn.

### Resultados visuales (en `D:\Deep-AeroTwin-UE57-Test\tmp\`)
- `poc_before_after.png` — POC cat→dog (prueba de que preserva geometría).
- `ejea_before_after.png`, `ejea_side_by_side.mp4`, `ejea_restyled.mp4` — Ejea restyle ns0.8: fotorrealismo bueno, **pero borra ciclistas/torres** (objetos finos se funden).
- `ejea_restyled_ns05.mp4` — ns0.5: objetos sobreviven parcialmente, menos realismo.
- `peloton_3way.png` — comparativa input / ns0.8 / ns0.5 (muestra el compromiso).
- `objects_check.png` — confirma que a ns0.8 el peloton desaparece.
- `ejea_detaware.mp4` (1.8 MB) — **modo detección-consciente**: fondo fotorrealista ns0.8 + objetos REALES (del frame original) pegados en las bbox exactas de YOLO. GENERADO OK.
  - El PNG comparativo `ejea_detaware_still.png` se quedó a medias por disco lleno → REGENERAR.

---

## HALLAZGO CLAVE (lo que pidió el usuario resolver)
A `noise_scale` alto el restyle borra objetos pequeños (ciclistas a 40 m ≈ pocos px, torres finas).
Tres formas de conservarlos:
1. Bajar `noise_scale` (0.8→0.5): preserva más, menos realismo. (probado, funciona a medias)
2. **Detección-consciente (lo que el usuario quiere): usar bbox+clase de YOLO** para que el objeto
   aparezca bien donde sabemos que está. Dos sabores:
   - (a) Composite con objeto REAL del frame original en la bbox (determinista, fiel) — YA HECHO en `ejea_detaware.mp4`.
   - (b) Inpaint generativo regional con prompt por clase ("torre de alta tensión", "vaca", "ciclista")
     → "genera bien una torre donde hay una torre". Es lo que el usuario pidió textualmente. PENDIENTE
     (requiere modelo de inpaint o ControlNet; más trabajo).
3. ControlNet depth/canny: candado estructural fuerte. PENDIENTE (lo más SOTA, más laborioso).

---

## PENDIENTE (orden sugerido al reanudar)

1. **[HECHO 2026-06-13 07:48]** `tmp\ejea_detaware_still.png` regenerado con cv2
   (frame 60, peloton de 15 cajas). INPUT | ns0.8(sin objetos) | detec-consciente | +bboxes.

2. **[CÓDIGO ENTREGADO, sin probar en GPU 2026-06-13]** Visor en vivo con slider de noise_scale.
   - Servidor: `neural\live_server.py` (FastAPI, un proceso, modelo caliente; slider EN VIVO
     mutando `session.init_noise_scale`). Wrapper: `tmp\run_live_server.cmd`.
   - Cliente: `neural\live_viewer.py` (PrintWindow + trackbar + side-by-side). Wrapper: `tmp\run_live_viewer.cmd`.
   - Guía: `neural\README_live_viewer.md`. Construido contra la API real verificada; FALTA correr en la 5090.
   - Modo prueba sin Unreal: `live_viewer.py --video tmp\ejea_clip_input.mp4`.
   (Plan original abajo, por si hay que depurar:)
   Arquitectura acordada:
   - **Server en WSL** (`~/sdv2_venv`): carga StreamDiffusionV2 en modo STREAMING (API `chunk_video`/`encode_chunk`/`denoise_chunk`,
     ver "Usage Example" del README del repo, o `streamv2v/api.py`). Mantener modelo caliente. Exponer en localhost
     (FastAPI/uvicorn, p.ej. 127.0.0.1:9500): endpoint que recibe frame JPEG + params (noise_scale, prompt) y devuelve frame restyled.
     WSL2 reenvía localhost ↔ Windows automáticamente.
   - **Cliente en Windows** (`venv\Scripts\python.exe`, tiene cv2): captura la ventana de Unreal con PrintWindow
     (código probado en `pipeline\vision_system.py` método `_printwindow_grab`, o `tmp\printwindow_probe.py`),
     envía frames al server, muestra ventana OpenCV con TRACKBAR de noise_scale (0-100→0.0-1.0) y side-by-side input/output.
     Prompt por defecto del campo + cambio por tecla opcional.
   - Recomendado: visor ligero a medida (OpenCV trackbar), NO el demo web (evita Node).

3. **Inpaint generativo por detección** (sabor 2b) si el usuario quiere objetos "bien generados" y no solo los reales pegados.

4. **Aceleración** (si se quieren más FPS): flash_attn + `--use_taehv` + `--use_tensorrt`.

---

## CÓMO EJECUTAR COSAS (notas operativas críticas)
- **PowerShell del MCP rompe pipes/redirects con `&` y `2>&1 |`**. Solución: meter todo en un `.cmd` en `tmp\`
  y lanzarlo con `Start-Process cmd /c ...`, redirigiendo a fichero, y leer el fichero con la herramienta Read.
- **WSL**: invocar `C:\Windows\System32\wsl.exe -e bash -lc "..."`. Para jobs largos NO usar nohup&
  (WSL mata el proceso al cerrar la sesión); lanzarlos SÍNCRONOS dentro de un `.cmd` con `Start-Process cmd` (el cmd mantiene WSL vivo).
- **Scripts .sh creados en Windows llevan CRLF** → `sed -i 's/\r$//' fichero.sh` antes de ejecutarlos en WSL.
- **`run_v2v.sh` PREFIJA ROOT_DIR a todas las rutas** → pasar VIDEO_PATH/PROMPT_FILE_PATH/OUTPUT_FOLDER RELATIVOS al repo
  (copiar inputs dentro del repo). OUTPUT_FOLDER relativo (p.ej. `poc_ejea/`).
- Rutas: el código de Wan busca `wan_models/` junto al repo → hay symlinks `neural/StreamDiffusionV2/wan_models -> ../wan_models` y `ckpts -> ../ckpts`.
- El mount WSL `/mnt/d/...` tiene LAG de sincronización con el bash del sandbox → leer ficheros recién escritos vía windows-mcp o la herramienta Read.

### Scripts ya listos en `D:\Deep-AeroTwin-UE57-Test\neural\` (y wrappers en `tmp\`)
- `wsl_setup_sdv2.sh` — crea venv + instala torch 2.11 cu128.
- `wsl_install_deps.sh` — instala el paquete + deps compatibles.
- `wsl_download_models.sh` — descarga Wan + ckpt.
- `wsl_run_poc.sh` / `wsl_run_ejea.sh` / `wsl_run_ejea_ns.sh` — runs offline (lanzar con `tmp\run_*.cmd`).
- `torch_probe.py` — verifica CUDA/sm_120.
- `tmp\detaware_composite.py`, `tmp\extract_bboxes.py`, `tmp\compare3.py` — análisis detección-consciente.

---

## AVISOS
- **Disco D: estuvo al 100%** (4 TB, datos del usuario). El usuario liberó espacio el 2026-06-13.
  Vigilar; los modelos neurales ocupan 22 GB en `D:\...\neural\`. Si hace falta, moverlos a C: (tenía 113 GB libres).
- NO tocar `Unreal\Content\Ejea.umap` original. El mapa de auditoría con peloton es `/Game/Ejea_AuditD1`.
- El paper (otra línea de trabajo) ya está terminado y comiteado: `paper\...\main.pdf` (23 págs). Commits locales
  0006664, 31ae3de, 43cbd23, abf991d. La capa neural NO está comiteada todavía (está en `neural/` y `tmp/`).
- Watchdog `aerotwin-overnight-watchdog` (scheduled, cada 15 min) sigue activo pero ya no tiene trabajo (solo vigila zombis).

## RESUMEN DE 1 LÍNEA PARA RETOMAR
"Capa de realismo StreamDiffusionV2 en WSL2 sobre la 5090 ya funciona (offline, ~13-18 fps a 480²); falta
regenerar el PNG del modo detección-consciente y construir el visor en vivo con slider de noise_scale."
