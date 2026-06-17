#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/final_show.log 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np,glob
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
COL="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_final_color.mp4"
FIN=glob.glob("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/final_fvsr/*.mp4")[-1]
def grab(p,frac,S=560):
    c=cv2.VideoCapture(p);n=int(c.get(7));c.set(cv2.CAP_PROP_POS_FRAMES,int(n*frac));ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=560
for frac,tag in [(0.15,"a"),(0.5,"b"),(0.85,"c")]:
    cols=[("ORIGINAL Cesium",grab(ORIG,frac)),("VACE+color real",grab(COL,frac)),("+ FlashVSR (FINAL)",grab(FIN,frac))]
    sep=np.full((S,6,3),255,np.uint8);imgs=[]
    for _,im in cols: imgs+=[im,sep]
    row=np.hstack(imgs[:-1]);hdr=np.full((32,row.shape[1],3),20,np.uint8)
    for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(10+k*(S+6),22),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/FINAL_show_{tag}.png",np.vstack([hdr,row]));print("wrote",tag)
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/FINAL_show_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo SHOW_DONE
