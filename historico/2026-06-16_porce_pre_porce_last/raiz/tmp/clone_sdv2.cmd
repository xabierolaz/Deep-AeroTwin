@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
set "LOG=D:\Deep-AeroTwin-UE57-Test\tmp\sdv2_clone.log"
cd /d "D:\Deep-AeroTwin-UE57-Test"
if not exist neural mkdir neural
cd neural
git clone --depth 1 https://github.com/chenfengxu714/StreamDiffusionV2.git > "%LOG%" 2>&1
echo CLONE_EXIT=%errorlevel% >> "%LOG%"
dir StreamDiffusionV2 >> "%LOG%" 2>&1
echo DONE >> "%LOG%"
