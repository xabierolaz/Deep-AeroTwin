@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test"
git add docs > "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit4_out.txt" 2>&1
git commit -m "docs: demo D4 twin spawn/update/despawn verificada (API + LogPorceTelemetry)" >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit4_out.txt" 2>&1
git log --oneline -4 >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit4_out.txt" 2>&1
