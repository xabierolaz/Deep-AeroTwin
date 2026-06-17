import cv2
from pathlib import Path

FRAMES = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_233504\vision\frames")
files = sorted(FRAMES.glob("yolo_*.jpg"), key=lambda p: int(p.stem.split("_")[1]))
# video frame index of yolo_005728 (the case-study trigger frame)
names = [p.stem for p in files]
target = "yolo_005728"
vidx = names.index(target) if target in names else len(files) // 2
c = cv2.VideoCapture(r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_route_yolo.mp4")
c.set(cv2.CAP_PROP_POS_FRAMES, vidx)
ok, f = c.read()
if ok:
    cv2.imwrite(r"D:\Deep-AeroTwin-UE57-Test\tmp\video_detframe.png", f)
open(r"D:\Deep-AeroTwin-UE57-Test\tmp\detframe.txt", "w").write(f"video_index={vidx} ok={ok}")
