@echo off
REM AUTO-SYNC: vigilante de papers. Al guardar cambios en cualquier fuente
REM canonica se sincroniza solo con GitHub + Overleaf (debounce 15 s).
REM Dejar esta ventana abierta (se puede minimizar). Cerrar = parar el auto-sync.
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\Deep-AeroTwin-UE57-Test\papers\overleaf_sync\auto_sync_watch.ps1"
