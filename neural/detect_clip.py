#!/usr/bin/env python3
"""
detect_clip.py — run the AeroTwin YOLO over a video clip, write detections.json.

Run this in WSL (GPU). Output feeds region_composite.py / the slider tool.

  python neural/detect_clip.py \
    --video tmp/ejea_clip_input.mp4 \
    --out   neural/detections.json \
    --conf 0.40

detections.json schema:
  {
    "video": "...", "width": W, "height": H, "fps": F, "n_frames": N,
    "model": "...", "conf": 0.40, "classes": ["biker","cow","tower"],
    "frames": [
      {"index": 0, "detections": [
          {"cls": "cow", "cls_id": 1, "conf": 0.83, "xyxy": [x1,y1,x2,y2]} ]},
      ...
    ]
  }
xyxy are pixel coords in the video's own (width,height).
"""
import argparse, json, os, sys

DEFAULT_MODEL = os.environ.get(
    "PORCE_YOLO_MODEL",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yolo",
                 "weights", "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--conf", type=float, default=0.40)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=None, help="e.g. 0 for GPU, cpu for CPU")
    ap.add_argument("--stride", type=int, default=1, help="detect every Nth frame")
    args = ap.parse_args()

    try:
        from ultralytics import YOLO
    except Exception as e:
        sys.exit(f"ultralytics not available ({e}); run inside the sdv2/WSL venv")
    import cv2

    model = YOLO(args.model)
    names = model.names  # {0:'biker',1:'cow',2:'tower'} expected
    print(f"[detect] model={args.model} classes={names}", flush=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"could not open {args.video}")
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    F = cap.get(cv2.CAP_PROP_FPS) or 16.0
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frames = []
    idx = 0
    total_dets = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.stride > 1 and (idx % args.stride != 0):
            idx += 1
            continue
        r = model.predict(frame, conf=args.conf, imgsz=args.imgsz,
                          device=args.device, verbose=False)[0]
        dets = []
        for b in r.boxes:
            cid = int(b.cls.item())
            xy = b.xyxy[0].tolist()
            dets.append({
                "cls": str(names.get(cid, cid)),
                "cls_id": cid,
                "conf": round(float(b.conf.item()), 4),
                "xyxy": [round(v, 1) for v in xy],
            })
        total_dets += len(dets)
        frames.append({"index": idx, "detections": dets})
        if idx % 25 == 0:
            print(f"[detect] frame {idx}/{N} dets={len(dets)}", flush=True)
        idx += 1
    cap.release()

    out = {
        "video": os.path.abspath(args.video),
        "width": W, "height": H, "fps": F, "n_frames": N,
        "model": os.path.abspath(args.model), "conf": args.conf,
        "classes": [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names),
        "frames": frames,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"[detect] DONE {len(frames)} frames, {total_dets} detections -> {args.out}",
          flush=True)


if __name__ == "__main__":
    main()
