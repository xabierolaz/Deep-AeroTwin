#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ref_g8.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$N/VideoX-Fun"
python "$N/configure_wan_control.py" \
  --src examples/wan2.1_fun/predict_v2v_control_ref.py \
  --out examples/wan2.1_fun/predict_aerotwin_ref_g8.py \
  --model "models/Diffusion_Transformer/Wan2.1-Fun-V1.1-1.3B-Control" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$N/ejea_control_canny.mp4" \
  --ref "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_ref.png" \
  --prompt-file "$N/ejea_prompt.txt" \
  --size 480 480 --frames 49 --fps 16 \
  --steps 30 --guidance 8.0 --gpu-mode model_cpu_offload \
  --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_g8_out"
echo "CFG_RC=$?"
python examples/wan2.1_fun/predict_aerotwin_ref_g8.py
echo "RUN_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_g8_out/ 2>/dev/null
echo "REF_G8_DONE"
