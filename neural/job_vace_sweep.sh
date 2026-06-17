#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/vace_sweep.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$N/VideoX-Fun"

run_ctx () {
  CTX=$1; TAG=$2
  python "$N/configure_wan_control.py" \
    --src examples/wan2.1_vace/predict_v2v_control.py \
    --out examples/wan2.1_vace/predict_ctx_${TAG}.py \
    --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
    --config-path "config/wan2.1/wan_civitai.yaml" \
    --control "$N/ejea_control_canny.mp4" \
    --prompt-file "$N/ejea_prompt.txt" \
    --size 480 480 --frames 49 --fps 16 \
    --steps 30 --guidance 5.0 --gpu-mode model_cpu_offload \
    --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_${TAG}"
  # fijar vace_context_scale al valor del barrido
  sed -i "s/^vace_context_scale.*/vace_context_scale  = ${CTX}/" examples/wan2.1_vace/predict_ctx_${TAG}.py
  grep -n 'vace_context_scale' examples/wan2.1_vace/predict_ctx_${TAG}.py | head -1
  python examples/wan2.1_vace/predict_ctx_${TAG}.py
  echo "CTX_${TAG}_RC=$?"
}

run_ctx 0.2 020
run_ctx 0.5 050
echo "VACE_SWEEP_DONE"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_020 /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_050 2>/dev/null
