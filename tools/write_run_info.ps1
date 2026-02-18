param(
  [string]$OutputDir = "",
  [string]$ProjectRoot = ""
)

$ErrorActionPreference = "SilentlyContinue"

if (-not $OutputDir) { $OutputDir = $env:PORCE_AUDIT_ROOT }
if (-not $OutputDir) { exit 0 }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function _env([string]$name) {
  return [System.Environment]::GetEnvironmentVariable($name)
}

function _expand_path([string]$value) {
  if ([string]::IsNullOrWhiteSpace($value)) { return $value }
  try { return [System.Environment]::ExpandEnvironmentVariables($value) } catch { return $value }
}

function _git([string[]]$gitArgs) {
  try {
    if ($ProjectRoot) {
      return (& git -C $ProjectRoot @gitArgs 2>$null | Select-Object -First 1)
    }
    return (& git @gitArgs 2>$null | Select-Object -First 1)
  } catch {
    return ""
  }
}

$runInfoPath = Join-Path $OutputDir "RUN_INFO.txt"
$envDumpPath = Join-Path $OutputDir "PORCE_ENV.txt"

$timestampLocal = (Get-Date).ToString("o")
$timestampUtc   = (Get-Date).ToUniversalTime().ToString("o")

$lines = @()
$lines += "timestamp_local=$timestampLocal"
$lines += "timestamp_utc=$timestampUtc"
if ($ProjectRoot) { $lines += "project_root=$ProjectRoot" }
$lines += ("git_head=" + (_git @("rev-parse","--short","HEAD")))
$lines += ("git_branch=" + (_git @("rev-parse","--abbrev-ref","HEAD")))
$lines += ""

$keys = @(
  "PORCE_SYSTEM_MODE",
  "PORCE_YOLO_MODEL",
  "PORCE_VISION_DET_CONF",
  "PORCE_VISION_PUBLISH_CONF",
  "PORCE_VISION_MIN_SEEN_TO_PUBLISH",
  "PORCE_VISION_MIN_BOX_HEIGHT_PX",
  "PORCE_VISION_MIN_BOX_AREA_FRAC",
  "PORCE_VISION_MAX_BOX_AREA_FRAC",
  "PORCE_VISION_MAX_BOX_AREA_FRAC_BIKER",
  "PORCE_VISION_MAX_BOX_AREA_FRAC_COW",
  "PORCE_VISION_MAX_BOX_AREA_FRAC_TOWER",
  "PORCE_VISION_IGNORE_BOTTOM_PX",
  "PORCE_VISION_IGNORE_BOTTOM_FRAC",
  "PORCE_VISION_IGNORE_TOP_PX",
  "PORCE_VISION_IGNORE_TOP_FRAC",
  "PORCE_CAPTURE_WINDOW_TITLE",
  "PORCE_CAPTURE_WINDOW_CLASS",
  "PORCE_CAPTURE_EXPECT_WIDTH",
  "PORCE_CAPTURE_EXPECT_HEIGHT",
  "PORCE_LOG_SERVER_HOST",
  "PORCE_LOG_SERVER_PORT",
  "PORCE_LOG_SERVER_FILE",
  "PORCE_AUDIT_ENABLE",
  "PORCE_AUDIT_ROOT",
  "PORCE_AUDIT_VISION_FRAME_EVERY_N",
  "PORCE_AUDIT_VISION_ONLY_WITH_DETS"
)

foreach ($k in $keys) {
  $v = _env $k
  if ($k -eq "PORCE_YOLO_MODEL") { $v = _expand_path $v }
  if ($null -eq $v) { $v = "" }
  $lines += "$k=$v"
}

$modelPathRaw = _env "PORCE_YOLO_MODEL"
$modelPath = _expand_path $modelPathRaw
if (-not [string]::IsNullOrWhiteSpace($modelPath)) {
  $lines += ("model_exists=" + (Test-Path -LiteralPath $modelPath))
}

$lines | Set-Content -Path $runInfoPath -Encoding UTF8

# Dump all PORCE_* env vars (excluding likely secrets).
$secretRegex = '(?i)(TOKEN|PASSWORD|SECRET|KEY)'
$envLines = Get-ChildItem Env:PORCE_* |
  Where-Object { $_.Name -notmatch $secretRegex } |
  Sort-Object Name |
  ForEach-Object { "$($_.Name)=$($_.Value)" }

$envLines | Set-Content -Path $envDumpPath -Encoding UTF8

exit 0
