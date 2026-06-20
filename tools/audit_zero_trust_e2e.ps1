param(
  [string]$RepoRoot = "",
  [string]$EngineBuildBat = "D:\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat",
  [int]$RealTwinPort = 18082,
  [int]$SimulationPort = 18083,
  [switch]$SkipUnrealBuild
)

$ErrorActionPreference = "Stop"

function Fail([string]$message) {
  throw $message
}

function Info([string]$message) {
  Write-Host "[audit_e2e] $message"
}

function Get-HttpErrorStatusCode($err) {
  try {
    return [int]$err.Exception.Response.StatusCode.value__
  } catch {
    return -1
  }
}

function Stop-PortListeners([int]$Port) {
  while ($true) {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { break }
    $listeners | ForEach-Object {
      Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
  }
}

function Set-ProcessEnv([hashtable]$map) {
  $previous = @{}
  foreach ($key in $map.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
    [Environment]::SetEnvironmentVariable($key, [string]$map[$key], "Process")
  }
  return $previous
}

function Restore-ProcessEnv([hashtable]$previous) {
  foreach ($key in $previous.Keys) {
    [Environment]::SetEnvironmentVariable($key, $previous[$key], "Process")
  }
}

function Wait-Brain([string]$BaseUrl, [int]$TimeoutSec = 30) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      return Invoke-RestMethod -Uri "$BaseUrl/api/status" -TimeoutSec 2
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $null
}

