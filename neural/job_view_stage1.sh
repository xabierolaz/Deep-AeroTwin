#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/view_stage1.log
exec > "$LOG" 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2, numpy as np
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
CTRL="/mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_control_canny.mp4"
VACE="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"
def info(p):
    c=cv2.VideoCapture(p); n=int(c.get(7)); w=int(c.get(3)); h=int(c.get(4)); c.release(); return n,w,h
no,wo,ho=info(ORIG); nv,wv,hv=info(VACE)
print("orig",no,wo,ho," vace",nv,wv,hv)
def grab(p,frac,S=480):
    c=cv2.VideoCapture(p); n=int(c.get(7)); c.set(cv2.CAP_PROP_POS_FRAMES,int(n*frac));ok,f=c.read();c.release()
    return cv2.resize(f,(S,S))
for frac in (0.2,0.5,0.8):
    o=grab(ORIG,frac); c=grab(CTRL,frac); v=grab(VACE,frac)
    sep=np.full((480,5,3),255,np.uint8)
    row=np.hstack([o,sep,c,sep,v])
    hdr=np.full((26,row.shape[1],3),20,np.uint8)
    for x,t in [(8,"ORIGINAL Cesium"),(485,"CANNY control"),(965,"VACE salida")]:
        cv2.putText(hdr,t,(x,18),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
    out=np.vstack([hdr,row])
    fn=f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/vace_compare_{int(frac*100)}.png"
    cv2.imwrite(fn,out); print("wrote",fn)
PY
echo VIEW_DONE
