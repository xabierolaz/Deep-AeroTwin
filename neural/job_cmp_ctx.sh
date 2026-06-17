#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/cmp_ctx.log 2>&1
for i in $(seq 1 60); do
  ls /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_050/*.mp4 >/dev/null 2>&1 && break
  sleep 10
done
sleep 5
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np,glob
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
C10="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"  # ctx 1.0
def g1(d):
    l=glob.glob(d); return l[-1] if l else None
C02=g1("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_020/*.mp4")
C05=g1("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_ctx_050/*.mp4")
def grab(p,idx,S=440):
    if not p: return np.zeros((S,S,3),np.uint8)
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,max(0,n-1));c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=440;fr=20
cols=[("ORIGINAL",grab(ORIG,fr)),("vace_ctx 0.2",grab(C02,int(fr/191*49))),
      ("vace_ctx 0.5",grab(C05,int(fr/191*49))),("vace_ctx 1.0",grab(C10,int(fr/191*81)))]
sep=np.full((S,5,3),255,np.uint8);imgs=[]
for _,im in cols: imgs+=[im,sep]
row=np.hstack(imgs[:-1]);hdr=np.full((26,row.shape[1],3),20,np.uint8)
for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(8+k*(S+5),18),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/CTX_compare.png",np.vstack([hdr,row]));print("ok",C02,C05)
PY
echo CMPCTX_DONE
