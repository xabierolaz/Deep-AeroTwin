"""Dataset fine-tune para las 2 torres de video_final.mp4 (1280x960 @10fps, 239 frames).
Tracking por plantilla (matchTemplate multi-escala, EMA) con semillas manuales:
  - torre 1: seed frame 10  (caja del detector vf_v1, conf 0.72)
  - torre 2: seed frame 200 (caja manual verificada visualmente)
Salida: out/dataset_vf2 (images|labels / train|val) + tiras de verificacion.
"""
import sys
from pathlib import Path
import cv2

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test\porce_runtime\tools\real_flight_replay")
OUT = ROOT / "out"
VIDEO = r"D:\Deep-AeroTwin-UE57-Test\papers\pipeline_b_telemetry\data\video_final.mp4"
DS = OUT / "dataset_vf2"
W, H = 1280, 960
LABEL_EVERY = 2

SEEDS = [
    # (nombre, seed_frame, box x,y,w,h, rango frames [min,max]) — rangos clampados a tracking fiable
    ("t1", 10, (279, 177, 108, 330), (3, 66)),
    ("t2", 200, (582, 250, 103, 281), (175, 238)),
]
BG_FRAMES = list(range(70, 126, 4)) + [0, 1, 2]


class TemplateTracker:
    SCALES = (0.8, 1.0, 1.25)
    TPL = 160

    def init(self, frame, box):
        x, y, w, h = box
        self.box = [float(x), float(y), float(w), float(h)]
        crop = frame[int(y):int(y + h), int(x):int(x + w)]
        self.tpl = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (self.TPL, self.TPL))

    def update(self, frame):
        x, y, w, h = self.box
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cx, cy = x + w / 2, y + h / 2
        sw, sh = w * 2.6, h * 2.6
        x1, y1 = max(0, int(cx - sw / 2)), max(0, int(cy - sh / 2))
        x2, y2 = min(W, int(cx + sw / 2)), min(H, int(cy + sh / 2))
        search = gray[y1:y2, x1:x2]
        best = None
        for s in self.SCALES:
            tw, th = max(16, int(w * s)), max(16, int(h * s))
            if search.shape[1] < tw or search.shape[0] < th:
                continue
            tpl_s = cv2.resize(self.tpl, (tw, th))
            res = cv2.matchTemplate(search, tpl_s, cv2.TM_CCOEFF_NORMED)
            _, mx, _, ml = cv2.minMaxLoc(res)
            if best is None or mx > best[0]:
                best = (mx, ml, tw, th)
        if best is None:
            return False, self.box
        score, (bx, by), bw, bh = best
        nx, ny = x1 + bx, y1 + by
        self.box = [float(nx), float(ny), float(bw), float(bh)]
        crop = gray[ny:ny + bh, nx:nx + bw]
        if crop.size > 0:
            tpl_new = cv2.resize(crop, (self.TPL, self.TPL))
            self.tpl = cv2.addWeighted(self.tpl, 0.92, tpl_new, 0.08, 0)
        return score >= 0.45, self.box


def read_frame(cap, idx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    return f if ok else None


def main():
    cap = cv2.VideoCapture(VIDEO)
    verify = OUT / "track_verify_vf2"
    verify.mkdir(parents=True, exist_ok=True)

    labels = {}  # frame -> (cx,cy,w,h) normalizados
    for name, seed_f, seed_box, (fmin, fmax) in SEEDS:
        for direction in (-1, +1):
            tr = TemplateTracker()
            fr = read_frame(cap, seed_f)
            tr.init(fr, seed_box)
            labels[seed_f] = seed_box
            idx = seed_f
            lost = 0
            while True:
                idx += direction
                if idx < fmin or idx > fmax:
                    break
                fr = read_frame(cap, idx)
                if fr is None:
                    break
                ok, box = tr.update(fr)
                x, y, w, h = box
                area_ok = 12 < w < 900 and 12 < h < 900
                in_frame = x > -w / 2 and y > -h / 2 and x < W - w / 3 and y < H - h / 3
                if not ok or not area_ok or not in_frame:
                    lost += 1
                    if lost >= 3:
                        print(f"{name} dir{direction:+d}: perdido en f{idx}")
                        break
                    continue
                lost = 0
                labels[idx] = (x, y, w, h)
                if idx % 20 == 0:
                    vis = fr.copy()
                    cv2.rectangle(vis, (int(x), int(y)), (int(x + w), int(y + h)), (0, 0, 255), 2)
                    cv2.imwrite(str(verify / f"{name}_f{idx:03d}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(f"{name}: rango etiquetado f{min(k for k in labels)}..f{max(labels)}")

    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (DS / sub).mkdir(parents=True, exist_ok=True)
    (DS / "dataset.yaml").write_text(
        f"path: {DS.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: tower\n", encoding="utf-8")

    n_img = 0
    for idx in sorted(labels):
        if idx % LABEL_EVERY != 0:
            continue
        fr = read_frame(cap, idx)
        if fr is None:
            continue
        split = "val" if idx % 10 < 2 else "train"
        nm = f"f{idx:03d}"
        cv2.imwrite(str(DS / "images" / split / f"{nm}.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
        x, y, w, h = labels[idx]
        cx, cy = (x + w / 2) / W, (y + h / 2) / H
        with (DS / "labels" / split / f"{nm}.txt").open("w") as f:
            f.write(f"0 {cx:.6f} {cy:.6f} {w / W:.6f} {h / H:.6f}\n")
        n_img += 1
    n_bg = 0
    for idx in BG_FRAMES:
        fr = read_frame(cap, idx)
        if fr is None:
            continue
        split = "val" if idx % 10 < 2 else "train"
        nm = f"bg{idx:03d}"
        cv2.imwrite(str(DS / "images" / split / f"{nm}.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (DS / "labels" / split / f"{nm}.txt").write_text("")
        n_bg += 1
    cap.release()
    print(f"dataset_vf2: {n_img} imgs torre + {n_bg} fondos -> {DS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
