#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/cmp_real.log 2>&1
for i in $(seq 1 50); do
  ls /mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_olivewinter/*.mp4 >/dev/null 2>&1 && break
  sleep 10
done
sleep 5
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np,glob
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
REF="/mnt/d/Deep-AeroTwin-UE57-Test/Captura de pantalla 2026-06-13 131038.png"  # foto real A-127 tierra
def g1(d):
    l=glob.glob(d); return l[-1] if l else None
TIE=g1("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_tierra/*.mp4")
OW=g1("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/vace_olivewinter/*.mp4")
ref=cv2.imread(REF); ref=cv2.cvtColor(ref,cv2.COLOR_BGR2LAB).astype(np.float32)
rm=[ref[...,c].mean() for c in range(3)]; rs=[ref[...,c].std()+1e-6 for c in range(3)]
def cmatch(bgr):
    l=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB).astype(np.float32)
    for c in range(3):
        l[...,c]=(l[...,c]-l[...,c].mean())/(l[...,c].std()+1e-6)*rs[c]+rm[c]
    return cv2.cvtColor(np.clip(l,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR)
def grab(p,idx,S=480,cm=False):
    if not p: return np.zeros((S,S,3),np.uint8)
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,max(0,n-1));c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    if not ok: return np.zeros((S,S,3),np.uint8)
    f=cv2.resize(f,(S,S)); return cmatch(f) if cm else f
S=480
for fr,tag in [(20,"a"),(40,"b")]:
    cols=[("ORIGINAL",grab(ORIG,fr)),("TIERRA",grab(TIE,int(fr/191*49))),
          ("TIERRA+colorReal",grab(TIE,int(fr/191*49),cm=True)),
          ("OLIVAR-invierno",grab(OW,int(fr/191*49))),
          ("OLIVAR+colorReal",grab(OW,int(fr/191*49),cm=True))]
    sep=np.full((S,4,3),255,np.uint8);imgs=[]
    for _,im in cols: imgs+=[im,sep]
    row=np.hstack(imgs[:-1]);hdr=np.full((26,row.shape[1],3),20,np.uint8)
    for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(8+k*(S+4),18),cv2.FONT_HERSHEY_SIMPLEX,0.46,(255,255,255),1)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/REAL_compare_{tag}.png",np.vstack([hdr,row]));print("wrote",tag)
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/REAL_compare_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo CMPREAL_DONE
