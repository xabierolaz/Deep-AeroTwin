#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/vace_dl.log
exec > "$LOG" 2>&1
set -x
source ~/sdv2_venv/bin/activate
DEST=/mnt/d/Deep-AeroTwin-UE57-Test/neural/VideoX-Fun/models/Diffusion_Transformer/Wan2.1-VACE-1.3B
mkdir -p "$DEST"
export HF_HUB_ENABLE_HF_TRANSFER=0
hf download Wan-AI/Wan2.1-VACE-1.3B --local-dir "$DEST"
echo "HF_RC=$?"
du -sh "$DEST"
ls -la "$DEST"
echo "DL_DONE"
