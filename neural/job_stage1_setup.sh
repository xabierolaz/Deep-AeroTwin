#!/bin/bash
# Job de setup etapa 1 (VACE) — reutiliza ~/sdv2_venv (torch 2.11+cu128 OK en 5090).
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/stage1_setup.log
exec > "$LOG" 2>&1
set -x
cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/VideoX-Fun
source ~/sdv2_venv/bin/activate
echo "=== pip install VideoX-Fun deps (torch ya satisfecho >=2.1.2) ==="
pip install --upgrade-strategy only-if-needed \
  Pillow einops safetensors timm tomesd librosa torchdiffeq torchsde decord \
  datasets scikit-image opencv-python omegaconf SentencePiece albumentations \
  "imageio[ffmpeg]" "imageio[pyav]" beautifulsoup4 ftfy func_timeout onnxruntime \
  "accelerate>=0.25.0" "diffusers>=0.30.1" "transformers>=4.46.2"
echo "PIP_DEPS_DONE rc=$?"
echo "=== torch sanity tras instalar deps ==="
python -c "import torch;print('torch',torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_name(0))"
echo "=== descarga pesos Wan2.1-VACE-1.3B ==="
mkdir -p models/Diffusion_Transformer
cd models/Diffusion_Transformer
if [ ! -d Wan2.1-VACE-1.3B ]; then
  GIT_LFS_SKIP_SMUDGE=0 git lfs install
  git clone https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B
fi
echo "WEIGHTS_DONE rc=$?"
du -sh Wan2.1-VACE-1.3B 2>/dev/null
echo "ALL_STAGE1_SETUP_DONE"
