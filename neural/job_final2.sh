#!/bin/bash
# Pase final parte 2: FlashVSR sobre el VACE color-matched (clip completo, 2x)
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/final2.log
exec > "$LOG" 2>&1
set -x
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
FV=/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR
export PYTHONPATH=$FV
source ~/flashvsr_venv/bin/activate
cd "$FV/examples/WanVSR"
# generar infer_final.py: input = VACE color-matched, scale 2.0, salida propia
python - <<'PY'
import re
t=open("infer_flashvsr_v1.1_tiny.py").read()
t=t.replace('RESULT_ROOT = "./results"','RESULT_ROOT = "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/final_fvsr"')
t=re.sub(r'inputs = \[.*?\]', 'inputs = ["/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final_color.mp4"]', t, count=1, flags=re.S)
t=t.replace('seed, scale, dtype, device = 0, 4.0,','seed, scale, dtype, device = 0, 2.0,')
open("infer_final.py","w").write(t); print("infer_final.py ready")
PY
python infer_final.py
echo "FINAL2_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/final_fvsr/ 2>/dev/null
echo "FINAL2_DONE"
