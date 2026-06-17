@echo off
C:\Windows\System32\nvidia-smi.exe --query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader > "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_busy.txt" 2>&1
C:\Windows\System32\wsl.exe -e bash -lc "ps aux|grep -E 'inference|python -m streamv2v'|grep -v grep|head -3" >> "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_busy.txt" 2>&1
