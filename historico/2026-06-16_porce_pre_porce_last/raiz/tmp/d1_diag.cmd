@echo off
set "OUT=D:\Deep-AeroTwin-UE57-Test\tmp\d1_diag_out.txt"
echo PATH_BEFORE=%PATH%> "%OUT%"
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;%LOCALAPPDATA%\Microsoft\WindowsApps;%PATH%"
echo PATH_AFTER=%PATH%>> "%OUT%"
where powershell >> "%OUT%" 2>&1
echo where_ps=%errorlevel%>> "%OUT%"
powershell -NoProfile -Command "Write-Output PS_OK" >> "%OUT%" 2>&1
echo ps_exit=%errorlevel%>> "%OUT%"
wsl -e sh -lc "echo WSL_OK" >> "%OUT%" 2>&1
echo wsl_exit=%errorlevel%>> "%OUT%"
