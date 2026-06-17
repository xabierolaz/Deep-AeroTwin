import cv2
import numpy as np

def mid_frame(p):
    c = cv2.VideoCapture(p)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    c.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 2))
    ok, f = c.read()
    c.release()
    return f if ok else None

inp = mid_frame(r"D:\Deep-AeroTwin-UE57-Test\tmp\poc_input.mp4")
out = mid_frame(r"D:\Deep-AeroTwin-UE57-Test\tmp\poc_output.mp4")
h = max(inp.shape[0], out.shape[0])
def fit(x):
    return cv2.resize(x, (int(x.shape[1] * h / x.shape[0]), h))
inp, out = fit(inp), fit(out)
sep = np.full((h, 6, 3), 255, np.uint8)
combo = np.hstack([inp, sep, out])
cv2.putText(combo, "INPUT (sim)", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
cv2.putText(combo, "OUTPUT (StreamDiffusionV2)", (inp.shape[1] + 16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
cv2.imwrite(r"D:\Deep-AeroTwin-UE57-Test\tmp\poc_before_after.png", combo)
print("saved", combo.shape)
