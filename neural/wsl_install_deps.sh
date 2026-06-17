#!/bin/bash
set +e
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/wsl_deps.log
exec > "$LOG" 2>&1
echo "=== START deps $(date) ==="
source ~/sdv2_venv/bin/activate

REPO=/mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2

echo "=== install package (no deps, keep torch 2.11) ==="
pip install --no-deps -e "$REPO"

echo "=== install compatible deps (numpy2 binary, no torch downgrade) ==="
pip install \
  "accelerate>=1.10" "av>=13" "diffusers==0.35.1" "einops>=0.8" \
  "fastapi>=0.117" "ftfy>=6.3" "imageio>=2.37" "imageio-ffmpeg>=0.6" \
  "markdown2>=2.5" "omegaconf>=2.3" "Pillow>=10.1" "pydantic>=2.10" \
  "regex" "scikit-image>=0.25" "sentencepiece>=0.2" "transformers==4.54.0" \
  "uvicorn>=0.37" "websockets" "huggingface_hub" "hf_transfer"

echo "=== import smoke test ==="
python -c "import streamdiffusionv2 as s; print('streamdiffusionv2 import OK', getattr(s,'__file__',''))" 2>&1 | head -5
python -c "import diffusers, transformers, numpy; print('diffusers', diffusers.__version__, 'transformers', transformers.__version__, 'numpy', numpy.__version__)"

echo "=== DONE_DEPS $(date) ==="
