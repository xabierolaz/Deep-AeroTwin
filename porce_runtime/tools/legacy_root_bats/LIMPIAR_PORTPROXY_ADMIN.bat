@echo off
setlocal EnableExtensions

set "LISTEN_ADDRESS=127.0.0.1"
set "PORTS=5760 5762"

title Deep-AeroTwin limpiar portproxy

if /I "%~1"=="--elevated" goto :elevated

net session >nul 2>&1
if errorlevel 1 (
  echo [INFO] Esta limpieza necesita permisos de Administrador.
  echo [INFO] Se abrira una ventana UAC para ejecutar este mismo .bat elevado.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs"
  if errorlevel 1 (
    echo [ERROR] No se pudo solicitar elevacion.
    pause
    exit /b 1
  )
  exit /b 0
)

:elevated
echo [Deep-AeroTwin] Limpiando reglas persistentes netsh portproxy
echo.
echo [ANTES]
netsh interface portproxy show all
echo.

for %%P in (%PORTS%) do (
  echo [DELETE] %LISTEN_ADDRESS%:%%P
  netsh interface portproxy delete v4tov4 listenaddress=%LISTEN_ADDRESS% listenport=%%P
)

echo.
echo [DESPUES]
netsh interface portproxy show all
echo.
echo [OK] Limpieza terminada.
pause
exit /b 0
