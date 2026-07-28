param(
  [string]$RepoRoot = "",
  [string]$TargetRoot = "D:\ayte_reclamacion\AYTE_DOCTOR\papers"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
  throw $Message
}

function Info([string]$Message) {
  Write-Host "[sync_papers] $Message"
}

function Resolve-ExistingDirectory([string]$Path, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    Fail "$Label directory not found: $Path"
  }
  return (Resolve-Path -LiteralPath $Path).Path
}

function Get-TreeStats([string]$Path) {
  $root = (Resolve-Path -LiteralPath $Path).Path.TrimEnd([char[]]@('\', '/'))
  $files = @(
    Get-ChildItem -LiteralPath $root -Recurse -File -Force |
      Sort-Object -Property FullName
  )
  $sum = ($files | Measure-Object -Property Length -Sum).Sum
  if ($null -eq $sum) {
    $sum = 0
  }

  $inventoryLines = @()
  foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($root.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $inventoryLines += "$relativePath`t$($file.Length)`t$hash"
  }

  $inventoryText = ($inventoryLines -join "`n")
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    $inventoryHashBytes = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($inventoryText))
  } finally {
    $sha256.Dispose()
  }
  $inventoryHash = [System.BitConverter]::ToString($inventoryHashBytes).Replace("-", "").ToLowerInvariant()

  return [ordered]@{
    files = [int]$files.Count
    bytes = [int64]$sum
    inventory_hash = $inventoryHash
    inventory = $inventoryLines
  }
}

function Compare-TreeStats([hashtable]$SourceStats, [hashtable]$TargetStats) {
  return (
    $SourceStats.files -eq $TargetStats.files -and
    $SourceStats.bytes -eq $TargetStats.bytes -and
    $SourceStats.inventory_hash -eq $TargetStats.inventory_hash
  )
}

function Invoke-RobocopyChecked([string]$Source, [string]$Target) {
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  & robocopy $Source $Target /E /R:2 /W:1 /NFL /NDL /NP | Out-Host
  $exitCode = [int]$LASTEXITCODE
  if ($exitCode -gt 7) {
    Fail "robocopy failed with exit code $exitCode for $Source -> $Target"
  }
  return $exitCode
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$papers = @(
  [ordered]@{
    name = "Semantic Proxy 3D"
    folder = "semantic_proxy_3d"
    source = Join-Path $RepoRoot "..\papers\semantic_proxy_3d"
  },
  [ordered]@{
    name = "Pipeline B Telemetry VRIH"
    folder = "pipeline_b_telemetry_vrih"
    source = Join-Path $RepoRoot "..\papers\pipeline_a_telemetry"
  },
  [ordered]@{
    name = "Path Planning Collision Evasion"
    folder = "path_planning_collision_evasion"
    source = Join-Path $RepoRoot "..\papers\porce_collision_evasion\Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
  }
)

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
$targetRootResolved = (Resolve-Path -LiteralPath $TargetRoot).Path

$rows = @()
foreach ($paper in $papers) {
  $source = Resolve-ExistingDirectory -Path $paper.source -Label $paper.name
  $target = Join-Path $targetRootResolved $paper.folder

  Info "Copying $($paper.name)"
  $robocopyExitCode = Invoke-RobocopyChecked -Source $source -Target $target

  $sourceStats = Get-TreeStats -Path $source
  $targetStats = Get-TreeStats -Path $target
  $match = Compare-TreeStats -SourceStats $sourceStats -TargetStats $targetStats
  if (-not $match) {
    Fail "Copy verification failed for $($paper.name): source files=$($sourceStats.files) bytes=$($sourceStats.bytes) hash=$($sourceStats.inventory_hash), target files=$($targetStats.files) bytes=$($targetStats.bytes) hash=$($targetStats.inventory_hash)"
  }

  $rows += [ordered]@{
    name = [string]$paper.name
    source = $source
    target = (Resolve-Path -LiteralPath $target).Path
    files = [int]$sourceStats.files
    bytes = [int64]$sourceStats.bytes
    inventory_hash = [string]$sourceStats.inventory_hash
    robocopy_exit_code = $robocopyExitCode
  }
}

$manifestPath = Join-Path $targetRootResolved "COPY_MANIFEST.md"
$lines = @(
  "# Paper Copy Manifest",
  "",
  "Generated: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz"))",
  "",
  "Source repository: ``$RepoRoot``",
  "",
  "## Copied Paper Folders",
  "",
  "| Paper folder | Source | Target | Files | Bytes | Inventory SHA-256 | Verified |",
  "|---|---|---|---:|---:|---|---|"
)

foreach ($row in $rows) {
  $lines += "| $($row.name) | ``$($row.source)`` | ``$($row.target)`` | $($row.files) | $($row.bytes) | ``$($row.inventory_hash)`` | yes |"
}

$lines += @(
  "",
  "Verification method: recursive file count, byte-sum, per-file SHA-256, and aggregate inventory SHA-256 comparison.",
  "",
  "Copy method: non-destructive ``robocopy /E``; no target files are deleted."
)

Set-Content -LiteralPath $manifestPath -Encoding UTF8 -Value $lines

Info "Manifest written to $manifestPath"
$rows | ForEach-Object {
  [pscustomobject]@{
    Paper = $_.name
    Files = $_.files
    Bytes = $_.bytes
    InventoryHash = $_.inventory_hash
    Target = $_.target
  }
} | Format-Table -AutoSize
