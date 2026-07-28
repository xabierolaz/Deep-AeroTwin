function Get-PorceUnrealEngineCandidates {
  param(
    [string]$EngineRoot = "",
    [string]$EngineVersion = "5.7"
  )

  $candidates = New-Object System.Collections.Generic.List[string]
  foreach ($value in @(
      $EngineRoot,
      [Environment]::GetEnvironmentVariable("PORCE_UNREAL_ENGINE_ROOT", "Process"),
      [Environment]::GetEnvironmentVariable("UE_ENGINE_ROOT", "Process"),
      [Environment]::GetEnvironmentVariable("UNREAL_ENGINE_ROOT", "Process")
    )) {
    if (-not [string]::IsNullOrWhiteSpace($value)) {
      $candidates.Add($value.Trim()) | Out-Null
    }
  }

  $suffix = "Epic Games\UE_$EngineVersion"
  foreach ($base in @(
      "D:\",
      "C:\",
      ${env:ProgramFiles},
      ${env:ProgramFiles(x86)}
    )) {
    if (-not [string]::IsNullOrWhiteSpace($base)) {
      $candidates.Add((Join-Path $base $suffix)) | Out-Null
    }
  }

  return @($candidates | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
}

function Resolve-PorceUnrealEngineRoot {
  param(
    [string]$EngineRoot = "",
    [string]$EngineVersion = "5.7"
  )

  $checked = New-Object System.Collections.Generic.List[string]
  foreach ($candidate in Get-PorceUnrealEngineCandidates -EngineRoot $EngineRoot -EngineVersion $EngineVersion) {
    $expanded = [Environment]::ExpandEnvironmentVariables($candidate)
    $checked.Add($expanded) | Out-Null
    $cmdPath = Join-Path $expanded "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
    $editorPath = Join-Path $expanded "Engine\Binaries\Win64\UnrealEditor.exe"
    $buildPath = Join-Path $expanded "Engine\Build\BatchFiles\Build.bat"
    if ((Test-Path $cmdPath) -and (Test-Path $editorPath) -and (Test-Path $buildPath)) {
      return (Resolve-Path $expanded).Path
    }
  }

  throw "Could not resolve Unreal Engine $EngineVersion root. Checked: $($checked -join '; '). Set PORCE_UNREAL_ENGINE_ROOT or UE_ENGINE_ROOT."
}

function Get-PorceUnrealEnginePaths {
  param(
    [string]$EngineRoot = "",
    [string]$EngineVersion = "5.7"
  )

  $resolvedRoot = Resolve-PorceUnrealEngineRoot -EngineRoot $EngineRoot -EngineVersion $EngineVersion
  return [pscustomobject]@{
    Root = $resolvedRoot
    UnrealEditor = Join-Path $resolvedRoot "Engine\Binaries\Win64\UnrealEditor.exe"
    UnrealEditorCmd = Join-Path $resolvedRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
    BuildBat = Join-Path $resolvedRoot "Engine\Build\BatchFiles\Build.bat"
  }
}
