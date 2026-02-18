@echo off

set "CFG_FILE=%~1"
if not defined CFG_FILE set "CFG_FILE=%~dp0..\pipeline\porce_defaults.env"
if not defined PROJECT_ROOT set "PROJECT_ROOT=%~dp0.."
if not exist "%CFG_FILE%" (
  echo [ERROR] PORCE defaults file not found: %CFG_FILE%
  exit /b 2
)

for /F "usebackq eol=# delims=" %%R in ("%CFG_FILE%") do (
  for /F "tokens=1,* delims==" %%K in ("%%R") do (
    if not "%%K"=="" if not "%%L"=="" (
      if not defined %%K (
        REM Allow environment-variable placeholders like %%VAR%% in cfg values.
        call set "%%K=%%L"
      )
    )
  )
)

exit /b 0
