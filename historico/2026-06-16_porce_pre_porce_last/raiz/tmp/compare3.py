import cv2, numpy as np
INP=r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"
O8=r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled.mp4"        # ns 0.8
O5=r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled_ns05.mp4"   # ns 0.5
OUT=r"D:\Deep-AeroTwin-UE57-Test\tmp\peloton_3way.png"
idx=(5728-5600)//2
def fr(p,i):
    c=cv2.VideoCapture(p); c.set(cv2.CAP_PROP_POS_FRAMES,i); ok,f=c.read(); c.release()
    return cv2.resize(f,(480,480)) if ok else None
a=fr(INP,idx); b=fr(O8,idx); d=fr(O5,idx)
x1,y1,x2,y2=int(255*.75),int(290*.75),int(380*.75),int(400*.75); pad=8
def z(img):
    c=img[max(0,y1-pad):y2+pad,max(0,x1-pad):x2+pad]
    return cv2.resize(c,(c.shape[1]*4,c.shape[0]*4),interpolation=cv2.INTER_NEAREST)
zs=[z(a),z(b),z(d)]; H=zs[0].shape[0]
labels=["INPUT (peloton)","ns=0.8 (mucho realismo)","ns=0.5 (mas fiel)"]
cols=[]
for img,lb,zz in zip([a,b,d],labels,zs):
    cv2.rectangle(img,(x1,y1),(x2,y2),(0,0,255),1)
    zz=cv2.resize(zz,(480,int(zz.shape[0]*480/zz.shape[1])))
    bar=np.full((26,480,3),25,np.uint8); cv2.putText(bar,lb,(6,18),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1)
    col=np.vstack([bar,img,np.full((4,480,3),255,np.uint8),zz]); cols.append(col)
sep=np.full((cols[0].shape[0],6,3),255,np.uint8)
combo=np.hstack([cols[0],sep,cols[1],sep,cols[2]])
cv2.imwrite(OUT,combo); print("saved",combo.shape)
