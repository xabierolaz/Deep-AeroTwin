#!/bin/bash
# StreamDiffusionV2 POC setup in WSL2 (RTX 5090 / Blackwell sm_120)
set -e
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_sdv2_setup.log
exec > "$LOG" 2>&1
echo "=== START $(date) ==="

NEURAL=/mnt/d/Deep-AeroTwin-UE57-Test/neural
VENV=$HOME/sdv2_venv          # venv on fast WSL fs
MODELS=$NEURAL/models         # checkpoints on D: (persistent, big disk)
mkdir -p "$MODELS"

echo "=== python venv ==="
python3 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install --upgrade pip wheel

echo "=== torch 2.11 cu128 (Blackwell) ==="
pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128

echo "=== torch probe ==="
python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda, "avail", torch.cuda.is_available())
if torch.cuda.is_available():
    print("dev", torch.cuda.get_device_name(0), "cap", torch.cuda.get_device_capability(0))
    a=torch.randn(4096,4096,device='cuda'); b=torch.randn(4096,4096,device='cuda')
    import time; torch.cuda.synchronize(); t=time.time()
    for _ in range(20): c=a@b
    torch.cuda.synchronize(); print("matmul 20x4096 ok, ms/iter", round((time.time()-t)/20*1000,2))
PY

echo "=== streamdiffusionv2 (PyPI) ==="
pip install streamdiffusionv2 huggingface_hub || pip install -e "$NEURAL/StreamDiffusionV2"

echo "=== versions ==="
pip show streamdiffusionv2 | head -3 || true
echo "=== DONE_SETUP $(date) ==="
