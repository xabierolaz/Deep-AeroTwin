param(
  [switch]$Soft,
  [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"

function _log([string]$msg) {
  if (-not $Quiet) {
    Write-Host $msg
  }
}

_log "[stop_pipeline] Stopping Deep-AeroTwin pipeline processes..."

# Match by command line so this works for:
# - separate cmd.exe windows started by launch.bat
# - Windows Terminal tabs (cmd.exe hosted by wt.exe)
$regex = '(?i)(flight_controller\.py|vision_system\.py|viz_recorder\.py|log_server\.py|tee\.py|e2e_flight_matrix\.py)'

function _self_parent_pid() {
  try {
    $me = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $PID)
    if ($me -and $me.ParentProcessId) { return [int]$me.ParentProcessId }
  } catch {
    return $null
  }
  return $null
}

$parentPid = _self_parent_pid
_log ("[stop_pipeline] self_pid={0} parent_pid={1}" -f $PID, ($parentPid | ForEach-Object { $_ }))
try {
  $selfWmi = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $PID)
  if ($selfWmi) {
    $selfCmd = ($selfWmi.CommandLine | ForEach-Object { $_ }) -join ""
    if ($selfCmd.Length -gt 160) { $selfCmd = $selfCmd.Substring(0, 160) + "..." }
    _log ("[stop_pipeline] self_wmi name={0} cmd={1}" -f $selfWmi.Name, $selfCmd)
  }
} catch {}

$pyTargets = @()
$cmdTargets = @()
try {
  # Only kill python processes. Killing the hosting cmd.exe can kill this script
  # when run from inside a pipeline tab (taskkill /T tries to kill itself).
  $pyTargets = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match $regex) } |
    Where-Object { $_.Name -and ($_.Name -imatch '^python(?:3)?\.exe$') } |
    Where-Object { ([int]$_.ProcessId -ne $PID) } |
    Sort-Object -Property ProcessId -Unique

  # Kill the hosting cmd.exe tabs too, but never kill our direct parent (so the script can finish
  # even if you run it from inside a pipeline tab).
  $cmdTargets = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match $regex) } |
    Where-Object { $_.Name -and ($_.Name -imatch '^cmd\.exe$') } |
    Where-Object { -not $parentPid -or ([int]$_.ProcessId -ne $parentPid) } |
    Where-Object { ([int]$_.ProcessId -ne $PID) } |
    Sort-Object -Property ProcessId -Unique
} catch {
  $pyTargets = @()
  $cmdTargets = @()
}

_log ("[stop_pipeline] targets: python={0} cmd_tabs={1}" -f ($pyTargets.Count | ForEach-Object { $_ }), ($cmdTargets.Count | ForEach-Object { $_ }))

if ((-not $pyTargets -or $pyTargets.Count -eq 0) -and (-not $cmdTargets -or $cmdTargets.Count -eq 0)) {
  _log "[stop_pipeline] No matching Windows processes found."
} else {
  foreach ($p in $pyTargets) {
    $targetPid = [int]$p.ProcessId
    $name = ($p.Name | ForEach-Object { $_ }) -join ""
    $cmd = ($p.CommandLine | ForEach-Object { $_ }) -join ""
    if ($cmd.Length -gt 160) { $cmd = $cmd.Substring(0, 160) + "..." }
    _log ("[stop_pipeline] taskkill PID={0} Name={1} Cmd={2}" -f $targetPid, $name, $cmd)
    if ($Soft) {
      & taskkill.exe /PID $targetPid 2>$null | Out-Null
    } else {
      & taskkill.exe /PID $targetPid /F 2>$null | Out-Null
    }
  }

  foreach ($p in $cmdTargets) {
    $targetPid = [int]$p.ProcessId
    $name = ($p.Name | ForEach-Object { $_ }) -join ""
    $cmd = ($p.CommandLine | ForEach-Object { $_ }) -join ""
    if ($cmd.Length -gt 160) { $cmd = $cmd.Substring(0, 160) + "..." }
    _log ("[stop_pipeline] taskkill PID={0} Name={1} Cmd={2}" -f $targetPid, $name, $cmd)
    if ($Soft) {
      & taskkill.exe /PID $targetPid 2>$null | Out-Null
    } else {
      & taskkill.exe /PID $targetPid /F 2>$null | Out-Null
    }
  }
}

# Stop SITL inside WSL (safe if SITL isn't running).
try {
  _log "[stop_pipeline] Stopping SITL in WSL (pkill arducopter)..."
  # Avoid PowerShell pipelines with wsl.exe (WSL rejects redirected stdin).
  & wsl.exe -e pkill -9 -f arducopter > $null 2>&1
} catch {
  _log "[stop_pipeline] WSL not available (skipping SITL stop)."
}

_log "[stop_pipeline] Done."
exit 0
