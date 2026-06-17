#!/bin/bash
# Setup del pipeline 2 etapas (WSL/GPU 5090):
#   Etapa 1: VACE (Wan2.1-VACE) — generación condicionada por estructura (canny/depth)
#   Etapa 2: FlashVSR — super-resolución estructura-fiel
# Idempotente: re-ejecutable; salta lo ya hecho. NO descarga si ya existe.
set -e
ROOT=/mnt/d/Deep-AeroTwin-UE57-Test/neural
cd "$ROOT"

echo "==================== 1) VideoX-Fun (VACE etapa 1) ===================="
if [ ! -d VideoX-Fun ]; then
  git clone https://github.com/aigc-apps/VideoX-Fun.git
fi
cd VideoX-Fun
python3 -m venv ~/vxf_venv 2>/dev/null || true
source ~/vxf_venv/bin/activate
pip install -q -U pip
# torch cu12x para Blackwell (5090). Ajusta el index si tu CUDA difiere.
pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128 || \
  echo "[warn] instala torch manualmente si falla (5090=sm_120 necesita cu128+)"
pip install -q -r requirements.txt || echo "[warn] revisa requirements"

echo "==================== 2) Pesos VACE (cabe en 32GB) ===================="
mkdir -p models/Diffusion_Transformer
cd models/Diffusion_Transformer
# 1.3B = holgado; 14B = mejor calidad pero ~28GB (usa GPU_memory_mode qfloat8/offload).
if [ ! -d Wan2.1-VACE-1.3B ]; then
  git lfs install
  git lfs clone https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B
fi
# Para 14B (opcional, mejor calidad):
# git lfs clone https://huggingface.co/Wan-AI/Wan2.1-VACE-14B
cd "$ROOT"

echo "==================== 3) FlashVSR (etapa 2) ===================="
if [ ! -d FlashVSR ]; then
  git clone https://github.com/OpenImagingLab/FlashVSR.git
fi
cd FlashVSR
python3 -m venv ~/flashvsr_venv 2>/dev/null || true
source ~/flashvsr_venv/bin/activate
pip install -q -U pip
pip install -e . -q || echo "[warn] revisa setup.py"
pip install -q -r requirements.txt || true
# Block-Sparse-Attention (REQUERIDO por FlashVSR). AVISO: los autores solo lo
# validan en A100/A800/H200; en RTX 50 (Blackwell) es DESCONOCIDO. Si falla aquí,
# usa el fork ComfyUI o el modo tiny (ver README_pipeline_2stage.md).
if [ ! -d Block-Sparse-Attention ]; then
  git clone https://github.com/mit-han-lab/Block-Sparse-Attention
  cd Block-Sparse-Attention && pip install -q packaging ninja && python setup.py install || \
    echo "[ERROR] Block-Sparse-Attention no compiló en la 5090; ver alternativas en el README"
  cd "$ROOT/FlashVSR"
fi
# Pesos FlashVSR v1.1 (recomendado)
cd examples/WanVSR
git lfs install
[ -d FlashVSR-v1.1 ] || git lfs clone https://huggingface.co/JunhaoZhuang/FlashVSR-v1.1
cd "$ROOT"

echo "==================== (opcional) SeedVR2 fallback etapa 2 ===================="
echo "Si FlashVSR no corre en la 5090, alternativa SeedVR2-3B:"
echo "  https://huggingface.co/ByteDance-Seed (buscar SeedVR2-3B) — VSR diffusion, 24GB+"

echo "==================== (opcional) Depth para mejor control ===================="
echo "Etapa1 por defecto usa CANNY (cv2). Para control DEPTH (recomendado en aéreo):"
echo "  git clone https://github.com/DepthAnything/Depth-Anything-V2 y genera el depth_video."
echo "SETUP COMPLETO."
