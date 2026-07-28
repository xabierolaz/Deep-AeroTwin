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

$uprojectPath = Join-Path $RepoRoot "..\Unreal\AirTraffic.uproject"
$scriptPath = Join-Path $RepoRoot "..\Unreal\Scripts\create_sppa_per_instance_material.py"
$reportPath = Join-Path $RepoRoot "pipeline\logs\sppa_per_instance_material_latest.json"
$enginePaths = Get-PorceUnrealEnginePaths -EngineRoot $EngineRoot
$ueCmd = $enginePaths.UnrealEditorCmd

if (-not $LogPath) {
  $LogPath = Join-Path $RepoRoot "pipeline\logs\sppa_per_instance_material_latest.log"
}

if (-not (Test-Path $uprojectPath)) {
  throw "Missing Unreal project: $uprojectPath"
}
if (-not (Test-Path $scriptPath)) {
  throw "Missing Unreal script: $scriptPath"
}
if (-not (Test-Path $ueCmd)) {
  throw "Missing UnrealEditor-Cmd.exe: $ueCmd"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
if (Test-Path $reportPath) {
  Remove-Item -LiteralPath $reportPath -Force
}

Write-Host "[sppa_material] Creating/verifying SPPA per-instance material..."
Write-Host "[sppa_material] Engine: $($enginePaths.Root)"
Write-Host "[sppa_material] Log: $LogPath"
Write-Host "[sppa_material] Report: $reportPath"
& $ueCmd $uprojectPath -run=pythonscript "-script=$scriptPath" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > $LogPath 2>&1
$exitCode = $LASTEXITCODE

$logText = ""
if (Test-Path $LogPath) {
  $logText = Get-Content $LogPath -Raw
}

if ($logText -notmatch 'SPPA_PER_INSTANCE_MATERIAL_OK') {
  Write-Host "[sppa_material] FAILED" -ForegroundColor Red
  if (Test-Path $LogPath) {
    Get-Content $LogPath -Tail 100
  }
  if ($exitCode -ne 0) {
    exit $exitCode
  }
  exit 5
}

if (-not (Test-Path $reportPath)) {
  Write-Host "[sppa_material] ERROR: Script did not write report: $reportPath" -ForegroundColor Red
  exit 6
}

$report = Get-Content $reportPath -Raw | ConvertFrom-Json
if (-not [bool]$report.ok) {
  Write-Host "[sppa_material] ERROR: Report JSON has ok=false" -ForegroundColor Red
  exit 6
}

Write-Host "[sppa_material] PASSED" -ForegroundColor Green
exit 0
