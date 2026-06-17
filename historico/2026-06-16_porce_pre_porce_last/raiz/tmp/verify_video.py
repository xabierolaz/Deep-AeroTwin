import cv2
p = r"D:\Deep-AeroTwin-UE57-Test\tmp\ejea_route_yolo.mp4"
c = cv2.VideoCapture(p)
n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
fps = c.get(cv2.CAP_PROP_FPS)
c.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 2))
ok, f = c.read()
if ok:
    cv2.imwrite(r"D:\Deep-AeroTwin-UE57-Test\tmp\video_mid.png", f)
open(r"D:\Deep-AeroTwin-UE57-Test\tmp\verify_video.txt", "w").write(
    f"open={c.isOpened()} frames={n} fps={fps} dur_s={(n/fps if fps else 0):.0f} midok={ok}"
)
