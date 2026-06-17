#!/bin/bash
set +e
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_models.log
exec > "$LOG" 2>&1
echo "=== START models $(date) ==="
source ~/sdv2_venv/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=1

# Put big checkpoints on D: (persistent, 255GB free)
ROOT=/mnt/d/Deep-AeroTwin-UE57-Test/neural
WAN=$ROOT/wan_models/Wan2.1-T2V-1.3B
CKPT=$ROOT/ckpts
mkdir -p "$WAN" "$CKPT"

echo "=== Wan2.1-T2V-1.3B base ==="
huggingface-cli download --resume-download Wan-AI/Wan2.1-T2V-1.3B --local-dir "$WAN" 2>&1 | tail -3
echo "WAN_EXIT=$?"

echo "=== StreamDiffusionV2 causal v2v 1.3B ckpt ==="
huggingface-cli download --resume-download jerryfeng/StreamDiffusionV2 --local-dir "$CKPT" --include "wan_causal_dmd_v2v/*" 2>&1 | tail -3
echo "CKPT_EXIT=$?"

echo "=== sizes ==="
du -sh "$WAN" "$CKPT" 2>/dev/null
echo "=== DONE_MODELS $(date) ==="
