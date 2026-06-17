#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/zoom.log 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
REF="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out/00000001.mp4"
FVSR="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/FlashVSR_v1.1_Tiny_ejea_lq_seed0.mp4"
def grab(p,idx,S=720):
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,max(0,n-1));c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=720;fr=20
cols=[("ORIGINAL Cesium",grab(ORIG,fr)),("Fun-Control+REF",grab(REF,int(fr/191*49))),("FlashVSR",grab(FVSR,fr))]
sep=np.full((S,6,3),255,np.uint8);imgs=[]
for _,im in cols: imgs+=[im,sep]
row=np.hstack(imgs[:-1]);hdr=np.full((34,row.shape[1],3),20,np.uint8)
for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(10+k*(S+6),24),cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),2)
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ZOOM_ref.png",np.vstack([hdr,row]));print("ok")
PY
echo ZOOM_DONE
