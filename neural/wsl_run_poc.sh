#!/bin/bash
set +e
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_poc_run.log
exec > "$LOG" 2>&1
echo "=== START POC run $(date) ==="
source ~/sdv2_venv/bin/activate
cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2

# de-CRLF the repo shell scripts (Windows checkout)
sed -i 's/\r$//' run_v2v.sh

# wire model paths expected by wan_wrapper (wan_models/ and ckpts/ next to repo)
ln -sfn ../wan_models wan_models
ln -sfn ../ckpts ckpts

echo "=== nvidia-smi ==="
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader

echo "=== run single-GPU v2v, step=2, 480x832, profile ==="
CHECKPOINT_FOLDER=ckpts/wan_causal_dmd_v2v \
CONFIG_PATH=configs/wan_causal_dmd_v2v.yaml \
HEIGHT=480 WIDTH=832 FPS=16 STEP=2 \
OUTPUT_FOLDER=/mnt/d/Deep-AeroTwin-UE57-Test/neural/outputs/ \
bash run_v2v.sh single --profile --num_frames 81

echo "=== outputs ==="
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/neural/outputs/ 2>/dev/null | tail
echo "=== DONE_POC $(date) ==="
