#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_run.log
exec > "$LOG" 2>&1
set -x
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
FV=/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR
export PYTHONPATH=$FV
source ~/flashvsr_venv/bin/activate
pip install -q modelscope
cd "$FV/examples/WanVSR"
python infer_aerotwin.py
echo "FVSR_RUN_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/ 2>/dev/null
echo "FVSR_RUN_DONE"
