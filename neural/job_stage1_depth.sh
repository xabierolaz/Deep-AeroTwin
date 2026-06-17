#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/stage1_depth.log
exec > "$LOG" 2>&1
set -x
NEURAL=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$NEURAL/VideoX-Fun"
python "$NEURAL/configure_wan_control.py" \
  --src examples/wan2.1_vace/predict_v2v_control.py \
  --out examples/wan2.1_vace/predict_aerotwin_depth.py \
  --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$NEURAL/ejea_control_depth.mp4" \
  --prompt-file "$NEURAL/ejea_prompt.txt" \
  --size 480 480 --frames 81 --fps 16 \
  --steps 30 --guidance 4.0 --gpu-mode model_cpu_offload \
  --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_depth_out"
echo "CONFIGURE_RC=$?"
python examples/wan2.1_vace/predict_aerotwin_depth.py
echo "PREDICT_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_depth_out/ 2>/dev/null
echo "STAGE1_DEPTH_DONE"
