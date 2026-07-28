param(
  [string]$ProjectRoot = "",
  [int]$RecentPipelineFiles = 80,
  [int]$RecentUnrealFiles = 30,
  [int]$RecentZeroTrustRuns = 8,
  [int]$MaxLogAgeDays = 14,
  [string]$Since = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$pipelineLogs = Join-Path $ProjectRoot "pipeline\logs"
$zeroTrustRoot = Join-Path $pipelineLogs "zero_trust"
$unrealLogs = Join-Path $ProjectRoot "..\Unreal\Saved\Logs"
$outPath = Join-Path $pipelineLogs "runtime_output_audit_latest.json"
$cutoff = (Get-Date).AddDays(-1 * [math]::Max(1, $MaxLogAgeDays))
if (-not [string]::IsNullOrWhiteSpace($Since)) {
  try {
    $sinceCutoff = [datetime]$Since
    if ($sinceCutoff -gt $cutoff) {
      $cutoff = $sinceCutoff
    }
  } catch {
    throw "Invalid -Since datetime: $Since"
  }
}
$hasExplicitSince = -not [string]::IsNullOrWhiteSpace($Since)
$unrealLineCutoffUtc = $null
if ($hasExplicitSince) {
  $unrealLineCutoffUtc = $cutoff.ToUniversalTime()
}

$patterns = @(
  @{ Key = "traceback"; Pattern = "Traceback"; Severity = "error"; Benign = $false },
  @{ Key = "runtime_error"; Pattern = "RuntimeError"; Severity = "error"; Benign = $false },
  @{ Key = "explicit_error"; Pattern = "[ERROR]"; Severity = "error"; Benign = $false },
  @{ Key = "fatal_error"; Pattern = "Fatal error"; Severity = "error"; Benign = $false },
  @{ Key = "unhandled_exception"; Pattern = "Unhandled Exception"; Severity = "error"; Benign = $false },
  @{ Key = "assertion_failed"; Pattern = "Assertion failed"; Severity = "error"; Benign = $false },
  @{ Key = "niagara_splatinterface"; Pattern = "SplatInterface"; Severity = "error"; Benign = $false },
  @{ Key = "niagara_null_system"; Pattern = "NiagaraSystem was nullptr"; Severity = "error"; Benign = $false },
  @{ Key = "viz_fixed_xlim"; Pattern = "Ignoring fixed x limits"; Severity = "error"; Benign = $false },
  @{ Key = "vision_window_not_found"; Pattern = "Window not found"; Severity = "warning"; Benign = $false; ActionableOver = 3 },
  @{ Key = "vision_window_acquired"; Pattern = "Window acquired"; Severity = "info"; Benign = $true },
  @{ Key = "planner_failsafe_stage2"; Pattern = "Failsafe etapa 2"; Severity = "warning"; Benign = $false },
  @{ Key = "planner_hold"; Pattern = "Hold de seguridad"; Severity = "warning"; Benign = $false },
  @{ Key = "vision_send15"; Pattern = "send=15"; Severity = "warning"; Benign = $false },
  @{ Key = "mav_result_failed"; Pattern = "MAV_RESULT_FAILED"; Severity = "warning"; Benign = $false; ActionableOver = 8 },
  @{ Key = "varest_connection_refused"; Pattern = "Request failed (-1): http://127.0.0.1:8080/api/state/latest"; Severity = "warning"; Benign = $false; ActionableOver = 2 },
  @{ Key = "unreal_http_connection_refused"; Pattern = "Could not connect to server"; Severity = "warning"; Benign = $false; ActionableOver = 4 },
  @{ Key = "unreal_pix_plugin"; Pattern = "PixWinPlugin: PIX capture plugin failed to initialize"; Severity = "info"; Benign = $true },
  @{ Key = "unreal_aqprof"; Pattern = "Failed to load 'aqProf"; Severity = "info"; Benign = $true },
  @{ Key = "unreal_vtune"; Pattern = "Failed to load 'Vtune"; Severity = "info"; Benign = $true },
  @{ Key = "unreal_winpix"; Pattern = "WinPixGpuCapturer"; Severity = "info"; Benign = $true },
  @{ Key = "unreal_mapcheck"; Pattern = "Map check complete"; Severity = "info"; Benign = $true },
  @{ Key = "unreal_success_zero"; Pattern = "Success - 0 error(s), 0 warning(s)"; Severity = "info"; Benign = $true },
  @{ Key = "deprecated_ini"; Pattern = "deprecated ini key"; Severity = "warning"; Benign = $false },
  @{ Key = "varest_redirect"; Pattern = "MatchSubstring"; Severity = "warning"; Benign = $false }
)

function Get-RecentFiles([string]$Path, [int]$Count) {
  if (-not (Test-Path $Path)) {
    return @()
  }
  return @(
    Get-ChildItem -Path $Path -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Extension -in @(".log", ".txt") } |
      Where-Object { $_.LastWriteTime -ge $cutoff } |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First $Count
  )
}

