"""Check whether cyclists/towers survive the restyle: zoom the peloton region
in the input vs output at the crossing moment."""
import cv2
import numpy as np

INP = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"
OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled.mp4"
OUTPNG = r"D:\Deep-AeroTwin-UE57-Test\tmp\objects_check.png"

# clip = original frames 5600..5980 step2; peloton trigger frame ~5728 -> clip idx (5728-5600)/2
clip_idx = (5728 - 5600) // 2  # 64

ci = cv2.VideoCapture(INP); co = cv2.VideoCapture(OUT)
ci.set(cv2.CAP_PROP_POS_FRAMES, clip_idx); oki, a = ci.read()
co.set(cv2.CAP_PROP_POS_FRAMES, clip_idx); oko, b = co.read()
print("read", oki, oko, "input", None if a is None else a.shape, "out", None if b is None else b.shape)

# input is 640x640, output is 480x480 -> resize input to 480 for matching
a = cv2.resize(a, (480, 480))
# peloton in 640-space ~ x[280..360] y[295..385] -> scale 0.75
x1, y1, x2, y2 = int(255 * .75), int(290 * .75), int(380 * .75), int(400 * .75)
pad = 8
def crop(img):
    c = img[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
    return cv2.resize(c, (c.shape[1] * 4, c.shape[0] * 4), interpolation=cv2.INTER_NEAREST)
ca, cb = crop(a), crop(b)
# draw the region box on full frames
for img in (a, b):
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 1)
S = 480
sep = np.full((S, 6, 3), 255, np.uint8)
top = np.hstack([a, sep, b])
# zoom row (pad to width)
H = max(ca.shape[0], cb.shape[0])
def fit(x):
    return cv2.resize(x, (int(x.shape[1] * H / x.shape[0]), H))
ca, cb = fit(ca), fit(cb)
zsep = np.full((H, 6, 3), 255, np.uint8)
zoom = np.hstack([ca, zsep, cb])
if zoom.shape[1] < top.shape[1]:
    zoom = np.hstack([zoom, np.full((H, top.shape[1] - zoom.shape[1], 3), 25, np.uint8)])
elif zoom.shape[1] > top.shape[1]:
    zoom = cv2.resize(zoom, (top.shape[1], int(zoom.shape[0] * top.shape[1] / zoom.shape[1])))
hsep = np.full((6, top.shape[1], 3), 255, np.uint8)
combo = np.vstack([top, hsep, zoom])
hdr = np.full((30, combo.shape[1], 3), 25, np.uint8)
cv2.putText(hdr, "INPUT (peloton visible)", (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
cv2.putText(hdr, "OUTPUT (restyle)", (S + 12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
cv2.imwrite(OUTPNG, np.vstack([hdr, combo]))
print("saved", OUTPNG)