function Start-BrainRuntime(
  [string]$Mode,
  [int]$Port,
  [string]$Token,
  [string]$RepoRoot,
  [string]$AuditRoot
) {
  $pipelineDir = Join-Path $RepoRoot "pipeline"
  $venvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    Fail "venv python not found: $venvPython"
  }

  Stop-PortListeners -Port $Port

  $modeKey = $Mode.Trim().ToUpperInvariant()
  $evasion = if ($modeKey -eq "REAL_TWIN") { "0" } else { "1" }
  $auditModeRoot = Join-Path $AuditRoot $modeKey.ToLowerInvariant()
  New-Item -ItemType Directory -Force -Path $auditModeRoot | Out-Null

  $envMap = @{
    "PORCE_SYSTEM_MODE" = $modeKey
    "PORCE_MOCK_MAVLINK" = "1"
    "PORCE_ENABLE_EVASION" = $evasion
    "PORCE_UNREAL_TELEMETRY_INGEST_ENABLE" = "0"
    "PORCE_BRAIN_HTTP_PORT" = "$Port"
    "PORCE_OBSTACLE_TOKEN" = $Token
    "PORCE_OBSTACLE_TOKEN_REQUIRED" = "1"
    "PORCE_CONFIG_BANNER" = "0"
    "PORCE_AUDIT_ENABLE" = "1"
    "PORCE_AUDIT_ROOT" = $auditModeRoot
  }
  $previous = Set-ProcessEnv -map $envMap
  $stdoutPath = Join-Path $auditModeRoot "stdout.log"
  $stderrPath = Join-Path $auditModeRoot "stderr.log"
  $proc = $null
  try {
    $proc = Start-Process -FilePath $venvPython `
      -ArgumentList @("-u", "flight_controller.py") `
      -WorkingDirectory $pipelineDir `
      -RedirectStandardOutput $stdoutPath `
      -RedirectStandardError $stderrPath `
      -PassThru
  } finally {
    Restore-ProcessEnv -previous $previous
  }

  $baseUrl = "http://127.0.0.1:$Port"
  $status = Wait-Brain -BaseUrl $baseUrl -TimeoutSec 30
  if ($null -eq $status) {
    if ($proc -and -not $proc.HasExited) {
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-PortListeners -Port $Port
    Fail "$Mode Brain did not become ready on $baseUrl"
  }

  return [pscustomobject]@{
    Process = $proc
    BaseUrl = $baseUrl
    Status = $status
    AuditRoot = $auditModeRoot
  }
}

function Stop-BrainRuntime($runtime, [int]$Port) {
  if ($runtime -and $runtime.Process -and -not $runtime.Process.HasExited) {
    Stop-Process -Id $runtime.Process.Id -Force -ErrorAction SilentlyContinue
  }
  Stop-PortListeners -Port $Port
}

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) {
    Fail $Message
  }
}

function Invoke-AlignmentAudit([string]$RepoRoot, [string]$BaseUrl, [double]$WarnErrorM = 0.5) {
  $scriptPath = Join-Path $RepoRoot "tools\audit_spawn_alignment.ps1"
  if (-not (Test-Path $scriptPath)) {
    Fail "Alignment audit script not found: $scriptPath"
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -BrainUrl $BaseUrl -WarnErrorM $WarnErrorM | Out-Null
  return [int]$LASTEXITCODE
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportRoot = Join-Path $RepoRoot "pipeline\logs\zero_trust\$timestamp"
New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null
$reportPath = Join-Path $reportRoot "E2E_ZERO_TRUST_AUDIT.json"

$report = [ordered]@{
  repo_root = $RepoRoot
  started_at = (Get-Date).ToString("o")
  preflight = $null
  real_twin = $null
  simulation = $null
  unreal_build = $null
  overall_ok = $false
}

Info "Running strict zero-trust preflight..."
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "tools\preflight_zero_trust.ps1") -RepoRoot $RepoRoot -Strict
if ($LASTEXITCODE -ne 0) {
  Fail "preflight_zero_trust.ps1 -Strict failed"
}
$report.preflight = [ordered]@{
  strict = $true
  ok = $true
}

$realTwinToken = "0123456789abcdef0123456789abcdef"
$simToken = "abcdefabcdefabcdefabcdefabcdefab"

$realTwinRuntime = $null
$simulationRuntime = $null
try {
  Info "Auditing REAL_TWIN zero-trust runtime..."
  $realTwinRuntime = Start-BrainRuntime -Mode "REAL_TWIN" -Port $RealTwinPort -Token $realTwinToken -RepoRoot $RepoRoot -AuditRoot $reportRoot
  $status = $realTwinRuntime.Status
  $ui1 = Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $initialObstacleCount = @($ui1.obstacles).Count

  Assert-True ([string]$status.workflow -eq "REAL_TWIN") "REAL_TWIN status.workflow mismatch"
  Assert-True ([string]$status.control_mode -eq "PASSIVE_TWIN") "REAL_TWIN control_mode mismatch"
  Assert-True (@($ui1.waypoints).Count -eq 0) "REAL_TWIN should expose no waypoints"
  Assert-True (-not [bool]$ui1.evasion.active) "REAL_TWIN should expose evasion inactive"

  $unauthBody = @{ obstacles = @(@{ source = "vision"; source_id = 900; type = "bike"; confidence = 0.8; lat = [double]$ui1.home.lat; lon = [double]$ui1.home.lon }) } | ConvertTo-Json -Depth 5
  $unauthCode = 200
  try {
    Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/obstacles" -Method Post -ContentType "application/json" -Body $unauthBody | Out-Null
  } catch {
    $unauthCode = Get-HttpErrorStatusCode $_
  }
  Assert-True ($unauthCode -eq 401) "REAL_TWIN should reject obstacle POST without token"

  $headers = @{ "X-PORCE-Token" = $realTwinToken }
  $homeLat = [double]$ui1.home.lat
  $homeLon = [double]$ui1.home.lon

  $rogueBody = @{ obstacles = @(@{ source = "rogue"; source_id = 901; type = "bike"; confidence = 0.7; lat = $homeLat; lon = $homeLon }) } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/obstacles" -Method Post -Headers $headers -ContentType "application/json" -Body $rogueBody | Out-Null
  Start-Sleep -Milliseconds 500
  $uiAfterRogue = Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  Assert-True (@($uiAfterRogue.obstacles).Count -eq $initialObstacleCount) "REAL_TWIN source filter should reject non-vision source"

  $body1 = @{
    obstacles = @(
      @{ source = "vision"; source_id = 11; type = "biker"; confidence = 0.91; lat = ($homeLat + 0.000010); lon = ($homeLon + 0.000010) },
      @{ source = "vision"; source_id = 12; type = "cow"; confidence = 0.88; lat = ($homeLat + 0.000015); lon = ($homeLon + 0.000020) },
      @{ source = "vision"; source_id = 13; type = "tower"; confidence = 0.97; lat = ($homeLat + 0.000030); lon = ($homeLon + 0.000005) }
    )
  } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/obstacles" -Method Post -Headers $headers -ContentType "application/json" -Body $body1 | Out-Null
  Start-Sleep -Milliseconds 800
  $ui2 = Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $bike1 = $ui2.obstacles | Where-Object { $_.object_type -eq "bike" } | Select-Object -First 1
  $cow1 = $ui2.obstacles | Where-Object { $_.object_type -eq "cow" } | Select-Object -First 1
  $tower1 = $ui2.obstacles | Where-Object { $_.object_type -eq "tower" } | Select-Object -First 1
  Assert-True ($null -ne $bike1) "REAL_TWIN did not canonicalize bike obstacle"
  Assert-True ($null -ne $cow1) "REAL_TWIN missing cow obstacle"
  Assert-True ($null -ne $tower1) "REAL_TWIN missing tower obstacle"
  Assert-True ($null -ne $bike1.world_m) "REAL_TWIN bike obstacle missing world_m"
  $bikeEntityId = [string]$bike1.entity_id

  $alignmentExit = Invoke-AlignmentAudit -RepoRoot $RepoRoot -BaseUrl $realTwinRuntime.BaseUrl -WarnErrorM 0.5
  Assert-True ($alignmentExit -eq 0) "REAL_TWIN alignment audit failed"

  $body2 = @{ obstacles = @(@{ source = "vision"; source_id = 11; type = "bicycle"; confidence = 0.93; lat = ($homeLat + 0.000020); lon = ($homeLon + 0.000015) }) } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/obstacles" -Method Post -Headers $headers -ContentType "application/json" -Body $body2 | Out-Null
  Start-Sleep -Milliseconds 800
  $ui3 = Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $bike2 = $ui3.obstacles | Where-Object { $_.entity_id -eq $bikeEntityId } | Select-Object -First 1
  Assert-True ($null -ne $bike2) "REAL_TWIN bike entity_id not stable across updates"
  Assert-True ([string]$bike2.object_type -eq "bike") "REAL_TWIN bike object_type not canonical"
  Assert-True ([string]$bike2.object_id -eq $bikeEntityId) "REAL_TWIN object_id should match entity_id"

  Start-Sleep -Seconds 4
  $ui4 = Invoke-RestMethod -Uri "$($realTwinRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $bikeAfterTtl = $ui4.obstacles | Where-Object { $_.entity_id -eq $bikeEntityId } | Select-Object -First 1
  Assert-True ($null -eq $bikeAfterTtl) "REAL_TWIN dynamic bike obstacle did not despawn after TTL"

  $report.real_twin = [ordered]@{
    status_workflow = [string]$status.workflow
    control_mode = [string]$status.control_mode
    unauthorized_post_rejected = ($unauthCode -eq 401)
    rogue_source_filtered = (@($uiAfterRogue.obstacles).Count -eq $initialObstacleCount)
    canonical_types = @($ui2.obstacles | ForEach-Object { $_.object_type })
    bike_entity_id = $bikeEntityId
    alignment_ok = ($alignmentExit -eq 0)
    despawn_after_ttl_ok = ($null -eq $bikeAfterTtl)
    audit_root = $realTwinRuntime.AuditRoot
    ok = $true
  }
} finally {
  Stop-BrainRuntime -runtime $realTwinRuntime -Port $RealTwinPort
}

try {
  Info "Auditing SIMULATION zero-trust runtime..."
  $simulationRuntime = Start-BrainRuntime -Mode "SIMULATION" -Port $SimulationPort -Token $simToken -RepoRoot $RepoRoot -AuditRoot $reportRoot
  $status = $simulationRuntime.Status
  $ui1 = Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2

  Assert-True ([string]$status.workflow -eq "SIMULATION") "SIMULATION status.workflow mismatch"
  Assert-True ([string]$status.control_mode -eq "AUTONOMOUS") "SIMULATION control_mode mismatch"
  Assert-True (@($ui1.waypoints).Count -gt 0) "SIMULATION should expose mission waypoints"
  Assert-True ([int]$status.wp_idx -ge 1) "SIMULATION current wp index should start at or above 1"

  $unauthBody = @{ obstacles = @(@{ source = "vision"; source_id = 902; type = "bike"; confidence = 0.8; lat = [double]$ui1.home.lat; lon = [double]$ui1.home.lon }) } | ConvertTo-Json -Depth 5
  $unauthCode = 200
  try {
    Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/obstacles" -Method Post -ContentType "application/json" -Body $unauthBody | Out-Null
  } catch {
    $unauthCode = Get-HttpErrorStatusCode $_
  }
  Assert-True ($unauthCode -eq 401) "SIMULATION should reject obstacle POST without token"

  $headers = @{ "X-PORCE-Token" = $simToken }
  $homeLat = [double]$ui1.home.lat
  $homeLon = [double]$ui1.home.lon
  $body = @{ obstacles = @(@{ source = "vision"; source_id = 21; type = "person"; confidence = 0.89; lat = ($homeLat + 0.000020); lon = ($homeLon + 0.000015) }) } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/obstacles" -Method Post -Headers $headers -ContentType "application/json" -Body $body | Out-Null
  Start-Sleep -Milliseconds 800
  $ui2 = Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $bike = $ui2.obstacles | Where-Object { $_.entity_id -eq "vision:21" } | Select-Object -First 1
  Assert-True ($null -ne $bike) "SIMULATION did not retain authorized obstacle"
  Assert-True ([string]$bike.object_type -eq "bike") "SIMULATION did not canonicalize person -> bike"

  $report.simulation = [ordered]@{
    status_workflow = [string]$status.workflow
    control_mode = [string]$status.control_mode
    wp_idx = [int]$status.wp_idx
    waypoints_count = @($ui1.waypoints).Count
    unauthorized_post_rejected = ($unauthCode -eq 401)
    canonical_bike_ok = ([string]$bike.object_type -eq "bike")
    audit_root = $simulationRuntime.AuditRoot
    ok = $true
  }
} finally {
  Stop-BrainRuntime -runtime $simulationRuntime -Port $SimulationPort
}

if ($SkipUnrealBuild) {
  $report.unreal_build = [ordered]@{
    skipped = $true
    ok = $true
  }
} else {
  Info "Building Unreal project for zero-trust audit..."
  if (-not (Test-Path $EngineBuildBat)) {
    Fail "Unreal Build.bat not found: $EngineBuildBat"
  }
  & $EngineBuildBat AirTrafficEditor Win64 Development (Join-Path $RepoRoot "Unreal\AirTraffic.uproject")
  if ($LASTEXITCODE -ne 0) {
    Fail "Unreal build failed during audit"
  }
  $report.unreal_build = [ordered]@{
    skipped = $false
    ok = $true
    build_bat = $EngineBuildBat
  }
}

$report.ended_at = (Get-Date).ToString("o")
$report.overall_ok = $true
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding UTF8
Info "Audit report written to $reportPath"
Info "Zero-trust E2E audit PASSED"
