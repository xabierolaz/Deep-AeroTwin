param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$EngineRoot = "",
    [string]$OutDir = "",
    [string]$PackageDir = "",
    [string]$Map = "/Game/SPPABenchmark",
    [string]$CookMaps = "/Game/SPPABenchmark+/Game/Ejea",
    [string]$Counts = "10,50,100",
    [string]$Backends = "no_render,unreal_assets,semantic_proxy",
    [int]$Repetitions = 3,
    [int]$WarmupFrames = 30,
    [int]$MeasureFrames = 120,
    [int]$UpdateEveryFrames = 15,
    [int]$Seed = 20260702,
    [int]$ResX = 1280,
    [int]$ResY = 720,
    [int]$TimeoutSeconds = 900,
    [switch]$SkipPackage,
    [switch]$NoCsvProfile
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\unreal_engine_paths.ps1"

$RepoRoot = (Resolve-Path $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($EngineRoot)) {
    $EngineRoot = Resolve-PorceUnrealEngineRoot
}

$ProjectPath = Join-Path $RepoRoot "Unreal\AirTraffic.uproject"
$RunUat = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"
$Summarizer = Join-Path $RepoRoot "tools\summarize_sppa_packaged_render.py"

if (-not (Test-Path $ProjectPath)) {
    throw "Project not found: $ProjectPath"
}
if (-not (Test-Path $RunUat)) {
    throw "RunUAT.bat not found: $RunUat"
}
if (-not (Test-Path $Summarizer)) {
    throw "Summarizer not found: $Summarizer"
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $OutDir = Join-Path $RepoRoot "experiments\sppa_packaged_render\${Stamp}_packaged_render"
}
$OutDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDir)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ([string]::IsNullOrWhiteSpace($PackageDir)) {
    $PackageDir = Join-Path $OutDir "package"
}
$PackageDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PackageDir)

if (-not $SkipPackage) {
    New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null
    Write-Host "[sppa_packaged_render] Packaging AirTraffic Win64 Development..."
    Write-Host "[sppa_packaged_render] Engine: $EngineRoot"
    Write-Host "[sppa_packaged_render] PackageDir: $PackageDir"
    & $RunUat BuildCookRun `
        "-project=$ProjectPath" `
        -noP4 `
        -platform=Win64 `
        -clientconfig=Development `
        "-map=$CookMaps" `
        -build `
        -cook `
        -stage `
        -pak `
        -archive `
        "-archivedirectory=$PackageDir" `
        -utf8output
    if ($LASTEXITCODE -ne 0) {
        throw "Packaging failed with exit code $LASTEXITCODE"
    }
}

$Exe = Get-ChildItem -Path $PackageDir -Recurse -File -Filter "AirTraffic*.exe" |
    Where-Object { $_.Name -notmatch "Crash|Bootstrap|UnrealPak" } |
    Sort-Object FullName |
    Select-Object -First 1

if (-not $Exe) {
    throw "Could not find packaged AirTraffic executable under $PackageDir"
}

$LogPath = Join-Path $OutDir "packaged_render_run.log"
$Args = @()
if (-not [string]::IsNullOrWhiteSpace($Map)) {
    $Args += $Map
}
$Args += @(
    "-PorceSPPAPackagedBenchmark",
    "-PorceSPPABenchmarkOutDir=`"$OutDir`"",
    "-PorceSPPABenchmarkCounts=`"$Counts`"",
    "-PorceSPPABenchmarkBackends=`"$Backends`"",
    "-PorceSPPABenchmarkRepetitions=$Repetitions",
    "-PorceSPPABenchmarkWarmupFrames=$WarmupFrames",
    "-PorceSPPABenchmarkMeasureFrames=$MeasureFrames",
    "-PorceSPPABenchmarkUpdateEveryFrames=$UpdateEveryFrames",
    "-PorceSPPABenchmarkSeed=$Seed",
    "-PorceSPPABenchmarkResX=$ResX",
    "-PorceSPPABenchmarkResY=$ResY",
    "-windowed",
    "-ResX=$ResX",
    "-ResY=$ResY",
    "-NoSound",
    "-Unattended",
    "-abslog=`"$LogPath`""
)
if ($NoCsvProfile) {
    $Args += "-PorceSPPABenchmarkNoCsvProfile"
}

Write-Host "[sppa_packaged_render] Running packaged benchmark..."
Write-Host "[sppa_packaged_render] Exe: $($Exe.FullName)"
Write-Host "[sppa_packaged_render] OutDir: $OutDir"
Write-Host "[sppa_packaged_render] Map: $Map CookMaps: $CookMaps"
Write-Host "[sppa_packaged_render] Counts: $Counts Backends: $Backends Repetitions: $Repetitions WarmupFrames: $WarmupFrames MeasureFrames: $MeasureFrames"

$Process = Start-Process -FilePath $Exe.FullName -ArgumentList $Args -PassThru -WindowStyle Hidden
if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
    try {
        $Process.Kill()
    } catch {
    }
    throw "Packaged benchmark timed out after $TimeoutSeconds seconds. See $LogPath"
}
if ($Process.ExitCode -ne 0) {
    if (Test-Path $LogPath) {
        Get-Content $LogPath -Tail 120
    }
    throw "Packaged benchmark failed with exit code $($Process.ExitCode). See $LogPath"
}

$ManifestPath = Join-Path $OutDir "run_manifest.json"
$FramePath = Join-Path $OutDir "packaged_frame_stats.csv"
$ActionPath = Join-Path $OutDir "packaged_action_rows.csv"
foreach ($Path in @($ManifestPath, $FramePath, $ActionPath)) {
    if (-not (Test-Path $Path)) {
        if (Test-Path $LogPath) {
            Get-Content $LogPath -Tail 160
        }
        throw "Packaged benchmark did not produce expected artifact: $Path"
    }
}

python $Summarizer $OutDir
if ($LASTEXITCODE -ne 0) {
    throw "Packaged benchmark summarizer failed with exit code $LASTEXITCODE"
}

Write-Host "[sppa_packaged_render] PASSED"
Write-Host "[sppa_packaged_render] Artifacts: $OutDir"
