@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test\paper\Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion\scripts"
"D:\Deep-AeroTwin-UE57-Test\venv\Scripts\python.exe" -u generate_paper_assets.py > "D:\Deep-AeroTwin-UE57-Test\tmp\genassets_out.txt" 2>&1
echo %errorlevel% > "D:\Deep-AeroTwin-UE57-Test\tmp\genassets_exit.txt"
