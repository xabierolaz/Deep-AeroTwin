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
$scriptPath = Join-Path $RepoRoot "..\Unreal\Scripts\verify_sppa_backend.py"
$reportPath = Join-Path $RepoRoot "pipeline\logs\sppa_backend_verify_latest.json"
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
if (Test-Path $reportPath) {
  Remove-Item -LiteralPath $reportPath -Force
}

Write-Host "[verify_sppa] Running Unreal reflection smoke..."
Write-Host "[verify_sppa] Engine: $($enginePaths.Root)"
Write-Host "[verify_sppa] Log: $LogPath"
Write-Host "[verify_sppa] Report: $reportPath"
& $ueCmd $uprojectPath -run=pythonscript "-script=$scriptPath" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > $LogPath 2>&1
$exitCode = $LASTEXITCODE

$logText = ""
if (Test-Path $LogPath) {
  $logText = Get-Content $LogPath -Raw
}

if ($logText -notmatch 'SPPA_BACKEND_VERIFY_OK') {
  Write-Host "[verify_sppa] FAILED" -ForegroundColor Red
  if (Test-Path $LogPath) {
    Get-Content $LogPath -Tail 80
  }
  if ($exitCode -ne 0) {
    exit $exitCode
  }
  exit 5
}

if ($exitCode -ne 0) {
  Write-Host "[verify_sppa] WARNING: UnrealEditor-Cmd returned exit code $exitCode after writing SPPA_BACKEND_VERIFY_OK; validating JSON report." -ForegroundColor Yellow
}

if (-not (Test-Path $reportPath)) {
  Write-Host "[verify_sppa] ERROR: Unreal smoke did not write report: $reportPath" -ForegroundColor Red
  exit 6
}

try {
  $report = Get-Content $reportPath -Raw | ConvertFrom-Json
} catch {
  Write-Host "[verify_sppa] ERROR: Could not parse report JSON: $reportPath" -ForegroundColor Red
  Write-Host "[verify_sppa] ERROR: $($_.Exception.Message)" -ForegroundColor Red
  exit 6
}

if (-not [bool]$report.ok) {
  Write-Host "[verify_sppa] ERROR: Report JSON has ok=false" -ForegroundColor Red
  if ($report.failures) {
    @($report.failures) | ForEach-Object { Write-Host "[verify_sppa] ERROR: $_" -ForegroundColor Red }
  }
  exit 6
}

foreach ($section in @(
  "backend_enum_values",
  "component_defaults",
  "component_methods",
  "component_properties",
  "component_switch",
  "per_instance_material_asset",
  "proxy_descriptor_ingestion",
  "proxy_generation",
  "proxy_reconfigure",
  "proxy_unknown_fallback",
  "instanced_batch",
  "instanced_batch_methods",
  "proxy_methods",
  "proxy_properties"
)) {
  if ($report.PSObject.Properties.Name -notcontains $section) {
    Write-Host "[verify_sppa] ERROR: Report JSON missing section: $section" -ForegroundColor Red
    exit 6
  }
}

Write-Host "[verify_sppa] PASSED" -ForegroundColor Green
exit 0
