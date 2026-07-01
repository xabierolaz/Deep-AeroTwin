param(
  [string]$RepoRoot = "",
  [switch]$SkipSemanticProxy,
  [switch]$SkipPipelineB
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
  throw $Message
}

function Info([string]$Message) {
  Write-Host "[verify_papers] $Message"
}

function Require-Command([string]$Name) {
  $command = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $command) {
    Fail "Required command not found on PATH: $Name"
  }
  return $command.Source
}

function Test-FileWritable([string]$Path) {
  if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $true
  }

  $stream = $null
  try {
    $stream = [System.IO.File]::Open(
      $Path,
      [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::ReadWrite,
      [System.IO.FileShare]::None
    )
    return $true
  } catch {
    return $false
  } finally {
    if ($null -ne $stream) {
      $stream.Close()
    }
  }
}

function Wait-FileWritable([string]$Path, [int]$TimeoutSeconds = 20) {
  if (-not $Path) {
    return
  }

  $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
  while (-not (Test-FileWritable $Path)) {
    if ($stopwatch.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
      Fail "Timed out waiting for writable PDF output: $Path"
    }
    Start-Sleep -Milliseconds 250
  }
}

function Invoke-LoggedCommand(
  [string]$Exe,
  [string[]]$ArgumentList,
  [string]$WorkingDirectory,
  [string]$LogPath,
  [string]$OutputPath = "",
  [int]$Attempts = 1
) {
  $commandLine = "$Exe $($ArgumentList -join ' ')"

  for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    if ($attempt -gt 1) {
      Info "$commandLine (retry ${attempt}/${Attempts})"
    } else {
      Info $commandLine
    }

    Wait-FileWritable -Path $OutputPath
    Push-Location $WorkingDirectory
    try {
      "=== $commandLine" | Set-Content -LiteralPath $LogPath -Encoding UTF8
      $previousErrorActionPreference = $ErrorActionPreference
      $ErrorActionPreference = "Continue"
      try {
        & $Exe @ArgumentList 2>&1 |
          ForEach-Object { $_.ToString() } |
          Tee-Object -FilePath $LogPath -Append |
          Out-Host
        $exitCode = [int]$LASTEXITCODE
      } finally {
        $ErrorActionPreference = $previousErrorActionPreference
      }
    } finally {
      Pop-Location
    }

    if ($exitCode -eq 0) {
      return
    }

    $logText = ""
    if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
      $logText = Get-Content -LiteralPath $LogPath -Raw
    }
    $canRetryBusyOutput = (
      $attempt -lt $Attempts -and
      $OutputPath -and
      $logText -match "I can't write on file"
    )
    if (-not $canRetryBusyOutput) {
      Fail "Command failed with exit code ${exitCode}: $commandLine"
    }

    Info "PDF output was temporarily busy; waiting before retrying."
    Start-Sleep -Milliseconds 750
  }
}

function Assert-Pdf([string]$PdfPath) {
  if (-not (Test-Path -LiteralPath $PdfPath -PathType Leaf)) {
    Fail "Expected PDF was not generated: $PdfPath"
  }
  $pdf = Get-Item -LiteralPath $PdfPath
  if ($pdf.Length -le 0) {
    Fail "Generated PDF is empty: $PdfPath"
  }
}

function Assert-LogHasNoUnresolvedRefs([string]$LogPath) {
  if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) {
    Fail "Expected compile log not found: $LogPath"
  }
  $text = Get-Content -LiteralPath $LogPath -Raw
  $fatalPatterns = @(
    "LaTeX Error",
    "Emergency stop",
    "Fatal error",
    "Undefined control sequence",
    "Citation .* undefined",
    "Reference .* undefined",
    "There were undefined references",
    "Label\(s\) may have changed",
    "Rerun to get"
  )
  foreach ($pattern in $fatalPatterns) {
    if ($text -match $pattern) {
      Fail "Paper compile log still contains unresolved/fatal marker '$pattern': $LogPath"
    }
  }
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

$logRoot = Join-Path $RepoRoot "pipeline\logs\paper_verify"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$pdflatex = Require-Command "pdflatex"
$bibtex = Require-Command "bibtex"
$xelatex = Require-Command "xelatex"

$results = @()

if (-not $SkipSemanticProxy) {
  $paperDir = Join-Path $RepoRoot "paper_semantic_proxy_3d"
  $tex = "semantic_proxy_3d_paper.tex"
  $pdf = Join-Path $paperDir "semantic_proxy_3d_paper.pdf"
  $log = Join-Path $logRoot "semantic_proxy_3d_paper.log"
  Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue

  Invoke-LoggedCommand -Exe $pdflatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Invoke-LoggedCommand -Exe $bibtex -ArgumentList @("semantic_proxy_3d_paper") -WorkingDirectory $paperDir -LogPath $log
  Invoke-LoggedCommand -Exe $pdflatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Invoke-LoggedCommand -Exe $pdflatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Assert-Pdf $pdf
  Assert-LogHasNoUnresolvedRefs $log
  $results += [pscustomobject]@{ Paper = "semantic_proxy_3d"; Pdf = $pdf; Bytes = (Get-Item $pdf).Length }
}

if (-not $SkipPipelineB) {
  $paperDir = Join-Path $RepoRoot "paper_pipeline_B_telemetry"
  $tex = "pipeline_b_concept.tex"
  $pdf = Join-Path $paperDir "pipeline_b_concept.pdf"
  $log = Join-Path $logRoot "pipeline_b_concept.log"
  Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue

  Invoke-LoggedCommand -Exe $xelatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Invoke-LoggedCommand -Exe $xelatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Invoke-LoggedCommand -Exe $xelatex -ArgumentList @("-interaction=nonstopmode", "-halt-on-error", $tex) -WorkingDirectory $paperDir -LogPath $log -OutputPath $pdf -Attempts 5
  Assert-Pdf $pdf
  Assert-LogHasNoUnresolvedRefs $log
  $results += [pscustomobject]@{ Paper = "pipeline_b_telemetry"; Pdf = $pdf; Bytes = (Get-Item $pdf).Length }
}

Info "Paper verification PASSED"
$results | Format-Table -AutoSize
