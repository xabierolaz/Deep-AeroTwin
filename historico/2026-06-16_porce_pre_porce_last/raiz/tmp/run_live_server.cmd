@echo off
REM Lanza el servidor de restyle en vivo dentro de WSL (~/sdv2_venv, GPU 5090).
REM Mantiene WSL vivo porque el cmd queda en primer plano (no usar nohup&).
C:\Windows\System32\wsl.exe -e bash -lc "source ~/sdv2_venv/bin/activate && cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2 && pip install -q fastapi uvicorn 2>/dev/null; python /mnt/d/Deep-AeroTwin-UE57-Test/neural/live_server.py --config_path configs/wan_causal_dmd_v2v.yaml --checkpoint_folder ckpts/wan_causal_dmd_v2v --prompt_file /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_prompt.txt --height 480 --width 480 --step 2 --noise_scale 0.8 --host 0.0.0.0 --port 9500"
