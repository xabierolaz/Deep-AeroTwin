#!/bin/bash
set +e
NS="${1:-0.5}"
TAG="${2:-ns05}"
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_ejea_${TAG}.log
exec > "$LOG" 2>&1
echo "=== START Ejea restyle noise_scale=$NS $(date) ==="
source ~/sdv2_venv/bin/activate
cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2
sed -i 's/\r$//' run_v2v.sh
ln -sfn ../wan_models wan_models
ln -sfn ../ckpts ckpts
export TOKENIZERS_PARALLELISM=false
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4 ./ejea_clip_input.mp4
cp /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_prompt.txt ./ejea_prompt.txt

CHECKPOINT_FOLDER=ckpts/wan_causal_dmd_v2v \
CONFIG_PATH=configs/wan_causal_dmd_v2v.yaml \
HEIGHT=480 WIDTH=480 FPS=16 STEP=2 \
OUTPUT_FOLDER=poc_ejea_${TAG}/ \
PROMPT_FILE_PATH=ejea_prompt.txt \
VIDEO_PATH=ejea_clip_input.mp4 \
bash run_v2v.sh single --num_frames 160 --noise_scale "$NS"

echo "=== output ==="
find poc_ejea_${TAG} -name "*.mp4" -exec ls -la {} \;
echo "=== DONE_${TAG} $(date) ==="
