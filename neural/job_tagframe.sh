#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/tagframe.log 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np
c=cv2.VideoCapture("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_clip_input.mp4")
c.set(cv2.CAP_PROP_POS_FRAMES,20); ok,f=c.read(); c.release()
f=cv2.resize(f,(960,960))
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_clean.png",f)
# grid 4x4 numbered for reference
g=f.copy(); H,W=g.shape[:2]; n=0
for r in range(4):
    for col in range(4):
        n+=1
        x0,y0=col*W//4,r*H//4
        cv2.rectangle(g,(x0,y0),(x0+W//4,y0+H//4),(0,255,255),1)
        cv2.putText(g,str(n),(x0+6,y0+26),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,0),4)
        cv2.putText(g,str(n),(x0+6,y0+26),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_grid.png",g)
print("ok")
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_grid.png /mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_clean.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo TAG_DONE
