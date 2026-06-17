@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD;.VBS;.JS;.MSC"
set "PATH=C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;%LOCALAPPDATA%\Microsoft\WindowsApps;%PATH%"
set "PORCE_CAPTURE_WINDOW_TITLE=AirTraffic (64-bit"
set "PORCE_CAPTURE_WINDOW_EXACT=0"
set "PORCE_AUDIT_VISION_FRAME_EVERY_N=2"
call "D:\Deep-AeroTwin-UE57-Test\launch.bat" > "D:\Deep-AeroTwin-UE57-Test\tmp\d1_launch_log.txt" 2>&1
exit /b %errorlevel%
