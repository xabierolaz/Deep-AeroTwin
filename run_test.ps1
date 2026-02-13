param(
  [string]$Scenario = "porce_off_no_detections",
  [int]$ScenarioTimeout = 420,
  [int]$ArmTimeout = 240,
  [int]$TakeoffTimeout = 180
)

# Safe wrapper around the Pipeline A E2E runner.
# NOTE: This intentionally does NOT kill all python.exe processes.

Set-Location $PSScriptRoot

Write-Host "[E2E] Scenario=$Scenario timeout=$ScenarioTimeout arm_timeout=$ArmTimeout takeoff_timeout=$TakeoffTimeout"
python pipeline\e2e_flight_matrix.py `
  --scenario $Scenario `
  --scenario-timeout $ScenarioTimeout `
  --arm-timeout $ArmTimeout `
  --takeoff-timeout $TakeoffTimeout

exit $LASTEXITCODE

