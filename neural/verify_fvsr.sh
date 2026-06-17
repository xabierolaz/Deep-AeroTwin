#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
FV=/mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR
source ~/flashvsr_venv/bin/activate 2>/dev/null
{
  echo "TIME $(date +%H:%M:%S)"
  echo "=== finish markers ==="
  grep -aE 'BSA_RC|BSA_IMPORT_OK|WEIGHTS_RC|FVSR_FINISH_DONE' /mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_finish.log 2>/dev/null | tail -8
  echo "=== procs ==="
  pgrep -af 'fvsr_finish|setup.py|nvcc|hf download' 2>/dev/null | grep -v pgrep | wc -l
  echo "=== BSA import test ==="
  python -c "import block_sparse_attn; print('BSA_OK', block_sparse_attn.__file__)" 2>&1 | tail -2
  echo "=== weights ==="
  ls -la "$FV/examples/WanVSR/FlashVSR-v1.1/" 2>/dev/null | grep -E 'safetensors|ckpt|pth|VAE'
  du -sh "$FV/examples/WanVSR/FlashVSR-v1.1" 2>/dev/null
} > "$O/$DEST" 2>&1
