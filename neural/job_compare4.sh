#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/compare4.log
exec > "$LOG" 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
VACE="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"
FVSR="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/FlashVSR_v1.1_Tiny_ejea_lq_seed0.mp4"
REF="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out/00000001.mp4"
def grab(p,idx,S=448):
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,max(0,n-1));c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=448
for fr,tag in [(15,"a"),(35,"b")]:
    cols=[("ORIGINAL Cesium",grab(ORIG,fr)),
          ("VACE canny",grab(VACE,int(fr/191*81))),
          ("FlashVSR",grab(FVSR,fr)),
          ("Fun-Control+REF",grab(REF,int(fr/191*49)))]
    sep=np.full((S,5,3),255,np.uint8);imgs=[]
    for _,im in cols: imgs+=[im,sep]
    row=np.hstack(imgs[:-1]); hdr=np.full((28,row.shape[1],3),20,np.uint8)
    for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(8+k*(S+5),19),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/FOUR_compare_{tag}.png",np.vstack([hdr,row])); print("wrote",tag)
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/FOUR_compare_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo COMPARE4_DONE
