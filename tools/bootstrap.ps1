param(
  [string]$RepoRoot = "",
  [string]$PythonExe = "",
  [switch]$RecreateVenv,
  [switch]$SkipSubmodules,
  [switch]$SkipPipInstall,
  [switch]$BuildSITL
)

$ErrorActionPreference = "Stop"

function Fail([string]$message, [int]$code = 1) {
  Write-Host "[bootstrap] ERROR: $message" -ForegroundColor Red
  exit $code
}

function Step([string]$message) {
  Write-Host "[bootstrap] $message"
}

function Warn([string]$message) {
  Write-Host "[bootstrap] WARN: $message" -ForegroundColor Yellow
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$lockFile = Join-Path $RepoRoot "pipeline\requirements.lock.txt"
$venvDir = Join-Path $RepoRoot "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$yoloWeight = Join-Path $RepoRoot "yolo\weights\yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"
$yoloConfigDir = Join-Path $RepoRoot "pipeline\logs\ultralytics"
$sitlBinary = Join-Path $RepoRoot "ardupilot\build\sitl\bin\arducopter"
$buildSITLScript = Join-Path $RepoRoot "tools\build_sitl_wsl.ps1"

if (-not (Test-Path $lockFile)) {
  Fail "Missing lockfile: $lockFile"
}
if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
  Fail "Repo root does not look like a git checkout: $RepoRoot"
}

if (-not $SkipSubmodules) {
  Step "Syncing and initializing git submodules..."
  $syncOk = $true
  try {
    & git -C $RepoRoot submodule sync --recursive
    if ($LASTEXITCODE -ne 0) { $syncOk = $false }
  } catch {
    $syncOk = $false
  }
  if (-not $syncOk) {
    Warn "git submodule sync failed in this environment. Continuing with best effort."
  }

  $updateOk = $true
  try {
    & git -C $RepoRoot submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { $updateOk = $false }
  } catch {
    $updateOk = $false
  }
  if (-not $updateOk) {
    $submoduleMarker = Join-Path $RepoRoot "ardupilot\.git"
    if (Test-Path $submoduleMarker) {
      Warn "git submodule update failed, but ardupilot submodule worktree already exists."
    } else {
      Fail "git submodule update failed and ardupilot is not initialized."
    }
  }
} else {
  Step "Skipping submodule setup by request."
}

if ($RecreateVenv -and (Test-Path $venvDir)) {
  Step "Removing existing virtual environment..."
  Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
  Step "Creating Python virtual environment..."
  if ($PythonExe) {
    & $PythonExe -m venv $venvDir
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 -m venv $venvDir
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venvDir
  } else {
    Fail "No Python interpreter found (expected py or python)."
  }
  if ($LASTEXITCODE -ne 0) {
    Fail "Virtual environment creation failed."
  }
} else {
  Step "Using existing virtual environment: $venvDir"
}

if (-not (Test-Path $venvPython)) {
  Fail "Virtual environment python not found: $venvPython"
}

if (-not $SkipPipInstall) {
  Step "Installing locked Python dependencies..."
  & $venvPython -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) {
    Fail "pip upgrade failed."
  }
  & $venvPython -m pip install -r $lockFile
  if ($LASTEXITCODE -ne 0) {
    Fail "pip install -r requirements.lock.txt failed."
  }
} else {
  Step "Skipping pip install by request."
}

Step "Verifying Python imports..."
New-Item -ItemType Directory -Force -Path $yoloConfigDir | Out-Null
$env:YOLO_CONFIG_DIR = $yoloConfigDir
& $venvPython -c "import flask,requests,pymavlink,ultralytics,cv2,mss,trimesh,pyrender,numpy,matplotlib;print('imports_ok')" 2>$null
if ($LASTEXITCODE -ne 0) {
  Fail "Dependency import check failed."
}

if (-not (Test-Path $yoloWeight)) {
  Fail "Missing canonical YOLO weight: $yoloWeight"
}
Step "YOLO weight present."

if ($BuildSITL) {
  if (-not (Test-Path $buildSITLScript)) {
    Fail "Missing SITL builder script: $buildSITLScript"
  }
  Step "Building SITL in WSL..."
  & $buildSITLScript -RepoRoot $RepoRoot
  if ($LASTEXITCODE -ne 0) {
    Fail "SITL build failed."
  }
} elseif (-not (Test-Path $sitlBinary)) {
  Write-Host "[bootstrap] WARN: SITL binary not found at $sitlBinary" -ForegroundColor Yellow
  Write-Host "[bootstrap] WARN: Run tools\build_sitl_wsl.ps1 before LANZAR_TODO_PAPER.bat or tools\launch_workflow.bat SIMULATION" -ForegroundColor Yellow
} else {
  Step "SITL binary already present."
}

Step "Bootstrap completed."
Write-Host "[bootstrap] Next steps:"
Write-Host "  1) powershell -NoProfile -ExecutionPolicy Bypass -File tools\preflight_zero_trust.ps1"
Write-Host "  2) LANZAR_TODO_PAPER.bat"
