@echo off
REM Sincroniza los 3 papers: regenera deploys, compila y sube a GitHub + Overleaf
"C:\Program Files\Git\bin\bash.exe" "D:/Deep-AeroTwin-UE57-Test/papers/overleaf_sync/sync.sh" all
pause
