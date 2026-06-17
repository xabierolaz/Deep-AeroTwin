"""Detection-aware composite: photoreal background (ns=0.8) + faithful object
regions taken from the ORIGINAL Unreal frame, blended at YOLO bboxes.
Guarantees cyclists/towers/cows appear exactly where detection found them."""
import json
import cv2
import numpy as np

INP = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"      # original (faithful objects)
BG = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_restyled.mp4"         # ns 0.8 photoreal background
BB = json.load(open(r"D:\Deep-AeroTwin-UE57-Test\tmp\clip_bboxes.json"))
VID = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_detaware.mp4"
STILL = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_detaware_still.png"

S = 480
SCALE = S / 640.0
COLOR = {"biker": (60,60,230), "bike": (60,60,230), "cow": (40,170,240), "tower": (210,140,40)}

ci = cv2.VideoCapture(INP)
cb = cv2.VideoCapture(BG)
n = min(int(ci.get(7)), int(cb.get(7)))

def composite(orig, bg, boxes):
    out = bg.copy().astype(np.float32)
    objf = orig.astype(np.float32)
    mask = np.zeros((S, S), np.float32)
    for o in boxes:
        x1 = max(0, int(o["x1"] * SCALE) - 3); y1 = max(0, int(o["y1"] * SCALE) - 3)
        x2 = min(S, int(o["x2"] * SCALE) + 3); y2 = min(S, int(o["y2"] * SCALE) + 3)
        if x2 <= x1 or y2 <= y1:
            continue
        m = np.zeros((S, S), np.float32)
        m[y1:y2, x1:x2] = 1.0
        m = cv2.GaussianBlur(m, (0, 0), sigmaX=2.5)
        mask = np.maximum(mask, m)
    m3 = cv2.merge([mask, mask, mask])
    return (objf * m3 + out * (1 - m3)).astype(np.uint8)

wr = cv2.VideoWriter(VID, cv2.VideoWriter_fourcc(*"mp4v"), 16, (S, S))
peloton_idx = (5728 - 5600) // 2
still = {}
for i in range(n):
    oki, orig = ci.read(); okb, bg = cb.read()
    if not (oki and okb):
        break
    orig = cv2.resize(orig, (S, S))
    boxes = BB.get(str(i), [])
    comp = composite(orig, bg, boxes)
    wr.write(comp)
    if i == peloton_idx:
        still = {"inp": orig.copy(), "bg": bg.copy(), "comp": comp.copy(), "boxes": boxes}
wr.release()

if still:
    sep = np.full((S, 6, 3), 255, np.uint8)
    # also a labeled version of the composite to show what's preserved
    lab = still["comp"].copy()
    for o in still["boxes"]:
        x1 = int(o["x1"] * SCALE); y1 = int(o["y1"] * SCALE)
        x2 = int(o["x2"] * SCALE); y2 = int(o["y2"] * SCALE)
        cv2.rectangle(lab, (x1, y1), (x2, y2), COLOR.get(o["type"], (255,255,255)), 1)
    row = np.hstack([still["inp"], sep, still["bg"], sep, still["comp"], sep, lab])
    hdr = np.full((28, row.shape[1], 3), 25, np.uint8)
    for x, t in [(8,"INPUT"), (S+10,"ns0.8 (sin objetos)"), (2*S+16,"DETEC-CONSCIENTE"), (3*S+22,"+ bboxes")]:
        cv2.putText(hdr, t, (x, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    cv2.imwrite(STILL, np.vstack([hdr, row]))
print("done frames", n)
