param(
  [string]$ProjectRoot = ""
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

$venvActivate = Join-Path $ProjectRoot "venv\\Scripts\\activate.bat"
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

$teeCapLines = _read_int_env "PORCE_TEE_CAP_LINES" 200
$brainPrefix = _read_text_env "PORCE_TEE_PREFIX_BRAIN" "BRAIN"
$eyesPrefix = _read_text_env "PORCE_TEE_PREFIX_EYES" "EYES"
$forceCmdWindows = _read_bool_env "PORCE_FORCE_CMD_WINDOWS" $false

function _cdPipe([string]$cmd) {
  return "cd /d $pipelineDir && $pyenv$cmd"
}

$brainTitle = "BRAIN (SIM)"
$eyesTitle  = "EYES (SIM)"

$masterCmd = _cdPipe "python -u log_server.py"
$sitlCmd   = _cdPipe ("wsl --cd `"$pipelineDir`" --exec bash run_sitl.sh 2>&1 | python tee.py --prefix `"SITL`" --cap-lines $teeCapLines")
$brainCmd  = "set PORCE_SYSTEM_MODE=SIMULATION && " + (_cdPipe "python -u flight_controller.py 2>&1 | python tee.py --prefix `"$brainPrefix`" --cap-lines $teeCapLines")
$eyesCmd   = "set PORCE_SYSTEM_MODE=SIMULATION && set PORCE_VISION_DEBUG_WINDOW=1 && set PORCE_VISION_DEBUG_DOCK=1 && " + (_cdPipe "python -u vision_system.py 2>&1 | python tee.py --prefix `"$eyesPrefix`" --cap-lines $teeCapLines")
$vizCmd    = _cdPipe ("python -u viz_recorder.py 2>&1 | python tee.py --prefix `"VIZ`" --cap-lines $teeCapLines")

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
      "cd /d $pipelineDir",
      $cmd
    ) | Set-Content -Path $tmpFile -Encoding UTF8

    Start-Process -FilePath "cmd.exe" -ArgumentList @('/k', "`"$tmpFile`"") -WindowStyle Normal | Out-Null
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
    _start_wt_tab "new" "MASTER LOG" $masterCmd
    Start-Sleep -Milliseconds 250
    _start_wt_tab "last" "SITL (WSL)" $sitlCmd
    _start_wt_tab "last" $brainTitle $brainCmd
    _start_wt_tab "last" $eyesTitle $eyesCmd
    _start_wt_tab "last" "VIZ RECORDER" $vizCmd
    return $true
  } catch {
    Write-Host "[launch_tabs] WARN: WT launch failed: $($_.Exception.Message)" -ForegroundColor Yellow
    return $false
  }
}

function _start_fallback_all() {
  $ok = $true
  $ok = (_start_fallback_tab "MASTER LOG" $masterCmd) -and $ok
  $ok = (_start_fallback_tab "SITL (WSL)" $sitlCmd) -and $ok
  $ok = (_start_fallback_tab $brainTitle $brainCmd) -and $ok
  $ok = (_start_fallback_tab $eyesTitle $eyesCmd) -and $ok
  $ok = (_start_fallback_tab "VIZ RECORDER" $vizCmd) -and $ok
  return $ok
}

function _invoke_wt([string[]]$wtCliArgs) {
  & $wt @wtCliArgs | Out-Null
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "wt.exe exited with code $exitCode"
  }
}

function _start_wt_tab([string]$windowTarget, [string]$title, [string]$cmd) {
  $wtCliArgs = @(
    "-w", $windowTarget,
    "new-tab", "--title", $title,
    "cmd", "/k", $cmd
  )
  _invoke_wt $wtCliArgs
}

if ($forceCmdWindows) {
  Write-Host "[launch_tabs] INFO: PORCE_FORCE_CMD_WINDOWS=1 -> forcing cmd fallback tabs."
  if (-not (_start_fallback_all)) {
    _fail "fallback tab creation failed"
  }
} elseif (-not (_start_with_tabs)) {
  Write-Host "[launch_tabs] WARN: Falling back to cmd tabs." -ForegroundColor Yellow
  if (-not (_start_fallback_all)) {
    _fail "fallback tab creation failed"
  }
}
