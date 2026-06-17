#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/view_depth.log
exec > "$LOG" 2>&1
source ~/sdv2_venv/bin/activate
OUT=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_depth_out
# esperar hasta 240s a que aparezca el mp4
for i in $(seq 1 48); do
  f=$(ls "$OUT"/*.mp4 2>/dev/null | head -1)
  [ -n "$f" ] && break
  sleep 5
done
echo "VACE_DEPTH_MP4=$f"
python - <<'PY'
import cv2, numpy as np, glob
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
DCTRL="/mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_control_depth.mp4"
VCANNY="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_out/00000001.mp4"
vd=sorted(glob.glob("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/stage1_depth_out/*.mp4"))
VDEPTH=vd[-1] if vd else None
def grab(p,frac,S=480):
    c=cv2.VideoCapture(p); n=int(c.get(7)); c.set(cv2.CAP_PROP_POS_FRAMES,int(n*frac));ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
for frac in (0.2,0.5,0.8):
    cols=[("ORIG Cesium",grab(ORIG,frac)),("DEPTH ctrl",grab(DCTRL,frac)),
          ("VACE canny",grab(VCANNY,frac)),("VACE depth",grab(VDEPTH,frac) if VDEPTH else np.zeros((480,480,3),np.uint8))]
    sep=np.full((480,5,3),255,np.uint8); imgs=[]
    for _,im in cols: imgs+=[im,sep]
    row=np.hstack(imgs[:-1])
    hdr=np.full((26,row.shape[1],3),20,np.uint8)
    for k,(t,_) in enumerate(cols):
        cv2.putText(hdr,t,(8+k*485,18),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/depth_compare_{int(frac*100)}.png",np.vstack([hdr,row]))
    print("wrote depth_compare_%d"%int(frac*100))
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/depth_compare_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo VIEW_DEPTH_DONE
