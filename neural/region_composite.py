#!/usr/bin/env python3
"""
region_composite.py — Localized neural restyle for AeroTwin.

Instead of applying the StreamDiffusion restyle to the WHOLE frame, this
composites the styled video ONLY inside the regions where YOLO detected an
object (biker / cow / tower), blending smoothly back into the original
footage everywhere else.

Two "sliders":
  --alpha        global strength of the restyle inside detected regions (0..1)
  --base-style   weak style applied everywhere as a floor (0..1), so the
                 background still gets a touch of style if you want it.

Per-class strength, feathering and box dilation are also adjustable.

Pure cv2 + numpy: runs anywhere, no GPU / torch needed. It consumes a
detections.json produced by detect_clip.py (run that in WSL with the GPU).

Example:
  python region_composite.py \
    --original tmp/ejea_clip_input.mp4 \
    --styled   neural/StreamDiffusionV2/poc_ejea/output_000.mp4 \
    --dets     neural/detections.json \
    --output   neural/ejea_localized.mp4 \
    --alpha 1.0 --base-style 0.0 --feather 25 --dilate 12 \
    --class-alpha cow=1.0,tower=0.9,biker=0.7
"""
import argparse, json, os, sys
import numpy as np
import cv2


def parse_class_alpha(s):
    out = {}
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition("=")
        out[k.strip().lower()] = float(v)
    return out


def build_mask(h, w, dets, class_alpha, default_strength, min_conf,
               dilate_px, feather_px):
    """Return float32 mask in [0,1]; value = per-region restyle strength."""
    mask = np.zeros((h, w), np.float32)
    for d in dets:
        if d.get("conf", 1.0) < min_conf:
            continue
        cls = str(d.get("cls", "")).lower()
        strength = class_alpha.get(cls, default_strength)
        if strength <= 0:
            continue
        x1, y1, x2, y2 = d["xyxy"]
        # detections may be in a different resolution; caller scales beforehand
        x1 = max(0, int(round(x1)) - dilate_px)
        y1 = max(0, int(round(y1)) - dilate_px)
        x2 = min(w, int(round(x2)) + dilate_px)
        y2 = min(h, int(round(y2)) + dilate_px)
        if x2 <= x1 or y2 <= y1:
            continue
        # max-combine so overlapping boxes take the strongest
        mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], strength)
    if feather_px > 0:
        k = int(feather_px) | 1  # odd kernel
        mask = cv2.GaussianBlur(mask, (k, k), 0)
    return np.clip(mask, 0.0, 1.0)


def scale_dets(frame_dets, src_w, src_h, dst_w, dst_h):
    if src_w == dst_w and src_h == dst_h:
        return frame_dets
    sx, sy = dst_w / src_w, dst_h / src_h
    out = []
    for d in frame_dets:
        x1, y1, x2, y2 = d["xyxy"]
        nd = dict(d)
        nd["xyxy"] = [x1 * sx, y1 * sy, x2 * sx, y2 * sy]
        out.append(nd)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True)
    ap.add_argument("--styled", required=True)
    ap.add_argument("--dets", required=True, help="detections.json from detect_clip.py")
    ap.add_argument("--output", required=True)
    ap.add_argument("--alpha", type=float, default=1.0,
                    help="global restyle strength inside detected regions (0..1)")
    ap.add_argument("--base-style", type=float, default=0.0,
                    help="weak style floor applied everywhere (0..1)")
    ap.add_argument("--class-alpha", default="",
                    help="per-class strength, e.g. cow=1.0,tower=0.9,biker=0.7")
    ap.add_argument("--default-strength", type=float, default=1.0,
                    help="strength for classes not listed in --class-alpha")
    ap.add_argument("--min-conf", type=float, default=0.40)
    ap.add_argument("--feather", type=int, default=25, help="gaussian feather px")
    ap.add_argument("--dilate", type=int, default=12, help="grow each box by px")
    ap.add_argument("--frame-offset", type=int, default=0,
                    help="styled[i] aligns to original[i+offset]")
    ap.add_argument("--max-frames", type=int, default=0, help="0 = all")
    ap.add_argument("--debug-mask", action="store_true",
                    help="also write *_mask.mp4 visualizing the mask")
    args = ap.parse_args()

    class_alpha = parse_class_alpha(args.class_alpha)

    with open(args.dets) as f:
        meta = json.load(f)
    det_w = meta.get("width")
    det_h = meta.get("height")
    frames_meta = {fr["index"]: fr.get("detections", []) for fr in meta["frames"]}

    cap_o = cv2.VideoCapture(args.original)
    cap_s = cv2.VideoCapture(args.styled)
    if not cap_o.isOpened() or not cap_s.isOpened():
        sys.exit("ERROR: could not open original/styled video")

    ow = int(cap_o.get(cv2.CAP_PROP_FRAME_WIDTH))
    oh = int(cap_o.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap_o.get(cv2.CAP_PROP_FPS) or 16.0
    n_o = int(cap_o.get(cv2.CAP_PROP_FRAME_COUNT))
    n_s = int(cap_s.get(cv2.CAP_PROP_FRAME_COUNT))
    n = min(n_o - max(0, args.frame_offset), n_s)
    if args.max_frames > 0:
        n = min(n, args.max_frames)

    det_w = det_w or ow
    det_h = det_h or oh

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(args.output, fourcc, fps, (ow, oh))
    vw_mask = None
    if args.debug_mask:
        mp = os.path.splitext(args.output)[0] + "_mask.mp4"
        vw_mask = cv2.VideoWriter(mp, fourcc, fps, (ow, oh))

    # skip offset frames in original
    for _ in range(max(0, args.frame_offset)):
        cap_o.read()

    written = 0
    det_frames_used = 0
    for i in range(n):
        ok_o, fo = cap_o.read()
        ok_s, fs = cap_s.read()
        if not ok_o or not ok_s:
            break
        if fs.shape[:2] != (oh, ow):
            fs = cv2.resize(fs, (ow, oh), interpolation=cv2.INTER_LINEAR)

        dets = frames_meta.get(i, [])
        if dets:
            det_frames_used += 1
        dets = scale_dets(dets, det_w, det_h, ow, oh)
        mask = build_mask(oh, ow, dets, class_alpha, args.default_strength,
                          args.min_conf, args.dilate, args.feather)
        mask = mask * args.alpha
        if args.base_style > 0:
            mask = np.maximum(mask, args.base_style)
        mask = np.clip(mask, 0.0, 1.0)[..., None]  # HxWx1

        fo_f = fo.astype(np.float32)
        fs_f = fs.astype(np.float32)
        out = fo_f + (fs_f - fo_f) * mask
        out = np.clip(out, 0, 255).astype(np.uint8)
        vw.write(out)
        if vw_mask is not None:
            mvis = (mask[..., 0] * 255).astype(np.uint8)
            vw_mask.write(cv2.cvtColor(mvis, cv2.COLOR_GRAY2BGR))
        written += 1

    cap_o.release(); cap_s.release(); vw.release()
    if vw_mask is not None:
        vw_mask.release()
    print(f"OK wrote {written} frames -> {args.output} "
          f"({det_frames_used} frames had detections)")


if __name__ == "__main__":
    main()
