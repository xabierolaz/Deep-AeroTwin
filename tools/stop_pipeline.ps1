param(
  [switch]$Soft,
  [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function _log([string]$msg) {
  if (-not $Quiet) {
    Write-Host $msg
  }
}

function _env_bool([string]$name, [bool]$default) {
  $raw = [System.Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $default
  }
  $normalized = $raw.Trim().ToLowerInvariant()
  if ($normalized -in @("1", "true", "yes", "on")) {
    return $true
  }
  if ($normalized -in @("0", "false", "no", "off")) {
    return $false
  }
  return $default
}

_log "[stop_pipeline] Stopping Deep-AeroTwin pipeline processes..."

# Match by command line so this works for:
# - separate cmd.exe windows started by launch.bat
# - Windows Terminal tabs (cmd.exe hosted by wt.exe)
$regex = '(?i)(flight_controller\.py|vision_system\.py|viz_recorder\.py|log_server\.py|tee\.py|sitl_runner\.py|run_sitl\.sh|sim_vehicle\.py|arducopter|mavproxy\.py|porce_tab_[0-9a-f]+\.bat)'
$terminalTitles = @(
  "MASTER LOG",
  "SITL (WSL)",
  "BRAIN (SIM)",
  "BRAIN (REAL_TWIN)",
  "EYES (SIM)",
  "VIZ RECORDER"
)

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

function _collect_targets() {
  $pyTargets = @()
  $cmdTargets = @()
  try {
    # Only kill python processes. Killing the hosting cmd.exe can kill this script
    # when run from inside a pipeline tab (taskkill /T tries to kill itself).
    $pyTargets = Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -and ($_.CommandLine -match $regex) } |
      Where-Object { $_.Name -and ($_.Name -imatch '^(python(?:3)?|pythonw|py)\.exe$') } |
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
  return @{
    py  = @($pyTargets)
    cmd = @($cmdTargets)
  }
}

function _is_pid_alive([int]$targetPid) {
  try {
    Get-Process -Id $targetPid -ErrorAction Stop | Out-Null
    return $true
  } catch {
    return $false
  }
}

function _kill_pid_once([int]$targetPid, [bool]$force) {
  if (-not (_is_pid_alive $targetPid)) {
    return $true
  }

  $args = @("/PID", "$targetPid")
  if ($force) {
    $args += "/F"
  }

  $taskkillOutput = @()
  try {
    $taskkillOutput = & taskkill.exe @args 2>&1
  } catch {}
  $taskkillExit = $LASTEXITCODE

  Start-Sleep -Milliseconds 150
  if (-not (_is_pid_alive $targetPid)) {
    return $true
  }

  # Fallback when taskkill fails silently (often AccessDenied/session edge cases).
  if ($force) {
    try {
      Stop-Process -Id $targetPid -Force -ErrorAction Stop
    } catch {}
    Start-Sleep -Milliseconds 100
    if (-not (_is_pid_alive $targetPid)) {
      return $true
    }
  }

  $msg = ("[stop_pipeline] WARN: PID={0} still alive after taskkill (exit={1})." -f $targetPid, $taskkillExit)
  if ($taskkillOutput) {
    $text = (($taskkillOutput | Out-String).Trim() -replace '\s+', ' ')
    if ($text.Length -gt 200) { $text = $text.Substring(0, 200) + "..." }
    if (-not [string]::IsNullOrWhiteSpace($text)) {
      $msg += " Output=" + $text
    }
  }
  _log $msg
  return $false
}

function _kill_targets([object[]]$targets, [bool]$force) {
  $remaining = 0
  foreach ($p in $targets) {
    $targetPid = [int]$p.ProcessId
    $name = ($p.Name | ForEach-Object { $_ }) -join ""
    $cmd = ($p.CommandLine | ForEach-Object { $_ }) -join ""
    if ($cmd.Length -gt 160) { $cmd = $cmd.Substring(0, 160) + "..." }
    _log ("[stop_pipeline] taskkill PID={0} Name={1} Cmd={2}" -f $targetPid, $name, $cmd)
    if (-not (_kill_pid_once $targetPid $force)) {
      $remaining += 1
    }
  }
  return $remaining
}

function _port_owner_matches_pipeline([int]$ownerPid, [int]$port = 0) {
  try {
    $proc = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ownerPid)
    if (-not $proc) { return $false }
    $name = ($proc.Name | ForEach-Object { $_ }) -join ""
    $cmd = ($proc.CommandLine | ForEach-Object { $_ }) -join ""
    if ($cmd -and ($cmd -match $regex)) { return $true }
    if ($name -imatch '^wsl\.exe$' -and $cmd -and ($cmd -match '(?i)(run_sitl\.sh|sim_vehicle\.py|arducopter|mavproxy\.py)')) { return $true }
  } catch {}
  return $false
}

function _cleanup_pipeline_ports([bool]$force) {
  $ports = @(8080, 9090, 5760, 5762, 5763)
  try {
    $hits = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
      Where-Object { $ports -contains [int]$_.LocalPort } |
      Sort-Object -Property LocalPort, OwningProcess -Unique
    if (-not $hits -or $hits.Count -eq 0) {
      return
    }
    $pipelineHits = @($hits | Where-Object { _port_owner_matches_pipeline ([int]$_.OwningProcess) ([int]$_.LocalPort) })
    if ($pipelineHits.Count -eq 0) {
      return
    }
    foreach ($h in $pipelineHits) {
      $ownerPid = [int]$h.OwningProcess
      _log ("[stop_pipeline] WARN: pipeline listener still alive port={0} pid={1}" -f ([int]$h.LocalPort), $ownerPid)
      if ($force -and $ownerPid -ne $PID -and (-not $parentPid -or $ownerPid -ne $parentPid)) {
        [void](_kill_pid_once $ownerPid $true)
      }
    }
  } catch {
    # Optional check; do not fail stop path on systems without NetTCP APIs.
  }
}

function _report_persistent_portproxy_rules() {
  try {
    $output = & netsh.exe interface portproxy show all 2>$null
    if (-not $output) {
      return
    }
    $hits = @($output | Where-Object { $_ -match '^\s*127\.0\.0\.1\s+(5760|5762)\s+' })
    foreach ($line in $hits) {
      _log ("[stop_pipeline] WARN: persistent netsh portproxy rule remains: {0}" -f ($line.Trim() -replace '\s+', ' '))
    }
    if ($hits.Count -gt 0) {
      _log "[stop_pipeline] WARN: remove these from an elevated shell with:"
      _log "  netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=5760"
      _log "  netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=5762"
    }
  } catch {}
}

function _stop_unreal_pie() {
  if (-not (_env_bool "PORCE_STOP_UNREAL_PIE_ON_STOP" $true)) {
    return
  }

  $mcpScript = Join-Path $RepoRoot "tools\unreal_mcp_call.py"
  if (-not (Test-Path $mcpScript)) {
    return
  }

  $pythonExe = Join-Path $RepoRoot "venv\Scripts\python.exe"
  if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
  }

  try {
    & $pythonExe $mcpScript control_editor "{}" --arg action=stop --timeout 5 > $null 2> $null
    if ($LASTEXITCODE -eq 0) {
      _log "[stop_pipeline] Unreal PIE stopped via MCP."
    }
  } catch {}
}

