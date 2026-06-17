#!/bin/bash
DEST="$1"
O='/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs'
L=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/functrl_run.log
{
  echo "TIME $(date +%H:%M:%S)"
  echo "=== markers ==="
  grep -aE 'FUNCTRL_DL_DONE|CFG_RC|FUNCTRL_RUN_RC|FUNCTRL_RUN_DONE|Error|Traceback|out of memory|ref written|configurad' "$L" 2>/dev/null | grep -avE '^\+' | tail -12
  echo "=== last ninja/progress ==="
  grep -aoE '[0-9]+%[^0-9]+[0-9]+/[0-9]+' "$L" 2>/dev/null | tail -1
  echo "=== procs ==="
  pgrep -af 'job_funcontrol_run|predict_aerotwin_ref|hf download' 2>/dev/null | grep -v pgrep | wc -l
  echo "=== out ==="
  ls -la /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out/ 2>/dev/null
} > "$O/$DEST" 2>&1
