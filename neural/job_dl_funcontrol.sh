#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_dl.log
exec > "$LOG" 2>&1
set -x
source ~/sdv2_venv/bin/activate
DEST=/mnt/d/Deep-AeroTwin-UE57-Test/neural/VideoX-Fun/models/Diffusion_Transformer/Wan2.1-Fun-V1.1-1.3B-Control
mkdir -p "$DEST"
export HF_HUB_ENABLE_HF_TRANSFER=0
hf download alibaba-pai/Wan2.1-Fun-V1.1-1.3B-Control --local-dir "$DEST"
echo "FUNCTRL_DL_RC=$?"
du -sh "$DEST"
echo "FUNCTRL_DL_DONE"
