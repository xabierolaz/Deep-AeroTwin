param(
  [string]$RepoRoot = "",
  [string]$EngineRoot = "",
  [string]$OutDir = "",
  [string]$Counts = "10,50,100",
  [int]$Repetitions = 3,
  [int]$UpdatesPerActor = 5,
  [switch]$SkipBuild,
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
$scriptPath = Join-Path $RepoRoot "..\Unreal\Scripts\benchmark_sppa_descriptor_backend.py"
$enginePaths = Get-PorceUnrealEnginePaths -EngineRoot $EngineRoot
$ueCmd = $enginePaths.UnrealEditorCmd
$buildBat = Join-Path $enginePaths.Root "Engine\Build\BatchFiles\Build.bat"

if (-not (Test-Path $uprojectPath)) {
  Write-Host "[sppa_unreal_bench] ERROR: Missing Unreal project: $uprojectPath" -ForegroundColor Red
  exit 2
}
if (-not (Test-Path $scriptPath)) {
  Write-Host "[sppa_unreal_bench] ERROR: Missing benchmark script: $scriptPath" -ForegroundColor Red
  exit 3
}
if (-not (Test-Path $ueCmd)) {
  Write-Host "[sppa_unreal_bench] ERROR: Missing UnrealEditor-Cmd.exe: $ueCmd" -ForegroundColor Red
  exit 4
}

if (-not $OutDir) {
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
  $OutDir = Join-Path $RepoRoot "..\papers\semantic_proxy_3d\experiments_root\sppa_unreal_backend\${stamp}_editor_actor_microbenchmark"
}
$OutDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDir)

if (Test-Path $OutDir) {
  $existing = Get-ChildItem -LiteralPath $OutDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($existing) {
    Write-Host "[sppa_unreal_bench] ERROR: Output directory is non-empty: $OutDir" -ForegroundColor Red
    exit 5
  }
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not $LogPath) {
  $LogPath = Join-Path $OutDir "unreal_actor_microbenchmark.log"
}

if (-not $SkipBuild) {
  if (-not (Test-Path $buildBat)) {
    Write-Host "[sppa_unreal_bench] ERROR: Missing Build.bat: $buildBat" -ForegroundColor Red
    exit 6
  }
  Write-Host "[sppa_unreal_bench] Building AirTrafficEditor..."
  & $buildBat AirTrafficEditor Win64 Development "-Project=$uprojectPath" -WaitMutex -FromMsBuild
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$oldOut = $env:PORCE_SPPA_UNREAL_BENCH_OUT_DIR
$oldCounts = $env:PORCE_SPPA_UNREAL_BENCH_COUNTS
$oldRepetitions = $env:PORCE_SPPA_UNREAL_BENCH_REPETITIONS
$oldUpdates = $env:PORCE_SPPA_UNREAL_BENCH_UPDATES
try {
  $env:PORCE_SPPA_UNREAL_BENCH_OUT_DIR = $OutDir
  $env:PORCE_SPPA_UNREAL_BENCH_COUNTS = $Counts
  $env:PORCE_SPPA_UNREAL_BENCH_REPETITIONS = [string]$Repetitions
  $env:PORCE_SPPA_UNREAL_BENCH_UPDATES = [string]$UpdatesPerActor

  Write-Host "[sppa_unreal_bench] Running Editor-Cmd actor microbenchmark..."
  Write-Host "[sppa_unreal_bench] Engine: $($enginePaths.Root)"
  Write-Host "[sppa_unreal_bench] OutDir: $OutDir"
  Write-Host "[sppa_unreal_bench] Counts: $Counts Repetitions: $Repetitions UpdatesPerActor: $UpdatesPerActor"
  & $ueCmd $uprojectPath -run=pythonscript "-script=$scriptPath" -unattended -nop4 -nosplash -stdout -FullStdOutLogOutput > $LogPath 2>&1
  $exitCode = $LASTEXITCODE
} finally {
  $env:PORCE_SPPA_UNREAL_BENCH_OUT_DIR = $oldOut
  $env:PORCE_SPPA_UNREAL_BENCH_COUNTS = $oldCounts
  $env:PORCE_SPPA_UNREAL_BENCH_REPETITIONS = $oldRepetitions
  $env:PORCE_SPPA_UNREAL_BENCH_UPDATES = $oldUpdates
}

$logText = ""
if (Test-Path $LogPath) {
  $logText = Get-Content $LogPath -Raw
}

if ($exitCode -ne 0 -or $logText -notmatch 'SPPA_UNREAL_BACKEND_BENCHMARK_OK') {
  Write-Host "[sppa_unreal_bench] FAILED" -ForegroundColor Red
  if (Test-Path $LogPath) {
    Get-Content $LogPath -Tail 120
  }
  if ($exitCode -ne 0) {
    exit $exitCode
  }
  exit 7
}

$manifestPath = Join-Path $OutDir "run_manifest.json"
if (-not (Test-Path $manifestPath)) {
  Write-Host "[sppa_unreal_bench] ERROR: Missing manifest: $manifestPath" -ForegroundColor Red
  exit 8
}

try {
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
} catch {
  Write-Host "[sppa_unreal_bench] ERROR: Could not parse manifest: $($_.Exception.Message)" -ForegroundColor Red
  exit 8
}

if ($manifest.failures -and @($manifest.failures).Count -gt 0) {
  Write-Host "[sppa_unreal_bench] ERROR: Benchmark manifest contains failures" -ForegroundColor Red
  @($manifest.failures) | Select-Object -First 10 | ForEach-Object { Write-Host "[sppa_unreal_bench] ERROR: $_" -ForegroundColor Red }
  exit 9
}

Write-Host "[sppa_unreal_bench] PASSED" -ForegroundColor Green
Write-Host "[sppa_unreal_bench] Artifacts: $OutDir"
exit 0
