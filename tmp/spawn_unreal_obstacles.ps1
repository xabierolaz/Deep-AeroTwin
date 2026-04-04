param(
  [string]$BrainUrl = "http://127.0.0.1:8080",
  [double]$DurationS = 12.0,
  [double]$Hz = 2.0,
  [switch]$NoToken
)

$ErrorActionPreference = "Stop"

function Resolve-Token {
  if ($NoToken) { return "" }
  $envToken = [System.Environment]::GetEnvironmentVariable("PORCE_OBSTACLE_TOKEN")
  if (-not [string]::IsNullOrWhiteSpace($envToken)) {
    return $envToken.Trim()
  }
  $tokenFile = Join-Path $PSScriptRoot "..\pipeline\logs\zero_trust\OBSTACLE_TOKEN.txt"
  if (Test-Path $tokenFile) {
    return (Get-Content -Path $tokenFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  }
  return ""
}

function Offset-LatLon([double]$latDeg, [double]$lonDeg, [double]$northM, [double]$eastM) {
  $earth = 6371000.0
  $dLat = $northM / $earth
  $cosLat = [Math]::Cos($latDeg * [Math]::PI / 180.0)
  if ([Math]::Abs($cosLat) -lt 1e-6) { $cosLat = 1e-6 }
  $dLon = $eastM / ($earth * $cosLat)
  $lat2 = $latDeg + ($dLat * 180.0 / [Math]::PI)
  $lon2 = $lonDeg + ($dLon * 180.0 / [Math]::PI)
  return @($lat2, $lon2)
}

if ($Hz -le 0) { throw "Hz debe ser > 0" }
if ($DurationS -le 0) { throw "DurationS debe ser > 0" }

$ui = Invoke-RestMethod -Uri "$BrainUrl/api/ui/data" -TimeoutSec 3
if (-not $ui.home -or $null -eq $ui.home.lat -or $null -eq $ui.home.lon) {
  throw "No se pudo leer home desde $BrainUrl/api/ui/data"
}

$homeLat = [double]$ui.home.lat
$homeLon = [double]$ui.home.lon
$token = Resolve-Token
$headers = @{}
if (-not [string]::IsNullOrWhiteSpace($token)) {
  $headers["X-PORCE-Token"] = $token
}

$patterns = @(
  @{ id = 9101; type = "tower"; north = 30.0; east = 8.0; conf = 0.95 },
  @{ id = 9102; type = "cow";   north = 18.0; east = -6.0; conf = 0.90 },
  @{ id = 9103; type = "biker"; north = 24.0; east = 3.0; conf = 0.92 }
)

$intervalMs = [int]([Math]::Round(1000.0 / $Hz))
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$sent = 0

Write-Host "[spawn_unreal_obstacles] Brain=$BrainUrl duration=${DurationS}s hz=$Hz token=$([string]::IsNullOrWhiteSpace($token) -eq $false)"

while ($stopwatch.Elapsed.TotalSeconds -lt $DurationS) {
  $obstacles = @()
  foreach ($p in $patterns) {
    $latLon = Offset-LatLon $homeLat $homeLon ([double]$p.north) ([double]$p.east)
    $distance = [Math]::Sqrt(([double]$p.north * [double]$p.north) + ([double]$p.east * [double]$p.east))
    $obstacles += @{
      id = [int]$p.id
      source_id = [int]$p.id
      lat = [double]$latLon[0]
      lon = [double]$latLon[1]
      distance = [double]$distance
      type = [string]$p.type
      confidence = [double]$p.conf
      source = "vision"
    }
  }

  $body = @{ obstacles = $obstacles } | ConvertTo-Json -Depth 4
  try {
    $null = Invoke-RestMethod -Uri "$BrainUrl/api/obstacles" -Method Post -ContentType "application/json" -Headers $headers -Body $body -TimeoutSec 2
    $sent += 1
  } catch {
    Write-Host "[spawn_unreal_obstacles] ERROR posting obstacles: $($_.Exception.Message)"
    break
  }

  Start-Sleep -Milliseconds $intervalMs
}

Write-Host "[spawn_unreal_obstacles] Done. posts_sent=$sent"