function Get-ZeroTrustSystemLogs() {
  $items = @()
  if (-not (Test-Path $zeroTrustRoot)) {
    return @()
  }

  $latestRun = Get-Content (Join-Path $zeroTrustRoot "LATEST_RUN.txt") -ErrorAction SilentlyContinue
  if ($latestRun) {
    $latestLog = Join-Path $latestRun "SYSTEM_ALL.log"
    if (Test-Path $latestLog) {
      $latestItem = Get-Item $latestLog
      if ($latestItem.LastWriteTime -ge $cutoff) {
        $items += $latestItem
      }
    }
  }

  $items += Get-ChildItem -Path $zeroTrustRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -ge $cutoff } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First $RecentZeroTrustRuns |
    ForEach-Object {
      $p = Join-Path $_.FullName "SYSTEM_ALL.log"
      if (Test-Path $p) { Get-Item $p }
    }
  return @($items | Sort-Object FullName -Unique)
}

function New-FileAudit($File) {
  $hits = @()
  foreach ($entry in $patterns) {
    $matches = @(Select-String -Path $File.FullName -Pattern $entry.Pattern -SimpleMatch -ErrorAction SilentlyContinue)
    if ($hasExplicitSince -and $unrealLineCutoffUtc -and $File.FullName.StartsWith($unrealLogs, [System.StringComparison]::OrdinalIgnoreCase)) {
      $matches = @(
        $matches | Where-Object {
          $line = [string]$_.Line
          $m = [regex]::Match($line, '^\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})')
          if (-not $m.Success) {
            return $false
          }
          try {
            $lineTime = [datetime]::ParseExact(
              $m.Groups[1].Value,
              'yyyy.MM.dd-HH.mm.ss',
              [System.Globalization.CultureInfo]::InvariantCulture
            )
            $lineTime = [datetime]::SpecifyKind($lineTime, [System.DateTimeKind]::Utc)
            return $lineTime -ge $unrealLineCutoffUtc
          } catch {
            return $false
          }
        }
      )
    }
    if ($matches.Count -le 0) {
      continue
    }
    $sample = @(
      $matches |
        Select-Object -First 3 |
        ForEach-Object {
          @{
            line = [int]$_.LineNumber
            text = [string]$_.Line.Trim()
          }
        }
    )
    $isBenign = [bool]$entry.Benign
    if ($entry.ContainsKey("ActionableOver")) {
      $isBenign = $matches.Count -le [int]$entry.ActionableOver
    }
    $hit = @{
      key = [string]$entry.Key
      pattern = [string]$entry.Pattern
      severity = [string]$entry.Severity
      benign = [bool]$isBenign
      count = [int]$matches.Count
      samples = $sample
    }
    if ($entry.ContainsKey("ActionableOver")) {
      $hit.actionable_over = [int]$entry.ActionableOver
    }
    $hits += $hit
  }

  $actionable = @($hits | Where-Object { -not $_.benign })
  return @{
    path = [string]$File.FullName.Replace($ProjectRoot + "\", "")
    full_path = [string]$File.FullName
    last_write_time = [string]$File.LastWriteTime.ToString("s")
    bytes = [int64]$File.Length
    hits = $hits
    actionable_hit_count = [int]$actionable.Count
    actionable_line_count = [int](($actionable | ForEach-Object { [int]$_.count } | Measure-Object -Sum).Sum)
  }
}

$files = @()
$files += Get-RecentFiles $pipelineLogs $RecentPipelineFiles
$files += Get-RecentFiles $unrealLogs $RecentUnrealFiles
$files += Get-ZeroTrustSystemLogs
$files = @($files | Sort-Object FullName -Unique)

$audits = @($files | ForEach-Object { New-FileAudit $_ })
$withHits = @($audits | Where-Object { $_.hits.Count -gt 0 })
$actionableFiles = @($withHits | Where-Object { $_.actionable_hit_count -gt 0 })
$summary = @{
  generated_at = [string](Get-Date).ToString("s")
  project_root = [string]$ProjectRoot
  cutoff = [string]$cutoff.ToString("s")
  scanned_files = [int]$files.Count
  files_with_hits = [int]$withHits.Count
  actionable_files = [int]$actionableFiles.Count
  actionable_line_count = [int](($actionableFiles | ForEach-Object { [int]$_.actionable_line_count } | Measure-Object -Sum).Sum)
}

$report = @{
  summary = $summary
  files = $audits
}

$json = $report | ConvertTo-Json -Depth 8
$json | Set-Content -Path $outPath -Encoding UTF8

Write-Host ("[runtime-audit] scanned={0} files_with_hits={1} actionable_files={2} actionable_lines={3}" -f `
  $summary.scanned_files, $summary.files_with_hits, $summary.actionable_files, $summary.actionable_line_count)
Write-Host ("[runtime-audit] report={0}" -f $outPath)

if ($actionableFiles.Count -gt 0) {
  Write-Host "[runtime-audit] actionable summary:"
  $actionableFiles |
    Sort-Object @{ Expression = "actionable_line_count"; Descending = $true }, path |
    Select-Object -First 30 |
    ForEach-Object {
      $hitText = (@($_.hits | Where-Object { -not $_.benign } | ForEach-Object { "{0}={1}" -f $_.key, $_.count }) -join "; ")
      Write-Host ("  - {0}: {1}" -f $_.path, $hitText)
    }
}
