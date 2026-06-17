#!/bin/bash
LOG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/sdv2_colorlock.log
exec > "$LOG" 2>&1
source ~/sdv2_venv/bin/activate
N=/mnt/d/Deep-AeroTwin-UE57-Test/neural
ORIG=/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4
SD08=$N/StreamDiffusionV2/poc_ejea/output_000.mp4
SD05=$N/StreamDiffusionV2/poc_ejea_ns05/output_000.mp4
# color-lock (mantiene color/luz de Cesium, inyecta textura/detalle del gen SDV2)
python "$N/detail_transfer.py" --original "$ORIG" --gen "$SD08" --output /mnt/d/Deep-AeroTwin-UE57-Test/tmp/sd08_colorlock.mp4 --detail-gain 1.0 --sigma 7 --color-mode lab
python "$N/detail_transfer.py" --original "$ORIG" --gen "$SD05" --output /mnt/d/Deep-AeroTwin-UE57-Test/tmp/sd05_colorlock.mp4 --detail-gain 1.0 --sigma 7 --color-mode lab
# compare grid
python - <<'PY'
import cv2,numpy as np
ORIG="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4"
SD08="/mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2/poc_ejea/output_000.mp4"
CL08="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/sd08_colorlock.mp4"
FVSR="/mnt/d/Deep-AeroTwin-UE57-Test/tmp/pipeline/fvsr_out/FlashVSR_v1.1_Tiny_ejea_lq_seed0.mp4"
def grab(p,idx,S=448):
    c=cv2.VideoCapture(p);n=int(c.get(7));idx=min(idx,n-1);c.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,f=c.read();c.release()
    return cv2.resize(f,(S,S)) if ok else np.zeros((S,S,3),np.uint8)
S=448
for fr,tag in [(20,"a"),(40,"b")]:
    cols=[("ORIGINAL",grab(ORIG,fr)),("SDV2 ns0.8",grab(SD08,fr)),("SDV2+colorlock",grab(CL08,fr)),("FlashVSR",grab(FVSR,fr))]
    sep=np.full((S,5,3),255,np.uint8);imgs=[]
    for _,im in cols: imgs+=[im,sep]
    row=np.hstack(imgs[:-1]); hdr=np.full((26,row.shape[1],3),20,np.uint8)
    for k,(t,_) in enumerate(cols): cv2.putText(hdr,t,(8+k*(S+5),18),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
    cv2.imwrite(f"/mnt/d/Deep-AeroTwin-UE57-Test/tmp/SDLOCK_compare_{tag}.png",np.vstack([hdr,row])); print("wrote",tag)
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/SDLOCK_compare_*.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo SDLOCK_DONE
