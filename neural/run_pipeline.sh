#!/bin/bash
# Pipeline 2 etapas: estructura->fotorrealismo (VACE) -> detalle (FlashVSR).
# Uso:  bash run_pipeline.sh <input_clip.mp4>
# Requisitos: haber corrido wsl_setup_pipeline.sh.
set -e
ROOT=/mnt/d/Deep-AeroTwin-UE57-Test
NEURAL=$ROOT/neural
INPUT="${1:-$ROOT/tmp/ejea_clip_input.mp4}"
PROMPT_FILE="$NEURAL/ejea_prompt.txt"
WORK=$ROOT/tmp/pipeline; mkdir -p "$WORK"
SIZE_H=480; SIZE_W=480; FRAMES=81; FPS=16

echo "=== ETAPA 0: extraer control (canny) desde el input ==="
# (para DEPTH: genera $WORK/control_depth.mp4 con Depth-Anything y cambia CONTROL abajo)
python3 "$NEURAL/extract_control.py" --video "$INPUT" \
  --out "$WORK/control_canny.mp4" --mode canny
CONTROL="$WORK/control_canny.mp4"

echo "=== ETAPA 1: VACE estructura->fotorrealismo ==="
cd "$NEURAL/VideoX-Fun"
source ~/vxf_venv/bin/activate
python3 "$NEURAL/configure_wan_control.py" \
  --src examples/wan2.1_vace/predict_v2v_control.py \
  --out examples/wan2.1_vace/predict_aerotwin.py \
  --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$CONTROL" \
  --prompt-file "$PROMPT_FILE" \
  --size $SIZE_H $SIZE_W --frames $FRAMES --fps $FPS \
  --steps 40 --guidance 5.0 --gpu-mode model_cpu_offload_and_qfloat8 \
  --save "$WORK/stage1_out"
python3 examples/wan2.1_vace/predict_aerotwin.py
STAGE1=$(ls -t "$WORK/stage1_out"/*.mp4 | head -1)
echo "stage1 -> $STAGE1"

echo "=== ETAPA 1.5: bloqueo de color a Cesium (opcional pero recomendado) ==="
# mantiene color/iluminación del original, conserva la textura nueva de VACE
python3 "$NEURAL/detail_transfer.py" --original "$INPUT" --gen "$STAGE1" \
  --output "$WORK/stage1_colorlocked.mp4" --detail-gain 1.0 --sigma 6 --color-mode lab || \
  cp "$STAGE1" "$WORK/stage1_colorlocked.mp4"

echo "=== ETAPA 2: FlashVSR super-resolución estructura-fiel (4x) ==="
cd "$NEURAL/FlashVSR/examples/WanVSR"
source ~/flashvsr_venv/bin/activate
# Los scripts de FlashVSR leen su input internamente; edita la ruta de entrada en
# infer_flashvsr_v1.1_tiny.py a $WORK/stage1_colorlocked.mp4 (o usa el fork ComfyUI).
echo "[ACCIÓN MANUAL] apunta el infer de FlashVSR a: $WORK/stage1_colorlocked.mp4"
echo "  luego: python infer_flashvsr_v1.1_tiny.py   (o _full si hay VRAM)"
echo "Salida final = vídeo VSR de FlashVSR."
echo "DONE pipeline (etapa 2 requiere el paso manual indicado)."