function _cleanup_terminal_windows([bool]$force) {
  $targets = @()
  try {
    $targets = Get-Process WindowsTerminal -ErrorAction SilentlyContinue |
      Where-Object { $_.MainWindowTitle -and ($terminalTitles -contains $_.MainWindowTitle) } |
      Sort-Object -Property Id -Unique
  } catch {
    $targets = @()
  }

  if (-not $targets -or $targets.Count -eq 0) {
    return
  }

  foreach ($p in $targets) {
    _log ("[stop_pipeline] closing WindowsTerminal PID={0} Title={1}" -f $p.Id, $p.MainWindowTitle)
    try {
      [void]$p.CloseMainWindow()
    } catch {}
  }

  Start-Sleep -Milliseconds 500
  foreach ($p in $targets) {
    try {
      $alive = Get-Process -Id $p.Id -ErrorAction Stop
      if ($force -and $alive) {
        _log ("[stop_pipeline] force-closing WindowsTerminal PID={0} Title={1}" -f $p.Id, $p.MainWindowTitle)
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      }
    } catch {}
  }
}

$targets = _collect_targets
$pyTargets = @($targets.py)
$cmdTargets = @($targets.cmd)
$forceKill = (-not $Soft)

_log ("[stop_pipeline] targets: python={0} cmd_tabs={1}" -f ($pyTargets.Count | ForEach-Object { $_ }), ($cmdTargets.Count | ForEach-Object { $_ }))

