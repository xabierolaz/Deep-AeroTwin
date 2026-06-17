#!/bin/bash
# uso: bash check.sh <nombre_destino_en_outputs>
DEST="$1"
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_finish.log
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
{
  echo "TIME $(date +%H:%M:%S)"
  echo "=== finish markers ==="
  grep -aE 'BSA_RC|BSA_IMPORT_OK|WEIGHTS_RC|FVSR_FINISH_DONE' "$L" 2>/dev/null | tail -8
  echo "=== last ninja ==="
  grep -aoE '\[[0-9]+/[0-9]+\]' "$L" 2>/dev/null | tail -1
  echo "=== procs (build/dl) ==="
  pgrep -af 'fvsr_finish|setup.py|nvcc|hf download' 2>/dev/null | grep -v pgrep | wc -l
  echo "=== weights size ==="
  du -sh /mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR/examples/WanVSR/FlashVSR-v1.1 2>/dev/null
} > "$O/$DEST" 2>&1
