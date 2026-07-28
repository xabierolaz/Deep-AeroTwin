param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$EngineRoot = "",
    [string]$OutDir = "",
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
$ScriptPath = Join-Path $RepoRoot "..\Unreal\Scripts\verify_pipeline_b_freshness_contract.py"

foreach ($RequiredPath in @($EditorCmd, $ProjectPath, $ScriptPath)) {
    if (-not (Test-Path $RequiredPath)) {
        throw "Required path not found: $RequiredPath"
    }
}

if (-not $SkipBuild) {
    if (-not (Test-Path $BuildBat)) {
        throw "Build.bat not found: $BuildBat"
    }
    Write-Host "[pipeline_b_freshness] Building AirTrafficEditor..."
    & $BuildBat AirTrafficEditor Win64 Development "-Project=$ProjectPath" -WaitMutex -FromMsBuild
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal build failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutDir = Join-Path $RepoRoot "..\papers\semantic_proxy_3d\experiments_root\pipeline_b_freshness_contract\$Stamp"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $OutDir "unreal_freshness_contract.log"
}

$env:PORCE_PIPELINE_B_FRESHNESS_OUT_DIR = $OutDir
Write-Host "[pipeline_b_freshness] Engine: $EngineRoot"
Write-Host "[pipeline_b_freshness] Output: $OutDir"
& $EditorCmd $ProjectPath -run=pythonscript "-script=$ScriptPath" -unattended -nop4 -nosplash -NoSound "-log=$LogPath"
if ($LASTEXITCODE -ne 0) {
    throw "Unreal freshness-contract run failed with exit code $LASTEXITCODE. See $LogPath"
}

$ResultPath = Join-Path $OutDir "unreal_freshness_contract_result.json"
if (-not (Test-Path $ResultPath)) {
    throw "Unreal freshness-contract result is missing: $ResultPath"
}
$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
if ($Result.status -ne "passed") {
    throw "Unreal freshness-contract result failed: $($Result.failure)"
}

Write-Host "[pipeline_b_freshness] PASSED"
Write-Host "[pipeline_b_freshness] Evidence: $ResultPath"
