param(
  [string]$ProjectRoot = "",
  [ValidateSet("SIMULATION","REAL_TWIN")]
  [string]$Mode = ""
)

$ErrorActionPreference = "Stop"

function _fail([string]$msg, [int]$code = 1) {
  Write-Host "[launch_tabs] ERROR: $msg" -ForegroundColor Red
  exit $code
}

if (-not $ProjectRoot) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not $Mode) {
  $Mode = $env:PORCE_SYSTEM_MODE
}
if (-not $Mode) {
  $Mode = "SIMULATION"
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
  _fail "Windows Terminal (wt.exe) not found. Install Windows Terminal and retry." 2
}

$venvActivate = Join-Path $ProjectRoot "venv\\Scripts\\activate.bat"
$pyenv = ""
if (Test-Path $venvActivate) {
  $pyenv = "call `"$venvActivate`" && "
} else {
  Write-Host "[launch_tabs] WARN: venv not found at: $venvActivate (using system python)"
}

function _cdPipe([string]$cmd) {
  return "cd /d `"$pipelineDir`" && $pyenv$cmd"
}

$brainTitle = if ($Mode -eq "SIMULATION") { "BRAIN (SIM)" } else { "BRAIN (TWIN)" }
$eyesTitle  = if ($Mode -eq "SIMULATION") { "EYES (SIM)" } else { "EYES (TWIN)" }

$masterCmd = _cdPipe "python -u log_server.py"
$sitlCmd   = "wsl --cd `"$pipelineDir`" --exec bash run_sitl.sh"
$brainCmd  = "set PORCE_SYSTEM_MODE=$Mode && " + (_cdPipe "python -u flight_controller.py 2>&1 | python tee.py --prefix BRAIN --cap-lines 200")
$eyesCmd   = "set PORCE_SYSTEM_MODE=$Mode && " + (_cdPipe "python -u vision_system.py 2>&1 | python tee.py --prefix EYES --cap-lines 200")
$vizCmd    = _cdPipe "python -u viz_recorder.py"

$args = @(
  "new-tab","--title","MASTER LOG","cmd","/k",$masterCmd
)

if ($Mode -eq "SIMULATION") {
  $args += @(";", "new-tab","--title","SITL (WSL)","cmd","/k",$sitlCmd)
}

$args += @(
  ";","new-tab","--title",$brainTitle,"cmd","/k",$brainCmd,
  ";","new-tab","--title",$eyesTitle,"cmd","/k",$eyesCmd,
  ";","new-tab","--title","VIZ RECORDER","cmd","/k",$vizCmd
)

try {
  & $wt @args | Out-Null
  exit $LASTEXITCODE
} catch {
  _fail $_.Exception.Message
}

