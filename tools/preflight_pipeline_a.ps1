param(
  [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"

function _say([string]$msg) {
  if (-not $Quiet) {
    Write-Host $msg
  }
}

function _ok([string]$msg) { _say "[OK]  $msg" }
function _warn([string]$msg) { _say "[WARN] $msg" }
function _fail([string]$msg) { _say "[FAIL] $msg" }

_say "== Deep-AeroTwin Preflight: Pipeline A (SIMULATION) =="

# -----------------------------------------------------------------------------
# Python
# -----------------------------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  _fail "python not found on PATH."
  exit 2
}

try {
  $pyv = (python --version 2>&1) -join ""
  _ok "python: $pyv"
} catch {
  _warn "python --version failed: $($_.Exception.Message)"
}

# Check imports (best-effort).
$imports = @("requests","flask","pymavlink","ultralytics","cv2","mss","numpy")
foreach ($m in $imports) {
  python -c "import $m" > $null 2>&1
  if ($LASTEXITCODE -eq 0) { _ok "import $m" } else { _warn "missing/failed import: $m (pip install -r pipeline/requirements.txt)" }
}

# -----------------------------------------------------------------------------
# WSL
# -----------------------------------------------------------------------------
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
  _fail "wsl.exe not found (Pipeline A requires WSL2 for SITL)."
  exit 3
}

& wsl.exe -e bash -lc "echo wsl_ok" > $null 2>&1
if ($LASTEXITCODE -eq 0) {
  _ok "WSL execution works (wsl -e bash -lc ...)"
} else {
  _fail "WSL execution failed (try 'wsl -l -v' in a normal terminal; this environment returned E_ACCESSDENIED)."
  _say "       workaround: run E2E with mock SITL: python pipeline\\e2e_flight_matrix.py --scenario porce_on_with_detections --mock-sitl"
}

# -----------------------------------------------------------------------------
# SITL binary (repo build path)
# -----------------------------------------------------------------------------
if (Test-Path ".\\ardupilot\\build\\sitl\\bin\\arducopter") {
  _ok "SITL binary present: ardupilot\\build\\sitl\\bin\\arducopter"
} else {
  # Fallback supported by pipeline/run_sitl.sh: WSL home clone at ~/ardupilot.
  & wsl.exe -e bash -lc 'test -x $HOME/ardupilot/build/sitl/bin/arducopter' > $null 2>&1
  if ($LASTEXITCODE -eq 0) {
    _ok "SITL binary present in WSL home: ~/ardupilot/build/sitl/bin/arducopter (fallback)"
  } else {
    _warn "SITL binary missing at ardupilot\\build\\sitl\\bin\\arducopter (repo) and ~/ardupilot/build/sitl/bin/arducopter (WSL home)"
    _say "       run in WSL (repo submodule): cd ardupilot; ./waf configure --board sitl && ./waf copter"
    _say "       or run in WSL (home clone): cd ~/ardupilot; ./waf configure --board sitl && ./waf copter"
    _say "       or set WSL env var: ARDUPILOT_SITL_BIN=/path/to/arducopter"
  }
}

# -----------------------------------------------------------------------------
# Vision weights
# -----------------------------------------------------------------------------
if (Test-Path ".\\pipeline\\weights\\yolo_3d_dome_v1_best.pt") {
  _ok "YOLO weights present: pipeline\\weights\\yolo_3d_dome_v1_best.pt"
} else {
  _warn "YOLO weights missing: pipeline\\weights\\yolo_3d_dome_v1_best.pt"
}

_say "== Preflight complete =="
exit 0
