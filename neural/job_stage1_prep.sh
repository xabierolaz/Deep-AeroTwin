#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/stage1_prep.log
exec > "$LOG" 2>&1
set -x
NEURAL=/mnt/d/Deep-AeroTwin-UE57-Test/neural
source ~/sdv2_venv/bin/activate

echo "=== weights present? ==="
ls -la "$NEURAL/VideoX-Fun/models/Diffusion_Transformer/Wan2.1-VACE-1.3B/"
echo "=== config yaml present? ==="
ls "$NEURAL/VideoX-Fun/config/wan2.1/" | head

echo "=== import test videox_fun ==="
cd "$NEURAL/VideoX-Fun"
python - <<'PY'
import sys
sys.path.insert(0,'.')
try:
    from videox_fun.models import VaceWanTransformer3DModel, AutoencoderKLWan, WanT5EncoderModel
    from videox_fun.pipeline import WanVacePipeline
    print("IMPORT_OK")
except Exception as e:
    import traceback; traceback.print_exc(); print("IMPORT_FAIL")
PY

echo "=== extract canny control from Ejea clip ==="
python "$NEURAL/extract_control.py" --video /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4 \
  --out "$NEURAL/ejea_control_canny.mp4" --mode canny
ls -la "$NEURAL/ejea_control_canny.mp4"
echo "PREP_DONE"
