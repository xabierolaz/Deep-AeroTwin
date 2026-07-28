param(
  [switch]$Apply,
  [string[]]$KeepRunName = @(
    "20260620_072924",
    "20260620_073611"
  )
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogsRoot = Join-Path $RepoRoot "pipeline\logs"

function _full_existing_path([string]$Path) {
  $resolved = (Resolve-Path -LiteralPath $Path).Path
  return [System.IO.Path]::GetFullPath($resolved)
}

function _is_inside_root([string]$Path, [string]$Root) {
  $separatorChars = [char[]]@(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  )
  $resolved = (_full_existing_path $Path).TrimEnd($separatorChars)
  $resolvedRoot = (_full_existing_path $Root).TrimEnd($separatorChars)
  return (
    $resolved.Equals($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $resolved.StartsWith(
      $resolvedRoot + [System.IO.Path]::DirectorySeparatorChar,
      [System.StringComparison]::OrdinalIgnoreCase
    )
  )
}

function _is_inside_logs_root([string]$Path) {
  return _is_inside_root $Path $LogsRoot
}

function _run_name_for_path([System.IO.DirectoryInfo]$Dir) {
  $current = $Dir
  while ($current -and (_is_inside_logs_root $current.FullName)) {
    if ($current.Name -match '^\d{8}_\d{6}$') {
      return $current.Name
    }
    $current = $current.Parent
  }
  return ""
}

if (-not (Test-Path $LogsRoot)) {
  Write-Host "[cleanup_runtime_artifacts] No pipeline logs dir: $LogsRoot"
  exit 0
}

$targets = @()
$targets += Get-ChildItem -Path $LogsRoot -Recurse -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -eq "frames" } |
  Where-Object {
    $runName = _run_name_for_path $_
    -not ($KeepRunName -contains $runName)
  }

$vizFrames = Join-Path $LogsRoot "viz_frames"
if (Test-Path $vizFrames) {
  $targets += Get-Item $vizFrames
}

$targets = @($targets | Sort-Object -Property FullName -Unique)
$summary = foreach ($target in $targets) {
  if (-not (_is_inside_logs_root $target.FullName)) {
    throw "Refusing to touch path outside pipeline logs: $($target.FullName)"
  }
  $files = @(Get-ChildItem -Path $target.FullName -Recurse -File -ErrorAction SilentlyContinue)
  [pscustomobject]@{
    Path = $target.FullName.Replace($RepoRoot + "\", "")
    Files = $files.Count
    MB = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB, 1)
  }
}

$totalFiles = ($summary | Measure-Object Files -Sum).Sum
$totalMb = ($summary | Measure-Object MB -Sum).Sum
if ($null -eq $totalFiles) { $totalFiles = 0 }
if ($null -eq $totalMb) { $totalMb = 0 }
Write-Host ("[cleanup_runtime_artifacts] targets={0} files={1} MB={2} apply={3}" -f $targets.Count, $totalFiles, $totalMb, [bool]$Apply)
$summary | Sort-Object MB -Descending | Select-Object -First 30 | Format-Table -AutoSize

if (-not $Apply) {
  Write-Host "[cleanup_runtime_artifacts] Dry run only. Re-run with -Apply to delete frame directories."
  exit 0
}

foreach ($target in $targets) {
  if (-not (_is_inside_logs_root $target.FullName)) {
    throw "Refusing to delete path outside pipeline logs: $($target.FullName)"
  }
  Remove-Item -LiteralPath $target.FullName -Recurse -Force
}

Write-Host "[cleanup_runtime_artifacts] Done."
