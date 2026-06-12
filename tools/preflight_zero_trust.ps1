param(
  [string]$RepoRoot = "",
  [switch]$Strict
)

$ErrorActionPreference = "Stop"

function NoteOk([string]$message) {
  Write-Host "[preflight] OK   $message" -ForegroundColor Green
}

function NoteWarn([string]$message) {
  Write-Host "[preflight] WARN $message" -ForegroundColor Yellow
  $script:warnings.Add($message) | Out-Null
}

function NoteFail([string]$message) {
  Write-Host "[preflight] FAIL $message" -ForegroundColor Red
  $script:failures.Add($message) | Out-Null
}

function Read-DotEnv([string]$path) {
  $result = @{}
  foreach ($line in Get-Content $path) {
    $trimmed = $line.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
    if ($trimmed.StartsWith("#")) { continue }
    $idx = $trimmed.IndexOf("=")
    if ($idx -lt 1) { continue }
    $key = $trimmed.Substring(0, $idx).Trim()
    $val = $trimmed.Substring($idx + 1).Trim()
    $result[$key] = $val
  }
  return $result
}

function Resolve-RepoVarPath([string]$value, [string]$repoRoot) {
  $expanded = $value.Replace("%PROJECT_ROOT%", $repoRoot)
  return [Environment]::ExpandEnvironmentVariables($expanded)
}

function Find-EnginePluginDir([string]$engineRoot, [string]$pluginPrefix) {
  if ([string]::IsNullOrWhiteSpace($engineRoot)) { return $null }
  $pluginsRoot = Join-Path $engineRoot "Engine\Plugins"
  if (-not (Test-Path $pluginsRoot)) { return $null }
  $matches = Get-ChildItem $pluginsRoot -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "$pluginPrefix*" }
  if ($matches) {
    return $matches | Select-Object -First 1 -ExpandProperty FullName
  }
  return $null
}

$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$uprojectPath = Join-Path $RepoRoot "Unreal\AirTraffic.uproject"
$defaultsPath = Join-Path $RepoRoot "pipeline\porce_defaults.env"
$runSITLPath = Join-Path $RepoRoot "pipeline\run_sitl.sh"
$launchPath = Join-Path $RepoRoot "launch.bat"
$engineIniPath = Join-Path $RepoRoot "Unreal\Config\DefaultEngine.ini"
$lockPath = Join-Path $RepoRoot "pipeline\requirements.lock.txt"
$venvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
$yoloConfigDir = Join-Path $RepoRoot "pipeline\logs\ultralytics"
$sitlBinary = Join-Path $RepoRoot "ardupilot\build\sitl\bin\arducopter"
$engineRoot = "D:\Epic Games\UE_5.7"

Write-Host "[preflight] Repo: $RepoRoot"

foreach ($required in @($uprojectPath, $defaultsPath, $runSITLPath, $launchPath, $engineIniPath, $lockPath)) {
  if (Test-Path $required) {
    NoteOk "Found $required"
  } else {
    NoteFail "Missing required file: $required"
  }
}

$submoduleGitlink = $null
try {
  $submoduleGitlink = (& git -C $RepoRoot ls-files --stage ardupilot 2>$null | Select-Object -First 1)
} catch {
  $submoduleGitlink = $null
}
if ([string]::IsNullOrWhiteSpace($submoduleGitlink)) {
  NoteFail "Could not read ardupilot gitlink (git ls-files --stage)."
} elseif ($submoduleGitlink -match '^160000\s+[0-9a-f]{40}\s+\d+\s+ardupilot$') {
  NoteOk "ardupilot gitlink present in index."
} else {
  NoteFail "Unexpected ardupilot gitlink format: $submoduleGitlink"
}

$submoduleMarker = Join-Path $RepoRoot "ardupilot\.git"
if (Test-Path $submoduleMarker) {
  NoteOk "ardupilot submodule worktree initialized."
} else {
  NoteFail "ardupilot submodule worktree missing (run git submodule update --init --recursive)."
}

