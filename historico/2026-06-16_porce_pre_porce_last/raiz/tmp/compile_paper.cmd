@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\MiKTeX\miktex\bin\x64;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test\paper\Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
pdflatex -interaction=nonstopmode -halt-on-error main.tex > "D:\Deep-AeroTwin-UE57-Test\tmp\latex_pass1.txt" 2>&1
echo pass1=%errorlevel% > "D:\Deep-AeroTwin-UE57-Test\tmp\latex_exit.txt"
pdflatex -interaction=nonstopmode -halt-on-error main.tex > "D:\Deep-AeroTwin-UE57-Test\tmp\latex_pass2.txt" 2>&1
echo pass2=%errorlevel% >> "D:\Deep-AeroTwin-UE57-Test\tmp\latex_exit.txt"
