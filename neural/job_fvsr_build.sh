#!/bin/bash
# Build FlashVSR completo en Blackwell (sm_120). venv en ext4 (~/flashvsr_venv).
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_build.log
exec > "$LOG" 2>&1
set -x
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
FV=/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR

echo "=== nvcc ==="; nvcc --version | tail -2

echo "=== crear venv en ext4 ==="
python3 -m venv ~/flashvsr_venv
source ~/flashvsr_venv/bin/activate
pip install -U pip wheel setuptools ninja packaging

echo "=== torch 2.11 cu128 (Blackwell) ==="
pip install torch==2.11.0 torchvision --index-url https://download.pytorch.org/whl/cu128
python -c "import torch;print('TORCH',torch.__version__,torch.version.cuda)"

echo "=== deps FlashVSR (sin pines de torch) ==="
grep -ivE '^torch($|[=<>])|^torchaudio|^torchvision' "$FV/requirements.txt" > /tmp/fvsr_reqs.txt
cat /tmp/fvsr_reqs.txt
pip install -r /tmp/fvsr_reqs.txt
echo "DEPS_RC=$?"

echo "=== instalar diffsynth (paquete FlashVSR) sin deps ==="
cd "$FV" && pip install -e . --no-deps
echo "PKG_RC=$?"

echo "=== compilar Block-Sparse-Attention SOLO sm_120 ==="
cd ~/Block-Sparse-Attention
export BLOCK_SPARSE_ATTN_CUDA_ARCHS=120
export MAX_JOBS=6
python setup.py install
echo "BSA_RC=$?"
python -c "import block_sparse_attn; print('BSA_IMPORT_OK')" 2>&1 | tail -3

echo "=== descargar pesos FlashVSR-v1.1 ==="
mkdir -p "$FV/examples/WanVSR/FlashVSR-v1.1"
export HF_HUB_ENABLE_HF_TRANSFER=0
hf download JunhaoZhuang/FlashVSR-v1.1 --local-dir "$FV/examples/WanVSR/FlashVSR-v1.1"
echo "WEIGHTS_RC=$?"
du -sh "$FV/examples/WanVSR/FlashVSR-v1.1"
echo "FVSR_BUILD_DONE"
