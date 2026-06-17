@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Windows\System32;C:\Windows;%PATH%"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader > "D:\Deep-AeroTwin-UE57-Test\tmp\smi.txt" 2>&1
"D:\Deep-AeroTwin-UE57-Test\venv\Scripts\python.exe" "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_probe.py" > "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_probe_stdout.txt" 2>&1
