@echo off
C:\Windows\System32\wsl.exe -e bash -lc "bash /mnt/d/Deep-AeroTwin-UE57-Test/neural/wsl_setup_sdv2.sh"
echo WSL_SETUP_RETURNED=%errorlevel% >> "D:\Deep-AeroTwin-UE57-Test\tmp\wsl_sdv2_setup.log"
