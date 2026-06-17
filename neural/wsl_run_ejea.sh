#!/bin/bash
set +e
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_ejea_run.log
exec > "$LOG" 2>&1
echo "=== START Ejea restyle $(date) ==="
source ~/sdv2_venv/bin/activate
cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2
sed -i 's/\r$//' run_v2v.sh
ln -sfn ../wan_models wan_models
ln -sfn ../ckpts ckpts
export TOKENIZERS_PARALLELISM=false

# run_v2v.sh prefixes ROOT_DIR to all paths -> copy inputs into repo, use relative paths
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4 ./ejea_clip_input.mp4
cp /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_prompt.txt ./ejea_prompt.txt

echo "=== run: Ejea clip -> photoreal drone, 480x480, step 2 ==="
CHECKPOINT_FOLDER=ckpts/wan_causal_dmd_v2v \
CONFIG_PATH=configs/wan_causal_dmd_v2v.yaml \
HEIGHT=480 WIDTH=480 FPS=16 STEP=2 \
OUTPUT_FOLDER=poc_ejea/ \
PROMPT_FILE_PATH=ejea_prompt.txt \
VIDEO_PATH=ejea_clip_input.mp4 \
bash run_v2v.sh single --profile --num_frames 160

echo "=== outputs ==="
find /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2/poc_ejea -name "*.mp4" -exec ls -la {} \;
echo "=== DONE_EJEA $(date) ==="
