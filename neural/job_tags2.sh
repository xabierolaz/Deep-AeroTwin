#!/bin/bash
exec > /mnt/d/Deep-AeroTwin-UE57-Test/tmp/tags2.log 2>&1
source ~/sdv2_venv/bin/activate
python - <<'PY'
import cv2,numpy as np
f=cv2.imread("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_clean.png")
H,W=f.shape[:2]
tags=[
 (1,(470,560),"filas de estructuras"),
 (2,(540,430),"zona beige abierta"),
 (3,(150,455),"superficie turquesa izq"),
 (4,(250,700),"turquesa abajo-izq"),
 (5,(830,520),"campo verde dcha"),
 (6,(700,355),"campo marron/tan"),
 (7,(360,345),"franja diagonal (carretera?)"),
 (8,(480,235),"colinas/horizonte"),
 (9,(720,120),"cielo"),
]
for n,(x,y),_ in tags:
    cv2.circle(f,(x,y),26,(0,0,0),-1)
    cv2.circle(f,(x,y),26,(0,255,255),3)
    s=str(n); ts=cv2.getTextSize(s,cv2.FONT_HERSHEY_SIMPLEX,0.9,2)[0]
    cv2.putText(f,s,(x-ts[0]//2,y+ts[1]//2),cv2.FONT_HERSHEY_SIMPLEX,0.9,(0,255,255),2)
# leyenda lateral
leg=np.full((H,430,3),25,np.uint8)
cv2.putText(leg,"IDENTIFICA CADA NUMERO:",(12,40),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)
for i,(n,_,txt) in enumerate(tags):
    y=80+i*46
    cv2.putText(leg,f"{n}.",(14,y),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)
    cv2.putText(leg,txt,(54,y),cv2.FONT_HERSHEY_SIMPLEX,0.55,(220,220,220),1)
out=np.hstack([f,leg])
cv2.imwrite("/mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_tagged.png",out)
print("ok")
PY
cp /mnt/d/Deep-AeroTwin-UE57-Test/tmp/frame_tagged.png '/mnt/c/Users/xabie/AppData/Roaming/Claude/local-agent-mode-sessions/3682cacb-9d71-4e50-8c63-b61d94a8e6ca/cdbbf262-19f2-47fc-b740-e9d24eed93a4/local_2595f30d-c4ba-45ce-9e18-016f151a053c/outputs/' 2>/dev/null
echo TAGS2_DONE
