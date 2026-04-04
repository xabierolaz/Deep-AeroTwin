param(
  [string]$BrainUrl = "http://127.0.0.1:8080",
  [double]$WarnErrorM = 0.5
)

$ErrorActionPreference = "Stop"

function HaversineM([double]$lat1, [double]$lon1, [double]$lat2, [double]$lon2) {
  $r = 6371000.0
  $dLat = [Math]::PI / 180.0 * ($lat2 - $lat1)
  $dLon = [Math]::PI / 180.0 * ($lon2 - $lon1)
  $a =
    [Math]::Sin($dLat / 2.0) * [Math]::Sin($dLat / 2.0) +
    [Math]::Cos([Math]::PI / 180.0 * $lat1) * [Math]::Cos([Math]::PI / 180.0 * $lat2) *
    [Math]::Sin($dLon / 2.0) * [Math]::Sin($dLon / 2.0)
  $c = 2.0 * [Math]::Atan2([Math]::Sqrt($a), [Math]::Sqrt([Math]::Max(1e-12, 1.0 - $a)))
  return $r * $c
}

function LatLonToNEM([double]$latRef, [double]$lonRef, [double]$lat, [double]$lon) {
  $r = 6371000.0
  $dLat = [Math]::PI / 180.0 * ($lat - $latRef)
  $dLon = [Math]::PI / 180.0 * ($lon - $lonRef)
  $north = $dLat * $r
  $east = $dLon * $r * [Math]::Cos([Math]::PI / 180.0 * $latRef)
  return @($north, $east)
}

$ui = Invoke-RestMethod -Uri "$BrainUrl/api/ui/data" -TimeoutSec 3
if ($null -eq $ui.home -or $null -eq $ui.obstacles) {
  throw "Respuesta invalida desde $BrainUrl/api/ui/data"
}

$homeLat = [double]$ui.home.lat
$homeLon = [double]$ui.home.lon
$obs = @($ui.obstacles)

Write-Host "[audit_spawn_alignment] home=($homeLat,$homeLon) obstacles=$($obs.Count)"
if ($obs.Count -eq 0) {
  Write-Host "[audit_spawn_alignment] No hay obstaculos activos para auditar."
  exit 0
}

$maxErr = 0.0
$warn = $false

foreach ($o in $obs) {
  if ($null -eq $o.lat -or $null -eq $o.lon -or $null -eq $o.world_m) {
    continue
  }
  $lat = [double]$o.lat
  $lon = [double]$o.lon
  $calc = LatLonToNEM $homeLat $homeLon $lat $lon
  $northCalc = [double]$calc[0]
  $eastCalc = [double]$calc[1]
  $northUi = [double]$o.world_m.north
  $eastUi = [double]$o.world_m.east
  $err = [Math]::Sqrt(($northCalc - $northUi) * ($northCalc - $northUi) + ($eastCalc - $eastUi) * ($eastCalc - $eastUi))
  if ($err -gt $maxErr) { $maxErr = $err }
  if ($err -gt $WarnErrorM) { $warn = $true }

  $id = if ($o.entity_id) { [string]$o.entity_id } else { [string]$o.id }
  $type = [string]$o.type
  Write-Host ("  id={0} type={1} latlon=({2:F6},{3:F6}) world_m=({4:F2},{5:F2}) calc_ne=({6:F2},{7:F2}) err_m={8:F3}" -f `
    $id, $type, $lat, $lon, $northUi, $eastUi, $northCalc, $eastCalc, $err)
}

Write-Host ("[audit_spawn_alignment] max_err_m={0:F3} threshold={1:F3}" -f $maxErr, $WarnErrorM)
if ($warn) {
  Write-Host "[audit_spawn_alignment] WARN: discrepancia superior al umbral." -ForegroundColor Yellow
  exit 2
}
Write-Host "[audit_spawn_alignment] OK"
exit 0
