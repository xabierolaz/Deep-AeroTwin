#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import cv2
from ultralytics import YOLO


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_defaults_model(root: Path) -> str:
    defaults = root / "pipeline" / "porce_defaults.env"
    if not defaults.exists():
        return str(root / "yolo" / "weights" / "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt")
    for line in defaults.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "PORCE_YOLO_MODEL":
            continue
        value = value.strip().replace("%PROJECT_ROOT%", str(root))
        return os.path.expandvars(value)
    return str(root / "yolo" / "weights" / "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt")


def route_from_name(path: Path) -> str:
    name = path.stem
    if "_offset_" in name:
        return name.split("_offset_", 1)[0].rsplit("_", 1)[0]
    parts = name.split("_")
    if len(parts) >= 4:
        return "_".join(parts[:4])
    return name


def draw_detections(image, detections):
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["xyxy"]]
        label = f"{det['class_name']} {det['conf']:.2f}"
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 80), 2)
        cv2.putText(image, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
        cv2.putText(image, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 80), 1)
    return image


def main() -> int:
    root = repo_root()
    default_raw = root / "figuras_paper_unreal_generadas" / "yolo_crossing_precheck" / "raw"
    default_out = root / "figuras_paper_unreal_generadas" / "yolo_crossing_precheck"
    parser = argparse.ArgumentParser(description="Run YOLO over Unreal peloton crossing precheck frames.")
    parser.add_argument("--raw-dir", type=Path, default=default_raw)
    parser.add_argument("--out-dir", type=Path, default=default_out)
    parser.add_argument("--model", default=read_defaults_model(root))
    parser.add_argument("--conf", type=float, default=0.10)
    parser.add_argument("--video-fps", type=float, default=8.0)
    parser.add_argument("--target-classes", default="biker,person,bicycle")
    parser.add_argument("--allow-missing-routes", action="store_true")
    args = parser.parse_args()

    raw_dir = args.raw_dir.resolve()
    out_dir = args.out_dir.resolve()
    annotated_dir = out_dir / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "yolo_precheck_manifest.json"
    video_path = out_dir / "yolo_crossing_precheck.mp4"

    frames = sorted(list(raw_dir.glob("*.png")) + list(raw_dir.glob("*.ppm")) + list(raw_dir.glob("*.jpg")))
    if not frames:
        raise SystemExit(f"No image frames found in {raw_dir}")

    model = YOLO(str(args.model))
    targets = {item.strip().lower() for item in str(args.target_classes).split(",") if item.strip()}
    route_stats = {}
    rows = []
    writer = None
    frame_size = None

    for frame_path in frames:
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        result = model.predict(source=image, conf=float(args.conf), verbose=False)[0]
        names = result.names or {}
        detections = []
        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            class_name = str(names.get(cls_id, cls_id)).lower()
            conf = float(box.conf[0].item())
            if targets and class_name not in targets:
                continue
            xyxy = [float(v) for v in box.xyxy[0].tolist()]
            detections.append({"class_name": class_name, "conf": conf, "xyxy": xyxy})

        route = route_from_name(frame_path)
        stats = route_stats.setdefault(route, {"frames": 0, "frames_with_dets": 0, "detections": 0, "max_conf": 0.0})
        stats["frames"] += 1
        stats["detections"] += len(detections)
        if detections:
            stats["frames_with_dets"] += 1
            stats["max_conf"] = max(stats["max_conf"], max(float(det["conf"]) for det in detections))

        annotated = draw_detections(image.copy(), detections)
        label = f"{route} | dets={len(detections)}"
        cv2.putText(annotated, label, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 4)
        cv2.putText(annotated, label, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
        out_frame = annotated_dir / (frame_path.stem + ".png")
        cv2.imwrite(str(out_frame), annotated)

        h, w = annotated.shape[:2]
        if writer is None:
            frame_size = (int(w), int(h))
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                float(args.video_fps),
                frame_size,
            )
            if not writer.isOpened():
                raise SystemExit(f"Could not open VideoWriter for {video_path}")
        if frame_size != (int(w), int(h)):
            annotated = cv2.resize(annotated, frame_size, interpolation=cv2.INTER_LINEAR)
        writer.write(annotated)

        rows.append(
            {
                "frame": str(frame_path),
                "annotated": str(out_frame),
                "route": route,
                "detections": detections,
            }
        )

    if writer is not None:
        writer.release()

    missing_routes = sorted(route for route, stats in route_stats.items() if int(stats["frames_with_dets"]) <= 0)
    manifest = {
        "ok": bool(not missing_routes or args.allow_missing_routes),
        "raw_dir": str(raw_dir),
        "annotated_dir": str(annotated_dir),
        "video": str(video_path),
        "model": str(args.model),
        "conf": float(args.conf),
        "target_classes": sorted(targets),
        "route_stats": route_stats,
        "missing_detection_routes": missing_routes,
        "frames": rows,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

    if missing_routes and not args.allow_missing_routes:
        raise SystemExit("Routes without YOLO detections: " + ", ".join(missing_routes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
