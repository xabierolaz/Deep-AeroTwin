#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
M=/mnt/d/Deep-AeroTwin-UE57-Test/neural/VideoX-Fun/models/Diffusion_Transformer/Wan2.1-Fun-V1.1-1.3B-Control
{
  echo "TIME $(date +%H:%M:%S)"
  grep -aE 'FUNCTRL_DL_RC|FUNCTRL_DL_DONE' /mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_dl.log 2>/dev/null | tail -3
  echo "proc: $(pgrep -af 'hf download' | grep -v pgrep | wc -l)"
  echo "size: $(du -sh "$M" 2>/dev/null)"
  ls "$M" 2>/dev/null | head
} > "$O/$DEST" 2>&1
