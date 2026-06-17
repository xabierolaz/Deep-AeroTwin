#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/depth.log
exec > "$LOG" 2>&1
set -x
NEURAL=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate
python "$NEURAL/extract_depth.py" \
  --video /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4 \
  --out "$NEURAL/ejea_control_depth.mp4" \
  --model depth-anything/Depth-Anything-V2-Small-hf
echo "DEPTH_RC=$?"
ls -la "$NEURAL/ejea_control_depth.mp4"
echo "DEPTH_JOB_DONE"
