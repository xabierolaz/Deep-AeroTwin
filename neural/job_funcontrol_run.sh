#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_run.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate

echo "=== esperar fin de descarga ==="
for i in $(seq 1 120); do
  grep -q FUNCTRL_DL_DONE /mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_dl.log 2>/dev/null && break
  sleep 10
done
grep -aE 'FUNCTRL_DL_RC|FUNCTRL_DL_DONE' /mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_dl.log | tail -2

echo "=== ref frame de Cesium (480x480) ==="
python - <<'PY'
import cv2
c=cv2.VideoCapture("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4")
c.set(cv2.CAP_PROP_POS_FRAMES,10); ok,f=c.read(); c.release()
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_ref.png", cv2.resize(f,(480,480)))
print("ref written")
PY

echo "=== configurar control_ref ==="
cd "$N/VideoX-Fun"
python "$N/configure_wan_control.py" \
  --src examples/wan2.1_fun/predict_v2v_control_ref.py \
  --out examples/wan2.1_fun/predict_aerotwin_ref.py \
  --model "models/Diffusion_Transformer/Wan2.1-Fun-V1.1-1.3B-Control" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$N/ejea_control_canny.mp4" \
  --ref "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_ref.png" \
  --prompt-file "$N/ejea_prompt.txt" \
  --size 480 480 --frames 49 --fps 16 \
  --steps 30 --guidance 4.0 --gpu-mode model_cpu_offload \
  --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out"
echo "CFG_RC=$?"

echo "=== run ==="
python examples/wan2.1_fun/predict_aerotwin_ref.py
echo "FUNCTRL_RUN_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out/ 2>/dev/null
echo "FUNCTRL_RUN_DONE"
