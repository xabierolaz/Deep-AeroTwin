@echo off
set "PATHEXT=.COM;.EXE;.BAT;.CMD"
set "PATH=C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows;%PATH%"
cd /d "D:\Deep-AeroTwin-UE57-Test"
git add -u > "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit_out.txt" 2>&1
git add docs paper WORKFLOWS.md launch_digital_twin.bat .mcp.json ^
  pipeline/real_twin_defaults.env ^
  tools/audit_zero_trust_e2e.ps1 tools/e2e_campaign.py tools/launch_workflow.bat ^
  "Unreal/Content/Ejea_AuditD1.umap" "Unreal/Content/Peloton" ^
  "Unreal/Source/AirTraffic/Private/PelotonSplineActor.cpp" "Unreal/Source/AirTraffic/Public" ^
  "Unreal/Plugins/McpAutomationBridge" >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit_out.txt" 2>&1
git commit -m "Evidencia paper + auditoria 2026-06-12: planner_obs_ids (D3), campana E2E estadistica (D2), captura PrintWindow robusta, caso peloton UE5.7 real-SITL, figuras y main.tex regenerados, mapa Ejea_AuditD1, latencias D5" >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit_out.txt" 2>&1
git log --oneline -2 >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit_out.txt" 2>&1
echo exit=%errorlevel% >> "D:\Deep-AeroTwin-UE57-Test\tmp\git_commit_out.txt"
