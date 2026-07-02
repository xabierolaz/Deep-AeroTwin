param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$EngineRoot = "",
    [string]$OutDir = "",
    [string]$Counts = "10,50,100",
    [int]$Repetitions = 3,
    [int]$UpdatesPerActor = 5,
    [double]$TimeoutS = 2.0,
    [int]$Seed = 20260702,
    [switch]$SkipBuild,
    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\unreal_engine_paths.ps1"

$RepoRoot = (Resolve-Path $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($EngineRoot)) {
    $EngineRoot = Resolve-PorceUnrealEngineRoot
}
$EditorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$BuildBat = Join-Path $EngineRoot "Engine\Build\BatchFiles\Build.bat"
$ProjectPath = Join-Path $RepoRoot "Unreal\AirTraffic.uproject"
$ScriptPath = Join-Path $RepoRoot "Unreal\Scripts\benchmark_sppa_http_poll_replay.py"

if (-not (Test-Path $EditorCmd)) {
    throw "UnrealEditor-Cmd.exe not found: $EditorCmd"
}
if (-not (Test-Path $ProjectPath)) {
    throw "Project not found: $ProjectPath"
}
if (-not (Test-Path $ScriptPath)) {
    throw "Benchmark script not found: $ScriptPath"
}

if (-not $SkipBuild) {
    if (-not (Test-Path $BuildBat)) {
        throw "Build.bat not found: $BuildBat"
    }
    Write-Host "[sppa_http_replay] Building AirTrafficEditor..."
    & $BuildBat AirTrafficEditor Win64 Development "-Project=$ProjectPath" -WaitMutex -FromMsBuild
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal build failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutDir = Join-Path $RepoRoot "experiments\sppa_unreal_http_poll_replay\${Stamp}_http_poll_replay"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $OutDir "http_poll_replay.log"
}

$env:PORCE_SPPA_HTTP_REPLAY_OUT_DIR = $OutDir
$env:PORCE_SPPA_HTTP_REPLAY_COUNTS = $Counts
$env:PORCE_SPPA_HTTP_REPLAY_REPETITIONS = "$Repetitions"
$env:PORCE_SPPA_HTTP_REPLAY_UPDATES = "$UpdatesPerActor"
$env:PORCE_SPPA_HTTP_REPLAY_TIMEOUT_S = "$TimeoutS"
$env:PORCE_SPPA_HTTP_REPLAY_SEED = "$Seed"

Write-Host "[sppa_http_replay] Running HTTP poll replay..."
Write-Host "[sppa_http_replay] Engine: $EngineRoot"
Write-Host "[sppa_http_replay] OutDir: $OutDir"
Write-Host "[sppa_http_replay] Counts: $Counts Repetitions: $Repetitions UpdatesPerActor: $UpdatesPerActor TimeoutS: $TimeoutS Seed: $Seed"

& $EditorCmd $ProjectPath -run=pythonscript "-script=$ScriptPath" -unattended -nop4 -nosplash -NoSound -log="$LogPath"
if ($LASTEXITCODE -ne 0) {
    throw "HTTP poll replay benchmark failed with exit code $LASTEXITCODE. See $LogPath"
}

$Manifest = Join-Path $OutDir "run_manifest.json"
if (-not (Test-Path $Manifest)) {
    throw "HTTP poll replay benchmark did not produce manifest: $Manifest"
}

$ManifestJson = Get-Content $Manifest -Raw | ConvertFrom-Json
if ($ManifestJson.failures.Count -gt 0) {
    throw "HTTP poll replay benchmark reported failures: $($ManifestJson.failures | ConvertTo-Json -Compress)"
}

Write-Host "[sppa_http_replay] PASSED"
Write-Host "[sppa_http_replay] Artifacts: $OutDir"
