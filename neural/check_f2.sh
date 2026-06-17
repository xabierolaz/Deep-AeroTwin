#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/final2.log
{
  echo "TIME $(date +%H:%M:%S)"
  grep -aE 'FINAL2_RC|FINAL2_DONE|Error|Traceback|out of memory|ImportError' "$L" 2>/dev/null|grep -av '^+'|tail -6
  echo "proc: $(pgrep -af infer_final|grep -v pgrep|wc -l)"
  echo "out:"; ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/final_fvsr/ 2>/dev/null
  echo "tail:"; tail -2 "$L" 2>/dev/null|grep -av '^+'
} > "$O/$DEST" 2>&1