if (Test-Path $sitlBinary) {
  NoteOk "SITL binary present: $sitlBinary"
} else {
  NoteFail "Missing SITL binary: $sitlBinary (run tools\build_sitl_wsl.ps1)"
}

& wsl.exe -e sh -lc "echo WSL_OK" > $null 2>&1
if ($LASTEXITCODE -eq 0) {
  NoteOk "WSL health check passed."
} else {
  NoteFail "WSL health check failed."
}

if (Test-Path $venvPython) {
  NoteOk "venv python found."
  New-Item -ItemType Directory -Force -Path $yoloConfigDir | Out-Null
  $env:YOLO_CONFIG_DIR = $yoloConfigDir
  & $venvPython -c "import flask,requests,pymavlink,ultralytics,cv2,mss,trimesh,pyrender,numpy,matplotlib;print('imports_ok')" > $null 2>$null
  if ($LASTEXITCODE -eq 0) {
    NoteOk "Python dependency import check passed."
  } else {
    NoteFail "Python dependency import check failed (run tools\bootstrap.ps1)."
  }
} else {
  NoteFail "venv not found at $venvPython (run tools\bootstrap.ps1)."
}

if (Test-Path $uprojectPath) {
  try {
    $uproject = Get-Content $uprojectPath -Raw | ConvertFrom-Json
    if (("$($uproject.EngineAssociation)") -eq "5.7") {
      NoteOk "Unreal EngineAssociation is 5.7."
    } else {
      NoteFail "Unreal EngineAssociation is '$($uproject.EngineAssociation)' (expected 5.7)."
    }

    $plugins = @{}
    foreach ($p in @($uproject.Plugins)) {
      if ($p -and $p.Name) {
        $plugins["$($p.Name)"] = [bool]$p.Enabled
      }
    }

    foreach ($requiredPlugin in @("PorceTelemetry", "CesiumForUnreal", "VaRest")) {
      if ($plugins.ContainsKey($requiredPlugin) -and $plugins[$requiredPlugin]) {
        NoteOk "Plugin enabled in .uproject: $requiredPlugin"
      } else {
        NoteFail "Plugin missing/disabled in .uproject: $requiredPlugin"
      }
    }
  } catch {
    NoteFail "Could not parse Unreal .uproject JSON."
  }
}

$cesiumProjectPlugin = Join-Path $RepoRoot "Unreal\Plugins\CesiumForUnreal"
$vaRestProjectPlugin = Join-Path $RepoRoot "Unreal\Plugins\VaRest"
$cesiumEnginePlugin = Find-EnginePluginDir -engineRoot $engineRoot -pluginPrefix "Cesium"
$vaRestEnginePlugin = Find-EnginePluginDir -engineRoot $engineRoot -pluginPrefix "VaRest"

if (Test-Path $cesiumProjectPlugin) {
  NoteOk "CesiumForUnreal vendored in project plugins."
} elseif ($cesiumEnginePlugin) {
  NoteOk "CesiumForUnreal found in UE 5.7 engine plugins: $cesiumEnginePlugin"
} else {
  NoteWarn "CesiumForUnreal is not vendored and was not found in UE 5.7 engine plugins."
}
if (Test-Path $vaRestProjectPlugin) {
  NoteOk "VaRest vendored in project plugins."
} elseif ($vaRestEnginePlugin) {
  NoteOk "VaRest found in UE 5.7 engine plugins: $vaRestEnginePlugin"
} else {
  NoteWarn "VaRest is not vendored and was not found in UE 5.7 engine plugins."
}

