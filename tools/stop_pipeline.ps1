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

$targets = @()
try {
  $targets = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match $regex) } |
    Sort-Object -Property ProcessId -Unique
} catch {
  $targets = @()
}

if (-not $targets -or $targets.Count -eq 0) {
  _log "[stop_pipeline] No matching Windows processes found."
} else {
  foreach ($p in $targets) {
    $pid = [int]$p.ProcessId
    $name = ($p.Name | ForEach-Object { $_ }) -join ""
    $cmd = ($p.CommandLine | ForEach-Object { $_ }) -join ""
    if ($cmd.Length -gt 160) { $cmd = $cmd.Substring(0, 160) + "..." }
    _log ("[stop_pipeline] taskkill PID={0} Name={1} Cmd={2}" -f $pid, $name, $cmd)
    if ($Soft) {
      & taskkill.exe /PID $pid /T | Out-Null
    } else {
      & taskkill.exe /PID $pid /T /F | Out-Null
    }
  }
}

# Stop SITL inside WSL (safe if SITL isn't running).
try {
  _log "[stop_pipeline] Stopping SITL in WSL (pkill arducopter)..."
  & wsl.exe -e pkill -9 -f arducopter | Out-Null
} catch {
  _log "[stop_pipeline] WSL not available (skipping SITL stop)."
}

_log "[stop_pipeline] Done."
exit 0

