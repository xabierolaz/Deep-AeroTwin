@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test"
git status --porcelain > "D:\Deep-AeroTwin-UE57-Test\tmp\git_status_out.txt" 2>&1
echo done >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_status_out.txt"
