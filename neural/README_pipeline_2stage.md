# Pipeline 2 etapas — Cesium → fotorrealista preservando geometría

Basado en `SOTA_RESEARCH_2026.md`. Dos etapas, todo open-source, pensado para 1× RTX 5090.

```
 input Cesium ──► [Etapa 0] extract_control (canny/depth)
                        │
                        ▼
                 [Etapa 1] VACE (Wan2.1-VACE)  ── estructura→materiales/luz fotorreales
                        │   (depth fija geometría 3D, canny fija líneas)
                        ▼
                 [Etapa 1.5] detail_transfer  ── bloquea color/iluminación a Cesium (Lab)
                        │
                        ▼
                 [Etapa 2] FlashVSR 4×  ── detalle/nitidez estructura-fiel
                        │   (fallback: SeedVR2)
                        ▼
                  vídeo final fotorrealista
```

## Puesta en marcha

1. **Setup (una vez):** en WSL, `bash neural/wsl_setup_pipeline.sh`
   Clona VideoX-Fun (VACE) + FlashVSR + Block-Sparse-Attention, crea venvs y descarga pesos
   (Wan2.1-VACE-1.3B y FlashVSR-v1.1). ~tens of GB de disco.
2. **Ejecutar:** `bash neural/run_pipeline.sh /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4`
   Hace etapa 0→1→1.5 automáticamente; la etapa 2 (FlashVSR) requiere apuntar su
   script de inferencia al vídeo de la etapa 1.5 (indicado al final del run).

## Componentes (todos ya escritos y los de cv2 verificados aquí)
- `extract_control.py` — canny/lineart/softedge (cv2, **verificado**). DEPTH: opcional con
  Depth-Anything-V2 (recomendado en aéreo; añade más fidelidad 3D que canny solo).
- `configure_wan_control.py` — reescribe los parámetros del `predict_v2v_control.py` REAL de
  VACE a nuestros valores (usa el código de upstream, no una copia). Soporta VACE y Fun-Control.
- `detail_transfer.py` — bloqueo de color/iluminación a Cesium en espacio Lab (**verificado**:
  Δab 0.03 vs original).
- `run_pipeline.sh` / `wsl_setup_pipeline.sh` — orquestación y setup.

## Decisiones y por qué (de la investigación)
- **Etapa 1 = VACE** (no StreamDiffusionV2): VACE condiciona por estructura (depth+canny),
  preserva geometría; SDV2 a ns alto alucina y deriva color (medido: Δab 12, align 0.015).
- **Etapa 2 = FlashVSR**: super-res que "mejora footage que YA tiene estructura" = nuestro caso.

## RIESGOS honestos (verifícalos en el 1er run; NO probado en GPU desde aquí)
1. **FlashVSR en la 5090 (Blackwell): compatibilidad DESCONOCIDA** según los autores
   (Block-Sparse-Attention validado solo en A100/A800/H200). Si no compila/corre:
   - usa un fork ComfyUI: `lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast` o `naxci1/ComfyUI-FlashVSR_Stable`,
   - o sustituye la etapa 2 por **SeedVR2-3B** (diffusion VSR, mejor para input "blando").
2. **VRAM:** VACE-1.3B va holgado; el 14B (mejor calidad) necesita
   `GPU_memory_mode=model_cpu_offload_and_qfloat8` o `sequential_cpu_offload` y es lento.
3. **Resolución:** VACE entrena a 480/720p; FlashVSR está optimizado para **4×**. Empieza a
   480² → 4× = 1920². Ajusta `sample_size` según VRAM.
4. **Depth:** por defecto uso canny (cv2, sin descargas). Para mejor fidelidad geométrica,
   genera el control con Depth-Anything-V2 y apunta `CONTROL` en run_pipeline.sh a ese mp4.
5. **torch/CUDA:** la 5090 es sm_120 → necesita torch cu128+. El setup lo intenta; si falla,
   instala torch manualmente en `~/vxf_venv` y `~/flashvsr_venv`.
6. **Sincronización mnt:** ficheros recién escritos pueden tardar en verse en el bash; en
   Windows están correctos.

## Siguiente mejora opcional
- Sustituir canny por **depth (Depth-Anything-V2)** en etapa 0.
- Si sale RealMaster (arXiv 2603.23462) con pesos: es el método dedicado sim→real; reemplazaría
  la etapa 1 entera.
