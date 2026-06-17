#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/compare_final.log
exec > "$LOG" 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2, numpy as np
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
VACE="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"
FVSR="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/FlashVSR_v1.1_Tiny_ejea_lq_seed0.mp4"
def grab(p,idx,S=512):
    c=cv2.VideoCapture(p); n=int(c.get(7)); idx=min(idx,n-1); c.set(cv2.CAP_PROP_POS_FRAMES,idx)
    ok,f=c.read(); c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=512
# FlashVSR procesó los primeros ~45 frames; alineo por frame absoluto temprano
for fr_o, tag in [(15,"a"),(35,"b")]:
    o=grab(ORIG,fr_o,S)
    v=grab(VACE,int(fr_o/191*81),S)     # VACE muestreó 81 de 191
    f=grab(FVSR,fr_o,S)                  # FlashVSR primeros frames 1:1
    sep=np.full((S,6,3),255,np.uint8)
    row=np.hstack([o,sep,v,sep,f])
    hdr=np.full((30,row.shape[1],3),20,np.uint8)
    for x,t in [(8,"ORIGINAL Cesium"),(S+14,"VACE (reinventa)"),(2*S+20,"FlashVSR (fiel+detalle)")]:
        cv2.putText(hdr,t,(x,20),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),1)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/FINAL_compare_{tag}.png",np.vstack([hdr,row]))
    print("wrote FINAL_compare_%s"%tag)
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/FINAL_compare_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo COMPARE_DONE