if ((-not $pyTargets -or $pyTargets.Count -eq 0) -and (-not $cmdTargets -or $cmdTargets.Count -eq 0)) {
  _log "[stop_pipeline] No matching Windows processes found."
} else {
  $remaining = 0
  $remaining += _kill_targets $pyTargets $forceKill
  $remaining += _kill_targets $cmdTargets $forceKill

  # One extra sweep to catch stragglers created during teardown.
  Start-Sleep -Milliseconds 250
  $after = _collect_targets
  $afterCount = @($after.py).Count + @($after.cmd).Count
  if ($afterCount -gt 0 -and $forceKill) {
    _log ("[stop_pipeline] second_sweep targets={0}" -f $afterCount)
    $remaining += _kill_targets @($after.py) $true
    $remaining += _kill_targets @($after.cmd) $true
  }
  if ($remaining -gt 0) {
    _log ("[stop_pipeline] WARN: lingering Windows targets after kill attempts: {0}" -f $remaining)
  }
}

# Stop SITL inside WSL (safe if SITL isn't running).
$wslHealthy = $true
try {
  & wsl.exe -e sh -lc "echo WSL_OK" > $null 2>&1
  if ($LASTEXITCODE -ne 0) {
    $wslHealthy = $false
  }
} catch {
  $wslHealthy = $false
}

if ($wslHealthy) {
  try {
    _log "[stop_pipeline] Stopping SITL in WSL (pkill arducopter/sim_vehicle/mavproxy)..."
    # Avoid PowerShell pipelines with wsl.exe (WSL rejects redirected stdin).
    & wsl.exe -e pkill -9 -f arducopter > $null 2>&1
    & wsl.exe -e pkill -9 -f sim_vehicle.py > $null 2>&1
    & wsl.exe -e pkill -9 -f mavproxy.py > $null 2>&1
  } catch {
    _log "[stop_pipeline] WSL stop command failed."
  }
} else {
  _log "[stop_pipeline] WSL unhealthy (skipping SITL stop)."
  $recoverRaw = [System.Environment]::GetEnvironmentVariable("PORCE_WSL_AUTO_RECOVER_ON_STOP")
  $recover = $false
  if (-not [string]::IsNullOrWhiteSpace($recoverRaw)) {
    $recover = @("1", "true", "yes", "on") -contains $recoverRaw.Trim().ToLowerInvariant()
  }
  if ($recover) {
    _log "[stop_pipeline] Trying WSL recover with wsl --shutdown..."
    try {
      & wsl.exe --shutdown > $null 2>&1
    } catch {}
  }
}

_cleanup_pipeline_ports $forceKill
_cleanup_terminal_windows $forceKill
_stop_unreal_pie
_report_persistent_portproxy_rules

try {
  $removedTempTabs = 0
  @("porce_tab_*.bat", "porce_wt_*.ps1") | ForEach-Object {
    $filter = $_
    Get-ChildItem -Path $env:TEMP -Filter $filter -File -ErrorAction SilentlyContinue
  } | ForEach-Object {
    try {
      Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
      $removedTempTabs += 1
    } catch {}
  }
  if ($removedTempTabs -gt 0) {
    _log ("[stop_pipeline] Removed stale temp tab launchers: {0}" -f $removedTempTabs)
  }
} catch {}

_log "[stop_pipeline] Done."
exit 0
