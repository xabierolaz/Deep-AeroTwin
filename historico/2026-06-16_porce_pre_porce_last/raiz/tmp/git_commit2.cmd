@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test"
git add paper Unreal/Content/Ejea_AuditD1.umap > "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit2_out.txt" 2>&1
git commit -m "Paper: robustez full-route (run 224316, peloton 16x23km/h) + latencias D5 + PDF final" >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit2_out.txt" 2>&1
git log --oneline -2 >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit2_out.txt" 2>&1
