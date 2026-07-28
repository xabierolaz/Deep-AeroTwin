param(
  [string]$RepoRoot = "",
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Fail([string]$message, [int]$code = 1) {
  Write-Host "[build_sitl_wsl] ERROR: $message" -ForegroundColor Red
  exit $code
}

function Step([string]$message) {
  Write-Host "[build_sitl_wsl] $message"
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$ardupilotDir = Join-Path $RepoRoot "ardupilot"
$sitlBinary = Join-Path $ardupilotDir "build\sitl\bin\arducopter"

if (-not (Test-Path $ardupilotDir)) {
  Fail "ardupilot directory not found: $ardupilotDir"
}

Step "Checking WSL health..."
& wsl.exe -e sh -lc "echo WSL_OK" > $null 2>&1
if ($LASTEXITCODE -ne 0) {
  Fail "WSL is not healthy. Try: wsl --shutdown"
}

$ardupilotWslPath = (& wsl.exe -e wslpath -a $ardupilotDir 2>$null | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($ardupilotWslPath)) {
  Fail "Could not resolve WSL path for $ardupilotDir"
}

$buildSteps = @(
  "set -euo pipefail",
  "cd '$ardupilotWslPath'"
)
if ($Clean) {
  $buildSteps += "./waf clean || true"
}
$buildSteps += "./waf configure --board sitl"
$buildSteps += "./waf copter"
$buildCmd = ($buildSteps -join "; ")

Step "Running SITL build in WSL..."
& wsl.exe -e bash -lc $buildCmd
if ($LASTEXITCODE -ne 0) {
  Fail "SITL build command failed."
}

if (-not (Test-Path $sitlBinary)) {
  Fail "Build finished but binary not found: $sitlBinary"
}

Step "SITL binary ready: $sitlBinary"
