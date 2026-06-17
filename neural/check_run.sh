#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/fvsr_run.log
{
  echo "TIME $(date +%H:%M:%S)"
  echo "=== run markers ==="
  grep -aE 'FVSR_RUN_RC|FVSR_RUN_DONE|Error|Traceback|out of memory|ImportError|wrote .*frames|BSA|RuntimeError' "$L" 2>/dev/null | grep -avE '^\+' | tail -12
  echo "=== procs ==="
  pgrep -af 'infer_aerotwin' 2>/dev/null | grep -v pgrep | wc -l
  echo "=== output ==="
  ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/ 2>/dev/null
  echo "=== last log line ==="
  tail -3 "$L" 2>/dev/null | grep -avE '^\+'
} > "$O/$DEST" 2>&1
