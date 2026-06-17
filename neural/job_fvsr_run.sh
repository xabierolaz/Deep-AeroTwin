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

echo "=== preparar input 320x320, 49 frames ==="
python - <<'PY'
import cv2
src="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
dst="/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR/examples/WanVSR/inputs/ejea_lq.mp4"
c=cv2.VideoCapture(src); fps=c.get(5) or 16
vw=cv2.VideoWriter(dst,cv2.VideoWriter_fourcc(*"mp4v"),fps,(320,320))
n=0
while n<49:
    ok,f=c.read()
    if not ok: break
    vw.write(cv2.resize(f,(320,320))); n+=1
c.release(); vw.release(); print("wrote",dst,n,"frames")
PY

echo "=== generar infer_aerotwin.py ==="
python - <<'PY'
src="/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR/examples/WanVSR/infer_flashvsr_v1.1_tiny.py"
t=open(src).read()
t=t.replace('RESULT_ROOT = "./results"','RESULT_ROOT = "/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out"')
import re
t=re.sub(r'inputs = \[.*?\]', 'inputs = ["./inputs/ejea_lq.mp4"]', t, count=1, flags=re.S)
open("/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR/examples/WanVSR/infer_aerotwin.py","w").write(t)
print("infer_aerotwin.py written")
PY

echo "=== run FlashVSR ==="
cd "$FV/examples/WanVSR"
python infer_aerotwin.py
echo "FVSR_RUN_RC=$?"
ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/ 2>/dev/null
echo "FVSR_RUN_DONE"
