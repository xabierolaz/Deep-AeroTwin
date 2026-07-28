param(
  [string]$RepoRoot = "",
  [int]$MaxBlobMiB = 50
)

$ErrorActionPreference = "Stop"

function Info([string]$Message) {
  Write-Host "[repo_hygiene] $Message"
}

function Add-Failure([System.Collections.Generic.List[string]]$Failures, [string]$Message) {
  $Failures.Add($Message) | Out-Null
  Write-Host "[repo_hygiene] FAIL $Message" -ForegroundColor Red
}

function Invoke-GitLines([string[]]$ArgumentList) {
  $output = & git -C $RepoRoot @ArgumentList 2>&1 | ForEach-Object { $_.ToString() }
  $exitCode = [int]$LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "git $($ArgumentList -join ' ') failed with exit code ${exitCode}: $($output -join "`n")"
  }
  return @($output)
}

function Format-MiB([Int64]$Bytes) {
  return "{0:N1} MiB" -f ($Bytes / 1MB)
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$failures = New-Object System.Collections.Generic.List[string]
$maxBlobBytes = [Int64]$MaxBlobMiB * 1MB

Info "Repo: $RepoRoot"

try {
  $topLevel = (Invoke-GitLines -ArgumentList @("rev-parse", "--show-toplevel") | Select-Object -First 1)
  if ((Resolve-Path -LiteralPath $topLevel).Path -ne $RepoRoot) {
    Add-Failure $failures "RepoRoot does not match git top-level: $topLevel"
  }
} catch {
  Add-Failure $failures $_.Exception.Message
}

$tracked = @()
try {
  $tracked = Invoke-GitLines -ArgumentList @("ls-files")
} catch {
  Add-Failure $failures $_.Exception.Message
}

$buildArtifactExts = New-Object "System.Collections.Generic.HashSet[string]" ([System.StringComparer]::OrdinalIgnoreCase)
foreach ($ext in @(".aux", ".blg", ".fdb_latexmk", ".fls", ".lof", ".log", ".lot", ".out", ".run.xml", ".synctex.gz", ".toc", ".bcf")) {
  $buildArtifactExts.Add($ext) | Out-Null
}

$trackedBuildArtifacts = @()
foreach ($path in $tracked) {
  $lower = $path.ToLowerInvariant()
  foreach ($ext in $buildArtifactExts) {
    if ($lower.EndsWith($ext)) {
      $trackedBuildArtifacts += $path
      break
    }
  }
}
if ($trackedBuildArtifacts.Count -gt 0) {
  Add-Failure $failures ("Tracked LaTeX/build artifacts found: " + (($trackedBuildArtifacts | Select-Object -First 20) -join ", "))
} else {
  Info "No tracked LaTeX/build artifacts."
}

try {
  $lfsOutput = & git -C $RepoRoot lfs fsck 2>&1 | ForEach-Object { $_.ToString() }
  $lfsExit = [int]$LASTEXITCODE
  if ($lfsExit -ne 0) {
    Add-Failure $failures ("git lfs fsck failed: " + ($lfsOutput -join "`n"))
  } else {
    Info "Git LFS fsck OK."
  }
} catch {
  Add-Failure $failures $_.Exception.Message
}

try {
  $revList = Invoke-GitLines -ArgumentList @("rev-list", "--objects", "--all")
  $batch = @()
  if ($revList.Count -gt 0) {
    $batch = $revList |
      & git -C $RepoRoot cat-file "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)" 2>&1 |
      ForEach-Object { $_.ToString() }
    $batchExit = [int]$LASTEXITCODE
    if ($batchExit -ne 0) {
      throw "git cat-file --batch-check failed with exit code ${batchExit}: $($batch -join "`n")"
    }
  }

  $largeBlobs = @()
  foreach ($line in $batch) {
    $parts = $line -split " ", 4
    if ($parts.Count -lt 3 -or $parts[0] -ne "blob") {
      continue
    }
    $size = [Int64]0
    if (-not [Int64]::TryParse($parts[2], [ref]$size)) {
      continue
    }
    if ($size -gt $maxBlobBytes) {
      $name = if ($parts.Count -ge 4) { $parts[3] } else { "<unnamed>" }
      $largeBlobs += [pscustomobject]@{
        Size = $size
        Object = $parts[1]
        Path = $name
      }
    }
  }

  if ($largeBlobs.Count -gt 0) {
    $top = @($largeBlobs | Sort-Object Size -Descending | Select-Object -First 20 | ForEach-Object {
      "$(Format-MiB $_.Size) $($_.Object) $($_.Path)"
    })
    Add-Failure $failures ("Reachable Git blobs over ${MaxBlobMiB} MiB found: " + ($top -join "; "))
  } else {
    Info "No reachable Git blobs over ${MaxBlobMiB} MiB."
  }
} catch {
  Add-Failure $failures $_.Exception.Message
}

if ($failures.Count -gt 0) {
  Info "FAILED failures=$($failures.Count)"
  exit 1
}

Info "PASSED"
exit 0
