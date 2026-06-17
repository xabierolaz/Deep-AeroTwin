@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test"
git add paper pipeline/vision_system.py > "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit3_out.txt" 2>&1
git commit -m "Fig4 con frame pristino: fix anotacion debug de vision contaminaba frames de audit (copia pre-anotacion); caso definitivo run 233504 (WP6, 16 obs, detour 3.4m, clearance 34.3m)" >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit3_out.txt" 2>&1
git log --oneline -1 >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit3_out.txt" 2>&1
