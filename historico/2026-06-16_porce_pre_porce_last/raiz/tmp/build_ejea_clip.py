"""Build a clean Ejea input clip (pristine frames, no boxes/HUD) for the restyle POC."""
import cv2
from pathlib import Path

FRAMES = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_233504\vision\frames")
OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_clip_input.mp4"
# segment spanning the peloton approach + crossing (frame ~5600 to ~5860)
files = sorted(FRAMES.glob("yolo_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
seg = [p for p in files if 5600 <= int(p.stem.split("_")[1]) <= 5980]
print("segment frames:", len(seg))
h, w = cv2.imread(str(seg[0])).shape[:2]
wr = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*"mp4v"), 16, (w, h))
for p in seg:
    wr.write(cv2.imread(str(p)))
wr.release()
print(f"wrote {OUT} {w}x{h} {len(seg)} frames")
