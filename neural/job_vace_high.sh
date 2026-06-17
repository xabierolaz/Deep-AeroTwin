#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/vace_high.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$N/VideoX-Fun"
run_ctx () {
  CTX=$1; TAG=$2; CTRL=$3
  python "$N/configure_wan_control.py" \
    --src examples/wan2.1_vace/predict_v2v_control.py \
    --out examples/wan2.1_vace/predict_hi_${TAG}.py \
    --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
    --config-path "config/wan2.1/wan_civitai.yaml" \
    --control "$CTRL" \
    --prompt-file "$N/ejea_prompt.txt" \
    --size 480 480 --frames 49 --fps 16 \
    --steps 30 --guidance 5.0 --gpu-mode model_cpu_offload \
    --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_hi_${TAG}"
  sed -i "s/^vace_context_scale.*/vace_context_scale  = ${CTX}/" examples/wan2.1_vace/predict_hi_${TAG}.py
  python examples/wan2.1_vace/predict_hi_${TAG}.py
  echo "HI_${TAG}_RC=$?"
}
run_ctx 1.5 c15 "$N/ejea_control_canny.mp4"
run_ctx 2.0 c20 "$N/ejea_control_canny.mp4"
echo "VACE_HIGH_DONE"
