@echo off

set "CFG_FILE=%~1"
set "FORCE_SET=%~2"
if not defined CFG_FILE set "CFG_FILE=%~dp0..\pipeline\porce_defaults.env"
if not defined PROJECT_ROOT set "PROJECT_ROOT=%~dp0.."
if not defined FORCE_SET set "FORCE_SET=%PORCE_DEFAULTS_FORCE%"
if /I "%FORCE_SET%"=="true" set "FORCE_SET=1"
if /I "%FORCE_SET%"=="yes" set "FORCE_SET=1"
if /I "%FORCE_SET%"=="on" set "FORCE_SET=1"
if not exist "%CFG_FILE%" (
  echo [ERROR] PORCE defaults file not found: %CFG_FILE%
  exit /b 2
)

for /F "usebackq eol=# delims=" %%R in ("%CFG_FILE%") do (
  for /F "tokens=1,* delims==" %%K in ("%%R") do (
    if not "%%K"=="" (
      if "%FORCE_SET%"=="1" (
        REM Force mode: overwrite existing env values for deterministic runs.
        REM Empty values are intentional: they clear stale process env such as tokens.
        call set "%%K=%%L"
      ) else (
        if not "%%L"=="" if not defined %%K (
          REM Allow environment-variable placeholders like %%VAR%% in cfg values.
          call set "%%K=%%L"
        )
      )
    )
  )
)

exit /b 0
