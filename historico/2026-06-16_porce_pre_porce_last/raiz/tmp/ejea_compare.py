"""Before/after stills (3 timepoints) + side-by-side comparison video for the Ejea restyle."""
import cv2
import numpy as np

INP = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"
OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled.mp4"
STILLS = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_before_after.png"
SIDE = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_side_by_side.mp4"

ci = cv2.VideoCapture(INP)
co = cv2.VideoCapture(OUT)
ni = int(ci.get(cv2.CAP_PROP_FRAME_COUNT))
no = int(co.get(cv2.CAP_PROP_FRAME_COUNT))
n = min(ni, no)
S = 480  # square display size

def read_at(cap, idx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    if not ok:
        return None
    return cv2.resize(f, (S, S))

# ---- 3-timepoint before/after montage ----
rows = []
for frac in (0.25, 0.5, 0.78):
    idx = int(frac * (n - 1))
    a = read_at(ci, idx); b = read_at(co, idx)
    if a is None or b is None:
        continue
    sep = np.full((S, 6, 3), 255, np.uint8)
    row = np.hstack([a, sep, b])
    cv2.putText(row, f"f{idx}", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    rows.append(row)
hsep = np.full((6, rows[0].shape[1], 3), 255, np.uint8)
montage = rows[0]
for r in rows[1:]:
    montage = np.vstack([montage, hsep, r])
# header
hdr = np.full((34, montage.shape[1], 3), 25, np.uint8)
cv2.putText(hdr, "Unreal (sim)", (S // 2 - 70, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.putText(hdr, "StreamDiffusionV2 (photoreal)", (S + 30, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
cv2.imwrite(STILLS, np.vstack([hdr, montage]))

# ---- side-by-side video ----
ci.set(cv2.CAP_PROP_POS_FRAMES, 0); co.set(cv2.CAP_PROP_POS_FRAMES, 0)
W = S * 2 + 6
wr = cv2.VideoWriter(SIDE, cv2.VideoWriter_fourcc(*"mp4v"), 16, (W, S + 30))
for i in range(n):
    oki, a = ci.read(); oko, b = co.read()
    if not (oki and oko):
        break
    a = cv2.resize(a, (S, S)); b = cv2.resize(b, (S, S))
    sep = np.full((S, 6, 3), 255, np.uint8)
    body = np.hstack([a, sep, b])
    bar = np.full((30, W, 3), 25, np.uint8)
    cv2.putText(bar, "INPUT  Unreal/Cesium (sim)", (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(bar, "OUTPUT  StreamDiffusionV2 photoreal", (S + 12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    wr.write(np.vstack([bar, body]))
wr.release()
print("stills+video done; frames", n)
