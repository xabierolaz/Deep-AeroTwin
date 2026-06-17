# SOTA jun-2026 — Cesium/sim → fotorrealista preservando geometría (vídeo)

Investigación multi-fuente para: **preservar fidelidad de geometría + coherencia
temporal en vídeo + añadir realismo/detalle**, open-source, 1× RTX 5090 (32 GB).

## Reencuadre del problema (importante)
El frame de Cesium/Unreal **ya tiene** geometría, color e iluminación correctos;
solo le falta **textura y detalle**. Eso lo acerca más a **realce/super-resolución
estructura-fiel** que a "restyle". Hay dos sub-objetivos distintos y el mejor modelo
depende de cuál priorices:

- **A) Transformar materiales/iluminación a fotorrealismo** (que deje de parecer CGI):
  generación condicionada por estructura (depth+canny).
- **B) Añadir detalle/nitidez manteniéndolo todo**: super-resolución estructura-fiel.

## Hallazgos (rankeados) — con evidencia

### 1. RealMaster — el método HECHO para esto (pero sin pesos)
"Lifting Rendered Scenes into Photorealistic Video" (arXiv 2603.23462, mar-2026).
Convierte vídeo renderizado en fotorrealista **manteniendo alineación total con el
motor 3D**: preserva geometría, dinámica e identidad vía *geometric conditioning* +
IC-LoRA; evaluado en secuencias de GTA-V, supera a baselines de edición de vídeo.
**Estado: NO he encontrado código ni pesos abiertos** (solo paper + project page).
→ El ideal académico para nuestro caso, pero **no usable hoy**. Vigilar release.

### 2. VACE (Wan2.1-14B / Wan2.2) — control de estructura, maduro y abierto  ⟵ recomendado A
All-in-one video edit (código+pesos, may-2025). Soporta pasos ControlNet **Depth,
Canny, Pose, MLSD, trayectoria**. Variantes 1.3B y 14B (480/720p). Apache-2.0.
- VRAM: 14B ≈ 28 GB de pesos, >20 GB en generación → **ajustado pero viable en 32 GB**;
  el 1.3B va holgado; hay FP8 y `Wan2GP` ("GPU poor") para bajar VRAM.
- Preserva coherencia espacial e identidad; maduro en ComfyUI. **depth** fija la
  geometría 3D, **canny** fija las líneas/detalle → combinándolos respeta la geometría.

### 3. Wan2.2 Fun Control — misma familia, más ligero  ⟵ fallback A
Canny/Depth/Tile/Pose vía VideoX-Fun. FP8 low-VRAM para consumer GPU. Es la vía que
ya dejé montada (extract_control.py + configure_wan_control.py). Algo menos capaz que
VACE pero más sencillo de encajar en tu 5090.

### 4. FlashVSR — super-resolución estructura-fiel en streaming  ⟵ recomendado B
Alibaba, CVPR 2026, Apache-2.0, pesos en HF (v1/v1.1). One-step **streaming** VSR,
~17 fps a 768×1408 en **A100**; "**enhances footage that already has real structure**"
= exactamente nuestro caso; preserva estructuras finas, evita aliasing. 4× SR.
- **RIESGO real:** su backend Block-Sparse-Attention está probado en A100/A800/H200;
  los autores dicen literalmente que la **compatibilidad/rendimiento en RTX 40/50
  (Blackwell) es DESCONOCIDA**. Hay forks ComfyUI (algunos sin LCSA → pierden calidad).
  → Hay que probarlo en la 5090; puede requerir el fork comunitario o el modo "tiny".

### 5. SeedVR2 — VSR diffusion, mejor para entrada "blanda"  ⟵ fallback B / 2ª etapa
ByteDance, 3B pesos abiertos. One-step diffusion VSR; brilla **reconstruyendo detalle
en input AI-generado/comprimido/borroso**. 24+ GB VRAM. Ideal como **2ª etapa tras una
generación** (limpia y nitidez), menos como primer paso sobre footage ya nítido.

### Otros (contexto)
- **Sim2real dedicado:** REGEN (real-time game→photoreal, dual-stage; research), TRITON
  (neural textures, usa geometría 3D, temporalmente consistente; 2022, requiere integrar
  rendering diferenciable). Académicos, no plug-and-play.
- **Tiempo real causal:** CausVid (~10 fps 1 GPU), Self-Forcing, Rolling Forcing,
  Causal Forcing (ICML 2026), MotionStream — para el visor en vivo; control por depth
  posible (FastGen). Relevante si priorizas interactividad sobre máxima calidad.
- **Coherencia temporal (técnicas):** FlowMo, Synchronized Multi-Frame Diffusion
  (flujo óptico para compartir info entre frames).

## Recomendación

**Pipeline en dos etapas (mejor calidad, todo open, cabe en la 5090):**
1. **Estructura→fotorrealismo:** VACE (Wan2.2) o Wan2.2-Fun Control con **depth + canny**
   (depth = geometría 3D, canny = líneas). Bloqueo de color a Cesium con `detail_transfer`
   si hay deriva de color.
2. **Detalle/nitidez:** FlashVSR (si valida en la 5090) o SeedVR2.

**Si hay que elegir UNO:**
- Quieres que **deje de parecer CGI** (materiales/luz fotorreales) → **VACE depth+canny**.
- Quieres "**igual pero con más detalle/nitidez**" → **FlashVSR** (con el caveat 5090).

**No usar como primario ahora:** RealMaster (sin pesos), StreamDiffusionV2 ns alto
(aluciná y deriva el color, demostrado en nuestras pruebas: Δab 12 y align de gradiente 0.015).

## Fuentes
- RealMaster: https://arxiv.org/abs/2603.23462 · https://danacohen95.github.io/RealMaster/
- VACE: https://huggingface.co/Wan-AI/Wan2.1-VACE-14B · https://github.com/Wan-Video/Wan2.1 · https://www.runcomfy.com/comfyui-workflows/vace-wan2-1-video-to-video-workflow
- Wan2.2 Fun Control: https://comfyui-wiki.com/en/tutorial/advanced/video/wan2.2/wan2-2-fun-control · https://huggingface.co/alibaba-pai/Wan2.2-Fun-A14B-Control
- FlashVSR: https://github.com/OpenImagingLab/FlashVSR · https://arxiv.org/abs/2510.12747 · https://huggingface.co/JunhaoZhuang/FlashVSR-v1.1
- SeedVR2 vs FlashVSR: https://upsampler.com/blog/seedvr-vs-flashvsr-ai-video-super-resolution-2026
- REGEN: https://www.researchgate.net/publication/400557942 · TRITON: https://arxiv.org/abs/2206.13500
- Tiempo real: https://causvid.github.io/ · https://github.com/thu-ml/Causal-Forcing · https://arxiv.org/html/2511.01266v5 (MotionStream)
- Wan2GP (low VRAM): https://github.com/Decentralised-AI/Wan2GP
