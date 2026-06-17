#!/bin/bash
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_finish.log
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
{
  echo "=== MARKERS ==="
  grep -aE 'BSA_RC|BSA_IMPORT_OK|WEIGHTS_RC|FVSR_BUILD_DONE' "$L" | tail -8
  echo "=== last ninja ==="
  grep -aoE '\[[0-9]+/[0-9]+\]' "$L" | tail -1
  echo "=== proc count ==="
  pgrep -af 'job_fvsr_build|nvcc|hf download' | grep -v pgrep | wc -l
  echo "=== weights size ==="
  du -sh /mnt/d/Deep-AeroTwin-UE57-Test/neural/FlashVSR/examples/WanVSR/FlashVSR-v1.1 2>/dev/null
} > /tmp/fvsr_poll_out.txt 2>&1
cp /tmp/fvsr_poll_out.txt "$O/fvsr_poll.txt" 2>/dev/null
cp /tmp/fvsr_poll_out.txt /mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_poll.txt 2>/dev/null
sync
