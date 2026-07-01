param(
  [string]$RepoRoot = "",
  [string]$EngineRoot = "",
  [string]$EngineBuildBat = "",
  [int]$RealTwinPort = 18082,
  [int]$SimulationPort = 18083,
  [switch]$SkipSppaReflection,
  [switch]$SkipUnrealBuild
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "unreal_engine_paths.ps1")

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

function Get-ProcessInfoById([int]$ProcessId) {
  try {
    return Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId)
  } catch {
    return $null
  }
}

function Format-ProcessInfo($processInfo) {
  if ($null -eq $processInfo) {
    return "<unknown process>"
  }
  $cmd = ($processInfo.CommandLine | ForEach-Object { $_ }) -join ""
  if ($cmd.Length -gt 220) {
    $cmd = $cmd.Substring(0, 220) + "..."
  }
  return "pid=$($processInfo.ProcessId) name=$($processInfo.Name) exe=$($processInfo.ExecutablePath) cmd=$cmd"
}

function Get-FreeLocalTcpPort() {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try {
    $listener.Start()
    return [int]$listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Test-IsOwnedAuditBrainProcess($processInfo, [string]$RepoRoot) {
  if ($null -eq $processInfo) {
    return $false
  }

  $name = (($processInfo.Name | ForEach-Object { $_ }) -join "").ToLowerInvariant()
  $cmd = (($processInfo.CommandLine | ForEach-Object { $_ }) -join "").ToLowerInvariant()
  $exe = (($processInfo.ExecutablePath | ForEach-Object { $_ }) -join "").ToLowerInvariant()
  $repo = $RepoRoot.ToLowerInvariant().TrimEnd([char[]]@('\', '/'))
  $venvPrefix = (Join-Path $repo "venv\scripts\").ToLowerInvariant()

  return (
    $name -match '^python(?:3)?(?:w)?\.exe$' -and
    $cmd -match 'flight_controller\.py' -and
    $exe.StartsWith($venvPrefix)
  )
}

function Resolve-AuditPort([string]$Name, [int]$Port, [bool]$Explicit, [string]$RepoRoot) {
  $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  if ($listeners.Count -eq 0) {
    return $Port
  }

  $foreignListeners = @()
  foreach ($listener in $listeners) {
    $owner = Get-ProcessInfoById -ProcessId ([int]$listener.OwningProcess)
    if (-not (Test-IsOwnedAuditBrainProcess -processInfo $owner -RepoRoot $RepoRoot)) {
      $foreignListeners += (Format-ProcessInfo $owner)
    }
  }

  if ($foreignListeners.Count -eq 0) {
    return $Port
  }

  if ($Explicit) {
    Fail "$Name audit port ${Port} is occupied by non-PORCE listener(s): $($foreignListeners -join '; ')"
  }

  $fallback = Get-FreeLocalTcpPort
  Info "$Name audit port ${Port} is occupied by non-PORCE listener(s); using free port ${fallback}."
  return $fallback
}

function Stop-PortListeners([int]$Port, [string]$RepoRoot) {
  while ($true) {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { break }
    $listeners | ForEach-Object {
      $ownerPid = [int]$_.OwningProcess
      $owner = Get-ProcessInfoById -ProcessId $ownerPid
      if (-not (Test-IsOwnedAuditBrainProcess -processInfo $owner -RepoRoot $RepoRoot)) {
        Fail "Refusing to kill non-PORCE listener on audit port ${Port}: $(Format-ProcessInfo $owner)"
      }
      Info "Stopping stale PORCE audit listener on port ${Port}: $(Format-ProcessInfo $owner)"
      Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
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

  Stop-PortListeners -Port $Port -RepoRoot $RepoRoot

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
    Stop-PortListeners -Port $Port -RepoRoot $RepoRoot
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
  Stop-PortListeners -Port $Port -RepoRoot $RepoRoot
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

function Read-SppaBackendEvidence([string]$ReportPath) {
  if (-not (Test-Path $ReportPath)) {
    Fail "SPPA backend report not found after verifier succeeded: $ReportPath"
  }

  try {
    $sppa = Get-Content $ReportPath -Raw | ConvertFrom-Json
  } catch {
    Fail "Could not parse SPPA backend report JSON: $ReportPath"
  }

  if (-not [bool]$sppa.ok) {
    $failures = @($sppa.failures) -join "; "
    Fail "SPPA backend report ok=false: $failures"
  }

  $backendEnumValues = @($sppa.backend_enum_values | ForEach-Object { [string]$_ })
  foreach ($requiredBackend in @("SEMANTIC_PROXY", "UNREAL_ASSETS")) {
    if ($backendEnumValues -notcontains $requiredBackend) {
      Fail "SPPA backend report missing backend enum value: $requiredBackend"
    }
  }

  $defaults = [ordered]@{}
  if ($sppa.component_defaults -and $sppa.component_defaults.defaults) {
    foreach ($prop in $sppa.component_defaults.defaults.PSObject.Properties) {
      $row = $prop.Value
      $rowProps = @($row.PSObject.Properties.Name)
      foreach ($field in @("ok", "expected", "value")) {
        if ($rowProps -notcontains $field) {
          Fail "SPPA backend report malformed component default '$($prop.Name)': missing '$field'"
        }
      }
      $defaults[$prop.Name] = [ordered]@{
        ok = [bool]$row.ok
        expected = [string]$row.expected
        value = [string]$row.value
      }
    }
  }

  foreach ($requiredDefault in @("SpawnBackend", "EndpointUrl", "bEnabled", "bShowSpawnBackendSwitchUI", "PollRateHz")) {
    if (-not $defaults.Contains($requiredDefault)) {
      Fail "SPPA backend report missing component default evidence: $requiredDefault"
    }
    if (-not [bool]$defaults[$requiredDefault].ok) {
      Fail "SPPA backend component default failed for $requiredDefault (expected=$($defaults[$requiredDefault].expected), value=$($defaults[$requiredDefault].value))"
    }
  }

  $rawSwitchRows = @($sppa.component_switch.rows)
  if ($rawSwitchRows.Count -eq 0) {
    Fail "SPPA backend report missing component switch evidence rows"
  }

  $switchRows = @()
  foreach ($rawRow in $rawSwitchRows) {
    $rowProps = @($rawRow.PSObject.Properties.Name)
    foreach ($field in @("action", "backend", "is_proxy")) {
      if ($rowProps -notcontains $field) {
        Fail "SPPA backend report malformed switch row: missing '$field'"
      }
    }
    $switchRows += [ordered]@{
      action = [string]$rawRow.action
      backend = [string]$rawRow.backend
      is_proxy = [bool]$rawRow.is_proxy
    }
  }

  $expectedSwitchRows = [ordered]@{
    set_assets = $false
    set_proxy = $true
    toggle_to_assets = $false
    toggle_to_proxy = $true
  }
  foreach ($action in $expectedSwitchRows.Keys) {
    $matches = @($switchRows | Where-Object { $_.action -eq $action })
    if ($matches.Count -ne 1) {
      Fail "SPPA backend report expected exactly one switch row for action '$action', found $($matches.Count)"
    }
    $expectedIsProxy = [bool]$expectedSwitchRows[$action]
    $actualIsProxy = [bool](($matches[0]).is_proxy)
    if ($actualIsProxy -ne $expectedIsProxy) {
      Fail "SPPA backend switch row '$action' has is_proxy=$actualIsProxy, expected $expectedIsProxy"
    }
  }

  $rawProxyRows = @($sppa.proxy_generation.rows)
  if ($rawProxyRows.Count -eq 0) {
    Fail "SPPA backend report missing proxy generation evidence rows"
  }

  $proxyRows = @()
  foreach ($rawRow in $rawProxyRows) {
    $rowProps = @($rawRow.PSObject.Properties.Name)
    foreach ($field in @("class_name", "confirmed", "mesh_component_count", "collision_enabled_count")) {
      if ($rowProps -notcontains $field) {
        Fail "SPPA backend report malformed proxy row: missing '$field'"
      }
    }
    $proxyRows += [ordered]@{
      class_name = [string]$rawRow.class_name
      confirmed = [bool]$rawRow.confirmed
      mesh_component_count = [int]$rawRow.mesh_component_count
      collision_enabled_count = [int]$rawRow.collision_enabled_count
    }
  }

  $expectedProxyRows = @(
    [ordered]@{ class_name = "bike"; min_mesh = 6; min_collision = 1; confirmed = $true },
    [ordered]@{ class_name = "cow"; min_mesh = 7; min_collision = 1; confirmed = $true },
    [ordered]@{ class_name = "tower"; min_mesh = 4; min_collision = 1; confirmed = $true },
    [ordered]@{ class_name = "unknown"; min_mesh = 3; min_collision = 0; max_collision = 0; confirmed = $false }
  )
  foreach ($expected in $expectedProxyRows) {
    $className = [string]$expected["class_name"]
    $matches = @($proxyRows | Where-Object { $_.class_name -eq $className })
    if ($matches.Count -ne 1) {
      Fail "SPPA backend report expected exactly one proxy row for class '$className', found $($matches.Count)"
    }

    $row = $matches[0]
    $expectedConfirmed = [bool]$expected["confirmed"]
    $actualConfirmed = [bool]$row.confirmed
    if ($actualConfirmed -ne $expectedConfirmed) {
      Fail "SPPA backend proxy row '$className' has confirmed=$actualConfirmed, expected $expectedConfirmed"
    }
    if ([int]$row.mesh_component_count -lt [int]$expected["min_mesh"]) {
      Fail "SPPA backend proxy row '$className' has mesh_component_count=$($row.mesh_component_count), expected at least $($expected["min_mesh"])"
    }
    if ([int]$row.collision_enabled_count -lt [int]$expected["min_collision"]) {
      Fail "SPPA backend proxy row '$className' has collision_enabled_count=$($row.collision_enabled_count), expected at least $($expected["min_collision"])"
    }
    if ($expected.Contains("max_collision") -and [int]$row.collision_enabled_count -gt [int]$expected["max_collision"]) {
      Fail "SPPA backend proxy row '$className' has collision_enabled_count=$($row.collision_enabled_count), expected at most $($expected["max_collision"])"
    }
  }

  if (-not $sppa.proxy_reconfigure) {
    Fail "SPPA backend report missing proxy reconfigure evidence"
  }
  $reconfigureProps = @($sppa.proxy_reconfigure.PSObject.Properties.Name)
  foreach ($field in @("bike_mesh_component_count", "cow_mesh_component_count", "tags_after_reconfigure", "failures")) {
    if ($reconfigureProps -notcontains $field) {
      Fail "SPPA backend proxy reconfigure evidence missing '$field'"
    }
  }
  if (@($sppa.proxy_reconfigure.failures).Count -gt 0) {
    Fail "SPPA backend proxy reconfigure failures: $(@($sppa.proxy_reconfigure.failures) -join '; ')"
  }
  $reconfigureTags = @($sppa.proxy_reconfigure.tags_after_reconfigure | ForEach-Object { [string]$_ })
  if ($reconfigureTags -contains "PORCE_CLASS_bike") {
    Fail "SPPA backend proxy reconfigure retained stale PORCE_CLASS_bike tag"
  }
  if ($reconfigureTags -notcontains "PORCE_CLASS_cow") {
    Fail "SPPA backend proxy reconfigure did not retain PORCE_CLASS_cow tag"
  }

  if (-not $sppa.proxy_unknown_fallback) {
    Fail "SPPA backend report missing proxy unknown fallback evidence"
  }
  $unknownFallbackProps = @($sppa.proxy_unknown_fallback.PSObject.Properties.Name)
  foreach ($field in @("mesh_component_count", "collision_enabled_count", "tags", "failures")) {
    if ($unknownFallbackProps -notcontains $field) {
      Fail "SPPA backend proxy unknown fallback evidence missing '$field'"
    }
  }
  if (@($sppa.proxy_unknown_fallback.failures).Count -gt 0) {
    Fail "SPPA backend proxy unknown fallback failures: $(@($sppa.proxy_unknown_fallback.failures) -join '; ')"
  }
  $unknownFallbackTags = @($sppa.proxy_unknown_fallback.tags | ForEach-Object { [string]$_ })
  if ($unknownFallbackTags -notcontains "PORCE_CLASS_unknown") {
    Fail "SPPA backend proxy unknown fallback did not tag PORCE_CLASS_unknown"
  }
  if ($unknownFallbackTags -contains "PORCE_CLASS_") {
    Fail "SPPA backend proxy unknown fallback retained blank PORCE_CLASS_ tag"
  }

  return [ordered]@{
    ok = [bool]$sppa.ok
    schema_ok = $true
    backend_enum_values = @($sppa.backend_enum_values)
    component_defaults = $defaults
    component_switch = $switchRows
    proxy_generation = $proxyRows
    proxy_reconfigure = [ordered]@{
      bike_mesh_component_count = [int]$sppa.proxy_reconfigure.bike_mesh_component_count
      cow_mesh_component_count = [int]$sppa.proxy_reconfigure.cow_mesh_component_count
      tags_after_reconfigure = $reconfigureTags
    }
    proxy_unknown_fallback = [ordered]@{
      mesh_component_count = [int]$sppa.proxy_unknown_fallback.mesh_component_count
      collision_enabled_count = [int]$sppa.proxy_unknown_fallback.collision_enabled_count
      tags = $unknownFallbackTags
    }
  }
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$enginePaths = Get-PorceUnrealEnginePaths -EngineRoot $EngineRoot
if (-not $EngineBuildBat) {
  $EngineBuildBat = $enginePaths.BuildBat
}

$realTwinPortExplicit = $PSBoundParameters.ContainsKey("RealTwinPort")
$simulationPortExplicit = $PSBoundParameters.ContainsKey("SimulationPort")
$RealTwinPort = Resolve-AuditPort -Name "REAL_TWIN" -Port $RealTwinPort -Explicit $realTwinPortExplicit -RepoRoot $RepoRoot
$SimulationPort = Resolve-AuditPort -Name "SIMULATION" -Port $SimulationPort -Explicit $simulationPortExplicit -RepoRoot $RepoRoot
if ($RealTwinPort -eq $SimulationPort) {
  if ($realTwinPortExplicit -or $simulationPortExplicit) {
    Fail "REAL_TWIN and SIMULATION audit ports must differ; both resolved to ${RealTwinPort}."
  }
  $SimulationPort = Get-FreeLocalTcpPort
  Info "SIMULATION audit port collided with REAL_TWIN; using free port ${SimulationPort}."
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportRoot = Join-Path $RepoRoot "pipeline\logs\zero_trust\$timestamp"
New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null
$reportPath = Join-Path $reportRoot "E2E_ZERO_TRUST_AUDIT.json"

$report = [ordered]@{
  repo_root = $RepoRoot
  started_at = (Get-Date).ToString("o")
  preflight = $null
  ports = [ordered]@{
    real_twin = $RealTwinPort
    simulation = $SimulationPort
  }
  sppa_backend = $null
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

if ($SkipSppaReflection) {
  $report.sppa_backend = [ordered]@{
    skipped = $true
    ok = $true
  }
} else {
  Info "Running SPPA backend Unreal reflection smoke..."
  $sppaVerifyScript = Join-Path $RepoRoot "tools\verify_sppa_backend.ps1"
  if (-not (Test-Path $sppaVerifyScript)) {
    Fail "SPPA backend verifier not found: $sppaVerifyScript"
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $sppaVerifyScript -RepoRoot $RepoRoot -EngineRoot $enginePaths.Root
  if ($LASTEXITCODE -ne 0) {
    Fail "SPPA backend reflection smoke failed"
  }
  $sppaReportPath = Join-Path $RepoRoot "pipeline\logs\sppa_backend_verify_latest.json"
  $sppaEvidence = Read-SppaBackendEvidence -ReportPath $sppaReportPath
  $report.sppa_backend = [ordered]@{
    skipped = $false
    ok = $true
    verifier = $sppaVerifyScript
    log_path = (Join-Path $RepoRoot "pipeline\logs\sppa_backend_verify_latest.log")
    report_path = $sppaReportPath
    evidence = $sppaEvidence
  }
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
  $explicitWorldNorth = 12.5
  $explicitWorldEast = -3.25
  $explicitWorldUp = 1.5
  $body = @{
    obstacles = @(
      @{
        source = "vision"
        source_id = 21
        type = "person"
        confidence = 0.89
        world_m = @{
          north = $explicitWorldNorth
          east = $explicitWorldEast
          up = $explicitWorldUp
        }
        heading_rad = ([Math]::PI / 2.0)
      }
    )
  } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/obstacles" -Method Post -Headers $headers -ContentType "application/json" -Body $body | Out-Null
  Start-Sleep -Milliseconds 800
  $ui2 = Invoke-RestMethod -Uri "$($simulationRuntime.BaseUrl)/api/ui/data" -TimeoutSec 2
  $bike = $ui2.obstacles | Where-Object { $_.entity_id -eq "vision:21" } | Select-Object -First 1
  Assert-True ($null -ne $bike) "SIMULATION did not retain authorized obstacle"
  Assert-True ([string]$bike.object_type -eq "bike") "SIMULATION did not canonicalize person -> bike"
  Assert-True ($null -ne $bike.world_m) "SIMULATION did not preserve explicit obstacle world_m"
  Assert-True ([Math]::Abs(([double]$bike.world_m.north) - $explicitWorldNorth) -lt 0.001) "SIMULATION explicit obstacle world_m.north mismatch"
  Assert-True ([Math]::Abs(([double]$bike.world_m.east) - $explicitWorldEast) -lt 0.001) "SIMULATION explicit obstacle world_m.east mismatch"
  Assert-True ([Math]::Abs(([double]$bike.world_m.up) - $explicitWorldUp) -lt 0.001) "SIMULATION explicit obstacle world_m.up mismatch"
  Assert-True ([Math]::Abs(([double]$bike.yaw_deg) - 90.0) -lt 0.001) "SIMULATION did not convert heading_rad to yaw_deg"

  $report.simulation = [ordered]@{
    status_workflow = [string]$status.workflow
    control_mode = [string]$status.control_mode
    wp_idx = [int]$status.wp_idx
    waypoints_count = @($ui1.waypoints).Count
    unauthorized_post_rejected = ($unauthCode -eq 401)
    canonical_bike_ok = ([string]$bike.object_type -eq "bike")
    explicit_world_m_ok = (
      $null -ne $bike.world_m -and
      [Math]::Abs(([double]$bike.world_m.north) - $explicitWorldNorth) -lt 0.001 -and
      [Math]::Abs(([double]$bike.world_m.east) - $explicitWorldEast) -lt 0.001 -and
      [Math]::Abs(([double]$bike.world_m.up) - $explicitWorldUp) -lt 0.001
    )
    heading_rad_to_yaw_deg_ok = ([Math]::Abs(([double]$bike.yaw_deg) - 90.0) -lt 0.001)
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
    engine_root = $enginePaths.Root
    build_bat = $EngineBuildBat
  }
}

$report.ended_at = (Get-Date).ToString("o")
$report.overall_ok = $true
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportPath -Encoding UTF8
$latestRunPath = Join-Path (Split-Path -Parent $reportRoot) "LATEST_RUN.txt"
Set-Content -Path $latestRunPath -Encoding UTF8 -Value $reportRoot
Info "Audit report written to $reportPath"
Info "Zero-trust E2E audit PASSED"
