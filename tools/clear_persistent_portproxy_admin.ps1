param(
  [int[]]$Ports = @(5760, 5762),
  [string]$ListenAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
  Write-Host "[portproxy] This cleanup requires an elevated PowerShell/cmd window."
  Write-Host "[portproxy] Run as Administrator:"
  foreach ($port in $Ports) {
    Write-Host ("  netsh interface portproxy delete v4tov4 listenaddress={0} listenport={1}" -f $ListenAddress, $port)
  }
  exit 2
}

foreach ($port in $Ports) {
  Write-Host ("[portproxy] deleting {0}:{1}" -f $ListenAddress, $port)
  & netsh.exe interface portproxy delete v4tov4 listenaddress=$ListenAddress listenport=$port
}

Write-Host "[portproxy] remaining rules:"
& netsh.exe interface portproxy show all
