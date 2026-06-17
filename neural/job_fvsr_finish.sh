#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_finish.log
exec > "$LOG" 2>&1
set -x
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
FV=/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR
source ~/flashvsr_venv/bin/activate

echo "=== resume BSA build (MAX_JOBS=3 para evitar OOM) ==="
cd ~/Block-Sparse-Attention
export BLOCK_SPARSE_ATTN_CUDA_ARCHS=120
export MAX_JOBS=3
python setup.py install
echo "BSA_RC=$?"
python -c "import block_sparse_attn; print('BSA_IMPORT_OK')" 2>&1 | tail -2

echo "=== descargar pesos FlashVSR-v1.1 ==="
mkdir -p "$FV/examples/WanVSR/FlashVSR-v1.1"
export HF_HUB_ENABLE_HF_TRANSFER=0
hf download JunhaoZhuang/FlashVSR-v1.1 --local-dir "$FV/examples/WanVSR/FlashVSR-v1.1"
echo "WEIGHTS_RC=$?"
du -sh "$FV/examples/WanVSR/FlashVSR-v1.1"
echo "FVSR_FINISH_DONE"
