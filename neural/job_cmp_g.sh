#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/cmp_g.log 2>&1
# esperar salida g8
for i in $(seq 1 40); do
  ls /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_g8_out/*.mp4 >/dev/null 2>&1 && break
  sleep 10
done
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np,glob
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
G4="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_out/00000001.mp4"
g8l=glob.glob("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_ref_g8_out/*.mp4")
G8=g8l[-1] if g8l else None
VACE="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"
def grab(p,idx,S=480):
    if not p: return np.zeros((S,S,3),np.uint8)
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,max(0,n-1));c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=480;fr=20
cols=[("ORIGINAL",grab(ORIG,fr)),("REF g4 (fiel)",grab(G4,int(fr/191*49))),
      ("REF g8 (mas realista)",grab(G8,int(fr/191*49))),("VACE (reinventa)",grab(VACE,int(fr/191*81)))]
sep=np.full((S,5,3),255,np.uint8);imgs=[]
for _,im in cols: imgs+=[im,sep]
row=np.hstack(imgs[:-1]);hdr=np.full((28,row.shape[1],3),20,np.uint8)
for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(8+k*(S+5),19),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/GUIDANCE_compare.png",np.vstack([hdr,row]));print("ok G8=",G8)
PY
echo CMPG_DONE
