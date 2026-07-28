param(
  [string]$ProjectRoot = "",
  [string]$Workflow = ""
)

$ErrorActionPreference = "Stop"

function _fail([string]$msg, [int]$code = 1) {
  Write-Host "[launch_tabs] ERROR: $msg" -ForegroundColor Red
  exit $code
}

if (-not $ProjectRoot) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$pipelineDir = Join-Path $ProjectRoot "pipeline"
if (-not (Test-Path $pipelineDir)) {
  _fail "pipeline dir not found at: $pipelineDir"
}

# Resolve Windows Terminal (wt.exe). In cmd.exe, app-execution-alias files may fail `if exist`,
# so we do this lookup in PowerShell.
$wt = $null
try {
  $wt = (Get-Command wt.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
} catch {
  $wt = $null
}
if (-not $wt) {
  $candidate = Join-Path $env:LOCALAPPDATA "Microsoft\\WindowsApps\\wt.exe"
  if (Test-Path $candidate) {
    $wt = $candidate
  }
}
if (-not $wt) {
  Write-Host "[launch_tabs] WARN: Windows Terminal (wt.exe) not available or not invocable." -ForegroundColor Yellow
}

$venvActivate = Join-Path $ProjectRoot "..\venv\\Scripts\\activate.bat"
$pyenv = ""
if (Test-Path $venvActivate) {
  $pyenv = "call `"$venvActivate`" && "
} else {
  Write-Host "[launch_tabs] WARN: venv not found at: $venvActivate (using system python)"
}

function _read_int_env([string]$name, [int]$default) {
  $raw = [System.Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $default
  }
  try {
    $value = [int]$raw
    if ($value -lt 0) {
      return $default
    }
    return $value
  } catch {
    return $default
  }
}

function _read_text_env([string]$name, [string]$default) {
  $raw = [System.Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $default
  }
  return $raw
}

function _read_bool_env([string]$name, [bool]$default) {
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

$workflowRaw = $Workflow
if ([string]::IsNullOrWhiteSpace($workflowRaw)) {
  $workflowRaw = [System.Environment]::GetEnvironmentVariable("PORCE_SYSTEM_MODE")
}
if ([string]::IsNullOrWhiteSpace($workflowRaw)) {
  $workflowRaw = "SIMULATION"
}
$workflowKey = $workflowRaw.Trim().ToUpperInvariant()
if ($workflowKey -notin @("SIMULATION", "REAL_TWIN")) {
  _fail "unsupported workflow: $workflowRaw"
}
$isRealTwin = $workflowKey -eq "REAL_TWIN"

$teeCapLines = _read_int_env "PORCE_TEE_CAP_LINES" 200
$brainPrefixDefault = if ($isRealTwin) { "BRAIN-TWIN" } else { "BRAIN" }
$brainPrefix = _read_text_env "PORCE_TEE_PREFIX_BRAIN" $brainPrefixDefault
$eyesPrefix = _read_text_env "PORCE_TEE_PREFIX_EYES" "EYES"
$forceCmdWindows = _read_bool_env "PORCE_FORCE_CMD_WINDOWS" $false
$allowCmdFallback = _read_bool_env "PORCE_ALLOW_CMD_WINDOWS_FALLBACK" $false
$keepTerminalOpen = _read_bool_env "PORCE_TERMINAL_KEEP_OPEN" $false
$cmdExitSwitch = if ($keepTerminalOpen) { "/k" } else { "/c" }
$windowTarget = _read_text_env "PORCE_WT_WINDOW" "DeepAeroTwinPORCE"
$dryRun = _read_bool_env "PORCE_LAUNCH_TABS_DRY_RUN" $false

function _cdPipe([string]$cmd) {
  return "cd /d `"$pipelineDir`" && $pyenv$cmd"
}

$masterCmd = _cdPipe "python -u log_server.py"
$tabSpecs = @(
  @{
    Title = "MASTER LOG"
    Cmd = $masterCmd
  }
)

if ($isRealTwin) {
  $brainTitle = "BRAIN (REAL_TWIN)"
  $brainCmd = "set PORCE_SYSTEM_MODE=REAL_TWIN && " + (_cdPipe "python -u flight_controller.py 2>&1 | python tee.py --prefix `"$brainPrefix`" --cap-lines $teeCapLines")
  $tabSpecs += @{
    Title = $brainTitle
    Cmd = $brainCmd
  }
} else {
  $brainTitle = "BRAIN (SIM)"
  $eyesTitle = "EYES (SIM)"
  $sitlCmd = _cdPipe ("python -u sitl_runner.py --prefix `"SITL`" --cap-lines $teeCapLines")
  $brainCmd = "set PORCE_SYSTEM_MODE=SIMULATION && " + (_cdPipe "python -u flight_controller.py 2>&1 | python tee.py --prefix `"$brainPrefix`" --cap-lines $teeCapLines")
  $eyesCmd = "set PORCE_SYSTEM_MODE=SIMULATION && " + (_cdPipe "python -u vision_system.py 2>&1 | python tee.py --prefix `"$eyesPrefix`" --cap-lines $teeCapLines")
  $vizCmd = _cdPipe ("python -u viz_recorder.py 2>&1 | python tee.py --prefix `"VIZ`" --cap-lines $teeCapLines")
  $tabSpecs += @(
    @{
      Title = "SITL (WSL)"
      Cmd = $sitlCmd
    },
    @{
      Title = $brainTitle
      Cmd = $brainCmd
    },
    @{
      Title = $eyesTitle
      Cmd = $eyesCmd
    },
    @{
      Title = "VIZ RECORDER"
      Cmd = $vizCmd
    }
  )
}

if ($dryRun) {
  Write-Host ("[launch_tabs] DRY-RUN workflow={0} window={1} keep_open={2} tabs={3}" -f $workflowKey, $windowTarget, $keepTerminalOpen, $tabSpecs.Count)
  foreach ($tab in $tabSpecs) {
    Write-Host ("[launch_tabs] DRY-RUN tab: {0}" -f $tab.Title)
  }
  exit 0
}

function _start_fallback_tab([string]$title, [string]$cmd) {
  $safeTitle = $title -replace '"', ''
  try {
    $safeTitle = if ([string]::IsNullOrWhiteSpace($safeTitle)) { "PORCE" } else { $safeTitle }
    Write-Host "[launch_tabs] INFO: launching fallback tab '$safeTitle'."
    $tmpName = "porce_tab_" + [System.Guid]::NewGuid().ToString("N") + ".bat"
    $tmpFile = Join-Path $env:TEMP $tmpName
    @(
      "@echo off",
      "title `"$safeTitle`"",
      "cd /d `"$pipelineDir`"",
      $cmd
    ) | Set-Content -Path $tmpFile -Encoding UTF8

    Start-Process -FilePath "cmd.exe" -ArgumentList @($cmdExitSwitch, "`"$tmpFile`"") -WindowStyle Normal | Out-Null
    return $true
  } catch {
    Write-Host "[launch_tabs] WARN: fallback tab creation failed for '$safeTitle': $($_.Exception.Message)" -ForegroundColor Yellow
    return $false
  }
}

function _start_with_tabs() {
  if (-not $wt) {
    return $false
  }
  try {
    $wtCliArgs = @("-w", $windowTarget)
    $isFirst = $true
    foreach ($tab in $tabSpecs) {
      if (-not $isFirst) {
        $wtCliArgs += ";"
      }
      $wtCliArgs += @(
        "new-tab", "--title", $tab.Title,
        "cmd", $cmdExitSwitch, $tab.Cmd
      )
      $isFirst = $false
    }
    _invoke_wt $wtCliArgs
    return $true
  } catch {
    Write-Host "[launch_tabs] WARN: WT launch failed: $($_.Exception.Message)" -ForegroundColor Yellow
    return $false
  }
}

function _start_fallback_all() {
  $ok = $true
  foreach ($tab in $tabSpecs) {
    $ok = (_start_fallback_tab $tab.Title $tab.Cmd) -and $ok
  }
  return $ok
}

function _invoke_wt([string[]]$wtCliArgs) {
  $tmpName = "porce_wt_" + [System.Guid]::NewGuid().ToString("N") + ".ps1"
  $tmpFile = Join-Path $env:TEMP $tmpName
  function _ps_quote([string]$text) {
    return "'" + ($text -replace "'", "''") + "'"
  }

  $lines = @()
  $lines += "`$wt = $(_ps_quote $wt)"
  $lines += "`$wtArgs = @("
  foreach ($arg in $wtCliArgs) {
    $lines += "  $(_ps_quote $arg)"
  }
  $lines += ")"
  $lines += "& `$wt @wtArgs"
  $lines += "exit `$LASTEXITCODE"
  $lines | Set-Content -Path $tmpFile -Encoding UTF8

  try {
    $proc = Start-Process -FilePath "powershell.exe" `
      -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $tmpFile) `
      -WindowStyle Hidden `
      -Wait `
      -PassThru
    if ($proc -and $proc.ExitCode -ne 0) {
      throw "wt launcher exited with code $($proc.ExitCode)"
    }
  } finally {
    Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
  }
}

if ($forceCmdWindows) {
  Write-Host "[launch_tabs] INFO: PORCE_FORCE_CMD_WINDOWS=1 -> forcing cmd fallback tabs."
  if (-not (_start_fallback_all)) {
    _fail "fallback tab creation failed"
  }
} elseif (-not (_start_with_tabs)) {
  if ($allowCmdFallback) {
    Write-Host "[launch_tabs] WARN: Falling back to separate cmd windows because PORCE_ALLOW_CMD_WINDOWS_FALLBACK=1." -ForegroundColor Yellow
    if (-not (_start_fallback_all)) {
      _fail "fallback tab creation failed"
    }
  } else {
    _fail "Windows Terminal tabs are required. Refusing to open separate cmd windows; set PORCE_ALLOW_CMD_WINDOWS_FALLBACK=1 only for emergency fallback."
  }
}
