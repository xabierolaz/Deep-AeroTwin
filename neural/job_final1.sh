#!/bin/bash
# Pase final parte 1: VACE olivar-invierno clip completo + color-match a foto real
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/final1.log
exec > "$LOG" 2>&1
set -x
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
cd "$N/VideoX-Fun"
python "$N/configure_wan_control.py" \
  --src examples/wan2.1_vace/predict_v2v_control.py \
  --out examples/wan2.1_vace/predict_final.py \
  --model "models/Diffusion_Transformer/Wan2.1-VACE-1.3B" \
  --config-path "config/wan2.1/wan_civitai.yaml" \
  --control "$N/ejea_control_canny.mp4" \
  --prompt-file "$N/ejea_prompt_olivewinter.txt" \
  --size 480 480 --frames 189 --fps 16 \
  --steps 30 --guidance 5.0 --gpu-mode model_cpu_offload \
  --save "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final"
python examples/wan2.1_vace/predict_final.py
echo "VACE_FINAL_RC=$?"
# color-match a foto real
python - <<'PY'
import cv2,numpy as np,glob
g=glob.glob("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final/*.mp4")
src=g[-1]
ref=cv2.cvtColor(cv2.imread("/mnt/d/Deep-AeroTwin-UE57-Test/Captura de pantalla 2026-06-13 131038.png"),cv2.COLOR_BGR2LAB).astype(np.float32)
rm=[ref[...,c].mean() for c in range(3)];rs=[ref[...,c].std()+1e-6 for c in range(3)]
cap=cv2.VideoCapture(src);fps=cap.get(5) or 16;W=int(cap.get(3));H=int(cap.get(4))
out="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final_color.mp4"
vw=cv2.VideoWriter(out,cv2.VideoWriter_fourcc(*"mp4v"),fps,(W,H))
while True:
    ok,f=cap.read()
    if not ok: break
    l=cv2.cvtColor(f,cv2.COLOR_BGR2LAB).astype(np.float32)
    for c in range(3): l[...,c]=(l[...,c]-l[...,c].mean())/(l[...,c].std()+1e-6)*rs[c]+rm[c]
    vw.write(cv2.cvtColor(np.clip(l,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR))
cap.release();vw.release();print("colormatched ->",out)
PY
echo "FINAL1_DONE"