if (Test-Path $defaultsPath) {
  $cfg = Read-DotEnv $defaultsPath

  if ($cfg["PORCE_BRAIN_APP_BIND_HOST"] -eq "127.0.0.1") {
    NoteOk "Brain bind host is loopback."
  } else {
    NoteFail "PORCE_BRAIN_APP_BIND_HOST must be 127.0.0.1."
  }

  if ($cfg["PORCE_LOG_SERVER_LISTEN_HOST"] -eq "127.0.0.1") {
    NoteOk "Log server listen host is loopback."
  } else {
    NoteFail "PORCE_LOG_SERVER_LISTEN_HOST must be 127.0.0.1."
  }

  if ($cfg["PORCE_OBSTACLE_TOKEN_REQUIRED"] -eq "1") {
    NoteOk "Obstacle token is required."
  } else {
    NoteFail "PORCE_OBSTACLE_TOKEN_REQUIRED must be 1."
  }

  if ($cfg["PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED"] -eq "1") {
    NoteOk "Unreal telemetry token is required."
  } else {
    NoteFail "PORCE_UNREAL_TELEMETRY_TOKEN_REQUIRED must be 1."
  }

  if ($cfg["PORCE_OBS_SOURCE_FILTER_ENABLE"] -eq "1") {
    NoteOk "Obstacle source filter is enabled."
  } else {
    NoteFail "PORCE_OBS_SOURCE_FILTER_ENABLE must be 1."
  }

  $allowedSources = "$($cfg["PORCE_OBS_ALLOWED_SOURCES"])"
  if ($allowedSources -match "(^|,)vision($|,)") {
    NoteOk "Allowed obstacle sources include vision."
  } else {
    NoteFail "PORCE_OBS_ALLOWED_SOURCES must include vision."
  }

  $modelPathRaw = "$($cfg["PORCE_YOLO_MODEL"])"
  if ([string]::IsNullOrWhiteSpace($modelPathRaw)) {
    NoteFail "PORCE_YOLO_MODEL is empty."
  } else {
    $modelPath = Resolve-RepoVarPath -value $modelPathRaw -repoRoot $RepoRoot
    if (Test-Path $modelPath) {
      NoteOk "YOLO model file found: $modelPath"
    } else {
      NoteFail "YOLO model file missing: $modelPath"
    }
  }
}

if (Test-Path $runSITLPath) {
  $runSITLRaw = Get-Content $runSITLPath -Raw
  if ($runSITLRaw -match 'SITL_SERIAL0:-tcp:127\.0\.0\.1:5760') {
    NoteOk "SITL serial0 default is loopback."
  } else {
    NoteFail "run_sitl.sh should default SITL_SERIAL0 to tcp:127.0.0.1:5760."
  }
}

if (Test-Path $launchPath) {
  $launchRaw = Get-Content $launchPath -Raw
  if ($launchRaw -match 'PORCE_OBSTACLE_TOKEN_PERSIST=0') {
    NoteOk "launch.bat defaults token persistence to disabled."
  } else {
    NoteFail "launch.bat must default PORCE_OBSTACLE_TOKEN_PERSIST=0."
  }
}

if (Test-Path $engineIniPath) {
  $engineRaw = Get-Content $engineIniPath -Raw
  if ($engineRaw -match 'bAllowNetworkConnection=True') {
    NoteWarn "AndroidFileServer allows network connections. Consider disabling for strict zero-trust."
  }
  if ($engineRaw -match 'SecurityToken=([A-Fa-f0-9]+)') {
    NoteWarn "DefaultEngine.ini contains a static AndroidFileServer SecurityToken."
  }
}

Write-Host ""
Write-Host "[preflight] Summary: failures=$($failures.Count) warnings=$($warnings.Count)"

if ($Strict -and $warnings.Count -gt 0) {
  foreach ($w in $warnings) {
    $failures.Add("STRICT: $w") | Out-Null
  }
}

if ($failures.Count -gt 0) {
  Write-Host "[preflight] FAILED" -ForegroundColor Red
  exit 1
}

Write-Host "[preflight] PASSED" -ForegroundColor Green
exit 0
