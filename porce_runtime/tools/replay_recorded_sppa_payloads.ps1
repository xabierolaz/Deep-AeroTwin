param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$EngineRoot = "",
    [string]$InputDir = "",
    [string]$OutDir = "",
    [string]$Streams = "common_asset_compatible,sppa_emit_all,sppa_changed_only",
    [string]$Backends = "unreal_assets,semantic_proxy",
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
$ProjectPath = Join-Path $RepoRoot "..\Unreal\AirTraffic.uproject"
$ScriptPath = Join-Path $RepoRoot "..\Unreal\Scripts\replay_recorded_sppa_payloads.py"

if (-not (Test-Path $EditorCmd)) {
    throw "UnrealEditor-Cmd.exe not found: $EditorCmd"
}
if (-not (Test-Path $ProjectPath)) {
    throw "Project not found: $ProjectPath"
}
if (-not (Test-Path $ScriptPath)) {
    throw "Replay script not found: $ScriptPath"
}

if (-not $SkipBuild) {
    if (-not (Test-Path $BuildBat)) {
        throw "Build.bat not found: $BuildBat"
    }
    Write-Host "[sppa_recorded_replay] Building AirTrafficEditor..."
    & $BuildBat AirTrafficEditor Win64 Development "-Project=$ProjectPath" -WaitMutex -FromMsBuild
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal build failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($InputDir)) {
    $InputDir = Join-Path $RepoRoot "..\papers\semantic_proxy_3d\experiments_root\sppa_recorded_payload_replay\20260703_recorded_obstacle_ingest"
}
if (-not (Test-Path $InputDir)) {
    throw "Input payload directory not found: $InputDir"
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutDir = Join-Path $RepoRoot "..\papers\semantic_proxy_3d\experiments_root\sppa_recorded_payload_unreal_replay\${Stamp}_recorded_payload_unreal_replay"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $OutDir "recorded_payload_unreal_replay.log"
}

$env:PORCE_SPPA_RECORDED_REPLAY_OUT_DIR = $OutDir
$env:PORCE_SPPA_RECORDED_REPLAY_INPUT_DIR = (Resolve-Path $InputDir).Path
$env:PORCE_SPPA_RECORDED_REPLAY_STREAMS = $Streams
$env:PORCE_SPPA_RECORDED_REPLAY_BACKENDS = $Backends

Write-Host "[sppa_recorded_replay] Running recorded payload Unreal replay..."
Write-Host "[sppa_recorded_replay] Engine: $EngineRoot"
Write-Host "[sppa_recorded_replay] InputDir: $InputDir"
Write-Host "[sppa_recorded_replay] OutDir: $OutDir"
Write-Host "[sppa_recorded_replay] Streams: $Streams"
Write-Host "[sppa_recorded_replay] Backends: $Backends"

& $EditorCmd $ProjectPath -run=pythonscript "-script=$ScriptPath" -unattended -nop4 -nosplash -NoSound -log="$LogPath"
if ($LASTEXITCODE -ne 0) {
    throw "Recorded payload Unreal replay failed with exit code $LASTEXITCODE. See $LogPath"
}

$Manifest = Join-Path $OutDir "run_manifest.json"
if (-not (Test-Path $Manifest)) {
    throw "Recorded payload Unreal replay did not produce manifest: $Manifest"
}

$ManifestJson = Get-Content $Manifest -Raw | ConvertFrom-Json
if ($ManifestJson.failures.Count -gt 0) {
    throw "Recorded payload Unreal replay reported failures: $($ManifestJson.failures | ConvertTo-Json -Compress)"
}

Write-Host "[sppa_recorded_replay] PASSED"
Write-Host "[sppa_recorded_replay] Artifacts: $OutDir"
