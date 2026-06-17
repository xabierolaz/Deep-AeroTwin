"""Compare object preservation: input vs ns0.8 vs ns0.5 at the peloton frame, zoomed."""
import cv2
import numpy as np

INP = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"
O8 = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled.mp4"
O5 = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled_ns05.mp4"
OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\objects_ns_compare.png"
idx = (5728 - 5600) // 2

def frame(p, i, size=480):
    c = cv2.VideoCapture(p); c.set(cv2.CAP_PROP_POS_FRAMES, i); ok, f = c.read(); c.release()
    return cv2.resize(f, (size, size)) if ok else None

a, b8, b5 = frame(INP, idx), frame(O8, idx), frame(O5, idx)
x1, y1, x2, y2 = int(255*.75), int(290*.75), int(380*.75), int(400*.75)
pad = 6
def zoom(img):
    c = img[max(0,y1-pad):y2+pad, max(0,x1-pad):x2+pad]
    return cv2.resize(c, (c.shape[1]*4, c.shape[0]*4), interpolation=cv2.INTER_NEAREST)
za, z8, z5 = zoom(a), zoom(b8), zoom(b5)
H = za.shape[0]
sep = np.full((H, 6, 3), 255, np.uint8)
row = np.hstack([za, sep, z5, sep, z8])
hdr = np.full((28, row.shape[1], 3), 25, np.uint8)
w3 = za.shape[1]
cv2.putText(hdr, "INPUT (peloton)", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
cv2.putText(hdr, "ns=0.5", (w3+12, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
cv2.putText(hdr, "ns=0.8", (2*w3+18, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
cv2.imwrite(OUT, np.vstack([hdr, row]))
print("saved")
