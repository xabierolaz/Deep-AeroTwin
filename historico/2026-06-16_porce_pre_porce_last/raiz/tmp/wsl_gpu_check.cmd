@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Windows\System32;C:\Windows;%PATH%"
set "LOG=D:\Deep-AeroTwin-UE57-Test\tmp\wsl_gpu.log"
echo === wsl distros === > "%LOG%"
wsl -l -v >> "%LOG%" 2>&1
echo === nvidia-smi in wsl === >> "%LOG%"
wsl -e sh -lc "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1 | head -3" >> "%LOG%" 2>&1
echo === python in wsl === >> "%LOG%"
wsl -e sh -lc "python3 --version; which python3; ls /usr/local/cuda* 2>/dev/null; nvcc --version 2>/dev/null | tail -2" >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
