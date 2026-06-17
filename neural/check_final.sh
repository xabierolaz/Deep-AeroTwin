#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/final1.log
{
  echo "TIME $(date +%H:%M:%S)"
  grep -aE 'VACE_FINAL_RC|colormatched|FINAL1_DONE|Error|Traceback|out of memory' "$L" 2>/dev/null|grep -av '^+'|tail -6
  echo "prog: $(grep -aoE '[0-9]+%[^0-9]+[0-9]+/[0-9]+' "$L" 2>/dev/null|tail -1)"
  echo "proc: $(pgrep -af predict_final|grep -v pgrep|wc -l)"
  echo "out:"; ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final/ /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final_color.mp4 2>/dev/null
} > "$O/$DEST" 2>&1
