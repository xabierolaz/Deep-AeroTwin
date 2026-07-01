param(
  [string]$RepoRoot = "",
  [string]$EngineRoot = "",
  [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "unreal_engine_paths.ps1")

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$uprojectPath = Join-Path $RepoRoot "Unreal\AirTraffic.uproject"
$scriptPath = Join-Path $RepoRoot "Unreal\Scripts\verify_sppa_backend.py"
$enginePaths = $null
try {
  $enginePaths = Get-PorceUnrealEnginePaths -EngineRoot $EngineRoot
} catch {
  Write-Host "[verify_sppa] ERROR: $($_.Exception.Message)" -ForegroundColor Red
  exit 4
}
$ueCmd = $enginePaths.UnrealEditorCmd

if (-not $LogPath) {
  $LogPath = Join-Path $RepoRoot "pipeline\logs\sppa_backend_verify_latest.log"
}

if (-not (Test-Path $uprojectPath)) {
  Write-Host "[verify_sppa] ERROR: Missing Unreal project: $uprojectPath" -ForegroundColor Red
  exit 2
}
if (-not (Test-Path $scriptPath)) {
  Write-Host "[verify_sppa] ERROR: Missing Unreal script: $scriptPath" -ForegroundColor Red
  exit 3
}
if (-not (Test-Path $ueCmd)) {
  Write-Host "[verify_sppa] ERROR: Missing UnrealEditor-Cmd.exe: $ueCmd" -ForegroundColor Red
  exit 4
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

Write-Host "[verify_sppa] Running Unreal reflection smoke..."
Write-Host "[verify_sppa] Engine: $($enginePaths.Root)"
Write-Host "[verify_sppa] Log: $LogPath"
& $ueCmd $uprojectPath -run=pythonscript "-script=$scriptPath" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > $LogPath 2>&1
$exitCode = $LASTEXITCODE

$logText = ""
if (Test-Path $LogPath) {
  $logText = Get-Content $LogPath -Raw
}

if ($exitCode -ne 0 -or $logText -notmatch 'SPPA_BACKEND_VERIFY_OK') {
  Write-Host "[verify_sppa] FAILED" -ForegroundColor Red
  if (Test-Path $LogPath) {
    Get-Content $LogPath -Tail 80
  }
  if ($exitCode -ne 0) {
    exit $exitCode
  }
  exit 5
}

Write-Host "[verify_sppa] PASSED" -ForegroundColor Green
exit 0
