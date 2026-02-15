<#
Deep-AeroTwin: Fix/Setup real WSL2 + Ubuntu + ArduPilot SITL.

Run from an elevated PowerShell (Run as Administrator).

This script is intentionally "step based" and stops when a reboot or first-run
Ubuntu user setup is required. Re-run it after completing those steps.
#>

[CmdletBinding()]
param(
  # Distro name as shown by `wsl -l -q` (e.g. Ubuntu, Ubuntu-22.04).
  # Leave empty to auto-select the current default installed distro.
  [string]$Distro = "",

  # Skip enabling Windows optional features (WSL + VM Platform).
  [switch]$SkipWindowsFeatures,

  # Skip `wsl --update`.
  [switch]$SkipWslUpdate,

  # Skip installing the distro if missing.
  [switch]$SkipDistroInstall,

  # Skip building ArduPilot SITL inside WSL.
  [switch]$SkipSITLBuild,

  # Skip running repo preflight at the end.
  [switch]$SkipPreflight,

  # Keep the console open at the end (useful if launched by double-click).
  [switch]$PauseOnExit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function _ts() { return (Get-Date).ToString("HH:mm:ss") }
function _say([string]$msg) { Write-Host ("[{0}] {1}" -f (_ts), $msg) }
function _ok([string]$msg) { _say ("[OK]  {0}" -f $msg) }
function _warn([string]$msg) { _say ("[WARN] {0}" -f $msg) }
function _fail([string]$msg) { _say ("[FAIL] {0}" -f $msg) }
function _step([int]$n, [string]$msg) { _say ""; _say ("== STEP {0}: {1} ==" -f $n, $msg) }

function _is_admin() {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function _run([string]$label, [string[]]$argv) {
  # NOTE: Do not name this parameter `$args` (automatic variable in PowerShell).
  if (-not $argv -or $argv.Count -lt 1 -or [string]::IsNullOrWhiteSpace($argv[0])) {
    throw ("internal_error:_run_empty_argv:{0}" -f $label)
  }
  _say ("$ {0}" -f ($argv -join " "))
  $exe = $argv[0]
  $exeArgs = @()
  if ($argv.Count -gt 1) {
    $exeArgs = $argv[1..($argv.Count-1)]
  }
  # Native commands writing to stderr become PowerShell "non-terminating errors".
  # With $ErrorActionPreference='Stop' (used elsewhere for cmdlets), those would
  # throw. Temporarily relax for native command execution so we can report the
  # output + exit code ourselves.
  $oldEap = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $out = & $exe @exeArgs 2>&1
  } finally {
    $ErrorActionPreference = $oldEap
  }
  $code = $LASTEXITCODE
  if ($code -eq 0) {
    _ok $label
  } else {
    _warn ("{0} (exit={1})" -f $label, $code)
  }
  $outArr = @()
  if ($null -ne $out) { $outArr = @($out) }
  $outText = ($outArr | ForEach-Object { $_.ToString() }) -join "`n"
  return [pscustomobject]@{ ExitCode = $code; Output = $outText }
}

function _get_feature_state([string]$featureName) {
  try {
    $f = Get-WindowsOptionalFeature -Online -FeatureName $featureName -ErrorAction Stop
    return [string]$f.State
  } catch {
    # Fallback to DISM if the cmdlet is unavailable.
    $out = & dism.exe /online /get-featureinfo /featurename:$featureName 2>&1
    if ($LASTEXITCODE -ne 0) { return "Unknown" }
    if ($out -match "State\\s*:\\s*Enabled") { return "Enabled" }
    if ($out -match "State\\s*:\\s*Disabled") { return "Disabled" }
    return "Unknown"
  }
}

function _enable_feature([string]$featureName) {
  try {
    $r = Enable-WindowsOptionalFeature -Online -FeatureName $featureName -All -NoRestart -ErrorAction Stop
    return [bool]$r.RestartNeeded
  } catch {
    # DISM does not reliably report restart requirement; assume reboot may be needed.
    & dism.exe /online /enable-feature /featurename:$featureName /all /norestart | Out-Null
    return $true
  }
}

function _service_restart_if_present([string]$name) {
  $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
  if (-not $svc) {
    _warn ("service not present: {0}" -f $name)
    return
  }
  try {
    if ($svc.Status -eq "Running") {
      Restart-Service -Name $name -Force -ErrorAction Stop
      _ok ("service restarted: {0}" -f $name)
    } else {
      Start-Service -Name $name -ErrorAction Stop
      _ok ("service started: {0}" -f $name)
    }
  } catch {
    _warn ("service failed: {0} ({1})" -f $name, $_.Exception.Message)
  }
}

if (-not (_is_admin)) {
  _fail "Run this from an elevated PowerShell (Right click -> Run as Administrator)."
  exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logDir = Join-Path $repoRoot "pipeline\\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$transcriptPath = Join-Path $logDir ("fix_wsl_sitl_real_{0}.txt" -f $ts)
$lastLogPointer = Join-Path $logDir "last_fix_wsl_sitl_real.txt"

try {
  Set-Content -Path $lastLogPointer -Value $transcriptPath -Encoding ASCII -Force
} catch {
  # Best-effort only.
}

$transcriptStarted = $false
try {
  Start-Transcript -Path $transcriptPath -Append | Out-Null
  $transcriptStarted = $true
} catch {
  _warn ("Could not start transcript: {0}" -f $_.Exception.Message)
}

try {
  _say "== Deep-AeroTwin: real WSL2 + SITL setup =="
  _ok ("repoRoot: {0}" -f $repoRoot)
  _ok ("log: {0}" -f $transcriptPath)

  _step 1 "Host info / prerequisites"
  try {
    $os = Get-CimInstance Win32_OperatingSystem
    _ok ("OS: {0} (build {1})" -f $os.Caption, $os.BuildNumber)
  } catch {
    _warn ("OS query failed: {0}" -f $_.Exception.Message)
  }
  try {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($null -ne $cpu.VirtualizationFirmwareEnabled) {
      if ($cpu.VirtualizationFirmwareEnabled) { _ok "CPU virtualization: enabled in firmware" } else { _warn "CPU virtualization: DISABLED in firmware (enable VT-x/AMD-V in BIOS/UEFI)" }
    } else {
      _warn "Could not query CPU virtualization firmware flag."
    }
  } catch {
    _warn ("CPU query failed: {0}" -f $_.Exception.Message)
  }

  if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    _fail "wsl.exe not found. Install WSL from Microsoft Store or enable Windows feature first."
    exit 2
  }
  _ok "wsl.exe found"

  _step 2 "Enable Windows optional features (WSL + VM Platform)"
  $features = @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform")
  $needReboot = $false
  foreach ($f in $features) {
    $state = _get_feature_state $f
    if ($state -eq "Enabled") {
      _ok ("feature enabled: {0}" -f $f)
      continue
    }
    _warn ("feature state: {0} = {1}" -f $f, $state)
    if ($SkipWindowsFeatures) {
      _warn "SkipWindowsFeatures is set; not enabling features."
      continue
    }
    _say ("Enabling feature: {0}" -f $f)
    $reboot = _enable_feature $f
    $needReboot = $needReboot -or $reboot
    $state2 = _get_feature_state $f
    if ($state2 -eq "Enabled") { _ok ("feature enabled: {0}" -f $f) } else { _warn ("feature still not enabled: {0} (state={1})" -f $f, $state2) }
  }

  if ($needReboot) {
    _warn "Windows reported a reboot may be required."
    _say "Action: reboot Windows, then re-run this script."
    exit 3010
  }

  _step 3 "WSL services + status"
  # Make sure the hypervisor is not forcibly disabled.
  try {
    & bcdedit /set hypervisorlaunchtype auto | Out-Null
    _ok "bcdedit: hypervisorlaunchtype=auto (best-effort)"
  } catch {
    _warn ("bcdedit failed (best-effort): {0}" -f $_.Exception.Message)
  }

  _service_restart_if_present "WslService"
  _service_restart_if_present "LxssManager"
  _service_restart_if_present "vmcompute"

  # First, try a clean shutdown to avoid stale state.
  _run "wsl --shutdown" @("wsl.exe", "--shutdown") | Out-Null

  $st = _run "wsl --status" @("wsl.exe", "--status")
  if ($st.ExitCode -ne 0) {
    _fail "WSL status failed."
    _say $st.Output
    _say "Hints:"
    _say "  1) Ensure virtualization is enabled in BIOS/UEFI (VT-x/AMD-V)."
    _say "  2) Reboot, then run: wsl --status"
    _say "  3) If it still fails with E_ACCESSDENIED, check Windows security/policy restrictions for WSL."
    exit 3
  }
  _say $st.Output

  $lv = _run "wsl -l -v" @("wsl.exe", "-l", "-v")
  if ($lv.ExitCode -ne 0) {
    _warn "Could not list WSL distros."
    _say $lv.Output
  } else {
    _say $lv.Output
  }

  _step 4 "WSL update + default version"
  if (-not $SkipWslUpdate) {
    $up = _run "wsl --update" @("wsl.exe", "--update")
    if ($up.ExitCode -ne 0) {
      _warn "wsl --update failed (often transient / network / Store). Continuing."
      _say $up.Output
    }
  } else {
    _warn "SkipWslUpdate is set; not running wsl --update."
  }

  $dv = _run "wsl --set-default-version 2" @("wsl.exe", "--set-default-version", "2")
  if ($dv.ExitCode -ne 0) {
    _warn "Could not set default WSL version to 2."
    _say $dv.Output
  }

  _step 5 "Ensure a WSL distro exists and is WSL2"
  $installed = _run "wsl -l -q" @("wsl.exe", "-l", "-q")
  if ($installed.ExitCode -ne 0) {
    _fail "Could not list installed distros (wsl -l -q)."
    _say $installed.Output
    exit 4
  }

  $distros = ($installed.Output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  $distros = @($distros | Where-Object { $_ -ne "" })

  $defaultDistro = ""
  if ($lv.ExitCode -eq 0) {
    foreach ($ln in ($lv.Output -split "`r?`n")) {
      if ($ln -match "^\\s*\\*\\s*(\\S+)") {
        $defaultDistro = $Matches[1].Trim()
        break
      }
    }
  }

  $requested = ""
  if ($null -ne $Distro) { $requested = $Distro.Trim() }
  $chosen = $requested
  if ([string]::IsNullOrWhiteSpace($chosen)) {
    if ($distros.Count -eq 0) {
      $chosen = "Ubuntu-22.04"
      _warn ("No distros installed. Will install: {0}" -f $chosen)
    } elseif (-not [string]::IsNullOrWhiteSpace($defaultDistro) -and ($distros -contains $defaultDistro)) {
      $chosen = $defaultDistro
      _ok ("Auto-selected default distro: {0}" -f $chosen)
    } elseif ($distros -contains "Ubuntu") {
      $chosen = "Ubuntu"
      _ok ("Auto-selected distro: {0}" -f $chosen)
    } else {
      $chosen = $distros[0]
      _ok ("Auto-selected first installed distro: {0}" -f $chosen)
    }
  }

  if (-not ($distros -contains $chosen)) {
    _warn ("Requested distro not installed: {0}" -f $chosen)
    if ($SkipDistroInstall) {
      if ($distros.Count -gt 0) {
        _warn ("Falling back to installed distro: {0}" -f $distros[0])
        $chosen = $distros[0]
      } else {
        _fail "SkipDistroInstall is set and no distros are installed."
        exit 4
      }
    } else {
      _say ("Installing distro: {0}" -f $chosen)
      _say "Note: this may open a console to create a Linux username/password."
      $inst = _run ("wsl --install -d {0}" -f $chosen) @("wsl.exe", "--install", "-d", $chosen)
      if ($inst.Output) { _say $inst.Output }

      # Refresh distro list after install attempt.
      $installed2 = _run "wsl -l -q (refresh)" @("wsl.exe", "-l", "-q")
      $distros2 = ($installed2.Output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
      if ($distros2 -contains $chosen) {
        _ok ("Distro installed: {0}" -f $chosen)
        _warn "If the distro prompted for user creation, complete it, then re-run this script to build SITL."
        exit 0
      }

      if ($distros2.Count -gt 0) {
        _warn ("Install did not register '{0}'. Falling back to existing distro: {1}" -f $chosen, $distros2[0])
        _warn "If you want a specific distro, run: wsl -l -o (or wsl --list --online) and then re-run with -Distro <name>."
        $chosen = $distros2[0]
      } else {
        _fail ("No distros installed and install failed for: {0}" -f $chosen)
        _warn "Try manually: wsl --install -d Ubuntu"
        _warn "Or list available: wsl -l -o"
        exit 4
      }
    }
  }

  _ok ("Using distro: {0}" -f $chosen)
  $Distro = $chosen

  # Ensure distro is version 2
  $lv2 = _run "wsl -l -v (check version)" @("wsl.exe", "-l", "-v")
  if ($lv2.ExitCode -eq 0) {
    $clean = ($lv2.Output -replace "`0", "")
    $line = ($clean -split "`r?`n" | Where-Object { $_ -match ("\\b{0}\\b" -f [Regex]::Escape($Distro)) } | Select-Object -First 1)
    if ($line -and ($line -match "\\s2\\s*$")) {
      _ok ("Distro is WSL2: {0}" -f $Distro)
    } else {
      _warn ("Distro is not WSL2 yet (or could not parse). Converting: {0} -> 2" -f $Distro)
      $sv = _run ("wsl --set-version {0} 2" -f $Distro) @("wsl.exe", "--set-version", $Distro, "2")
      _say $sv.Output
    }
  } else {
    _warn "Could not check distro version via wsl -l -v."
    _say $lv2.Output
  }

  # Quick smoke test inside the distro (also catches "distro not initialized yet").
  $smoke = _run ("wsl -d {0} -e bash -lc echo ok" -f $Distro) @("wsl.exe", "-d", $Distro, "-e", "bash", "-lc", "echo distro_ok")
  if ($smoke.ExitCode -ne 0) {
    _fail "Could not execute bash inside the distro."
    _say $smoke.Output
    _say "Action: launch the distro once from Start Menu (Ubuntu) to finish initialization, then re-run this script."
    exit 5
  }
  _ok "WSL distro execution works"

  _step 6 "Clone + build ArduPilot SITL (WSL home: ~/ardupilot)"
  if (-not $SkipSITLBuild) {
    $bash = @'
set -euo pipefail
echo "[INFO] user=$(whoami) home=$HOME"
if ! command -v git >/dev/null 2>&1; then
  echo "[INFO] Installing git..."
  sudo apt-get update -y
  sudo apt-get install -y git
fi

if [ ! -d "$HOME/ardupilot/.git" ]; then
  echo "[INFO] Cloning ArduPilot into $HOME/ardupilot (can take a while)..."
  git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$HOME/ardupilot"
fi

cd "$HOME/ardupilot"
echo "[INFO] Installing ArduPilot prereqs (sudo may prompt)..."
./Tools/environment_install/install-prereqs-ubuntu.sh -y

# Some setups require a new shell for env changes; best-effort load.
if [ -f "$HOME/.profile" ]; then . "$HOME/.profile" || true; fi

echo "[INFO] Configuring + building SITL..."
./waf configure --board sitl
./waf copter -j"$(nproc)"

test -x "$HOME/ardupilot/build/sitl/bin/arducopter"
echo "[OK] SITL binary ready: $HOME/ardupilot/build/sitl/bin/arducopter"
'@
    $build = _run ("wsl -d {0} -e bash -lc <build>" -f $Distro) @("wsl.exe", "-d", $Distro, "-e", "bash", "-lc", $bash)
    if ($build.ExitCode -ne 0) {
      _fail "SITL build failed."
      _say $build.Output
      _say "Common fixes:"
      _say "  1) Re-run: wsl -d <distro> -e bash (and check sudo works)"
      _say "  2) Ensure disk space is available"
      _say "  3) If corporate network blocks GitHub, clone manually inside WSL and re-run with -SkipSITLBuild"
      exit 6
    }

    $sitlCheck = _run "check SITL binary (WSL home)" @("wsl.exe", "-d", $Distro, "-e", "bash", "-lc", 'ls -l "$HOME/ardupilot/build/sitl/bin/arducopter" && "$HOME/ardupilot/build/sitl/bin/arducopter" --version | head -n 1')
    if ($sitlCheck.ExitCode -eq 0 -and $sitlCheck.Output) {
      _say $sitlCheck.Output
    }
  } else {
    _warn "SkipSITLBuild is set; not building SITL."
  }

  _step 7 "Repo preflight (Pipeline A)"
  if (-not $SkipPreflight) {
    $preflight = Join-Path $repoRoot "tools\\preflight_pipeline_a.ps1"
    if (Test-Path $preflight) {
      _say ("Running: {0}" -f $preflight)
      powershell.exe -NoProfile -ExecutionPolicy Bypass -File $preflight
      if ($LASTEXITCODE -eq 0) { _ok "preflight ok" } else { _warn ("preflight exit={0}" -f $LASTEXITCODE) }
    } else {
      _warn ("preflight script not found: {0}" -f $preflight)
    }
  } else {
    _warn "SkipPreflight is set; skipping preflight."
  }

  _say ""
  _ok "Done."
  _say "Next: run a real E2E scenario (no --mock-sitl):"
  _say "  python pipeline\\e2e_flight_matrix.py --scenario porce_off_no_detections"

} catch {
  _fail $_.Exception.Message
  _warn ("Transcript: {0}" -f $transcriptPath)
  exit 1
} finally {
  if ($transcriptStarted) {
    try { Stop-Transcript | Out-Null } catch {}
  }
  if ($PauseOnExit) {
    try { Read-Host "Press ENTER to exit" | Out-Null } catch {}
  }
}
