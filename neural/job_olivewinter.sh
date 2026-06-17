#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/olivewinter.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$N/VideoX-Fun"
python "$N/configure_wan_control.py" \
  --src examples/wan2.1_vace/predict_v2v_control.py \
  --out examples/wan2.1_vace/predict_olivewinter.py \
  --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$N/ejea_control_canny.mp4" \
  --prompt-file "$N/ejea_prompt_olivewinter.txt" \
  --size 480 480 --frames 49 --fps 16 \
  --steps 30 --guidance 5.0 --gpu-mode model_cpu_offload \
  --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_olivewinter"
python examples/wan2.1_vace/predict_olivewinter.py
echo "OW_RC=$?"
ls /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_olivewinter/
echo "OW_DONE"
