@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Windows\System32;C:\Windows;%PATH%"
set "LOG=D:\Deep-AeroTwin-UE57-Test\tmp\neural_setup.log"
echo === create venv === > "%LOG%"
"C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe" -m venv "D:\Deep-AeroTwin-UE57-Test\venv_neural" >> "%LOG%" 2>&1
echo === upgrade pip === >> "%LOG%"
"D:\Deep-AeroTwin-UE57-Test\venv_neural\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
echo === install torch cu128 === >> "%LOG%"
"D:\Deep-AeroTwin-UE57-Test\venv_neural\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 >> "%LOG%" 2>&1
echo EXIT=%errorlevel% >> "%LOG%"
echo === probe === >> "%LOG%"
"D:\Deep-AeroTwin-UE57-Test\venv_neural\Scripts\python.exe" "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_probe.py" > "D:\Deep-AeroTwin-UE57-Test\tmp\gpu_probe_neural.txt" 2>&1
echo DONE >> "%LOG%"
