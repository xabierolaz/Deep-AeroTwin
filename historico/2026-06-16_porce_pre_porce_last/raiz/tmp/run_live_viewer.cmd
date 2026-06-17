@echo off
REM Cliente visor en Windows (venv del proyecto tiene cv2). Ventana de Unreal abierta.
cd /d D:\Deep-AeroTwin-UE57-Test
venv\Scripts\python.exe neural\live_viewer.py --title "airtraffic (64-bit" --server http://127.0.0.1:9500
