from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REPO = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO / "pipeline" / "logs" / "zero_trust"
DEFAULT_OUT = Path(__file__).resolve().parent / "yolo_crossing_precheck" / "final_artifacts"

RAW_NAME = "figure_unreal_raw_peloton_crossing.png"
OVERLAY_NAME = "figure_yolo_overlay_peloton_crossing_close.png"
VIDEO_NAME = "video_yolo_peloton_crossing_event.mp4"
MANIFEST_NAME = "figure2_artifact_manifest.json"

COLORS = {
    "biker": (0, 220, 120),
    "person": (0, 220, 120),
    "bicycle": (0, 220, 120),
    "cow": (255, 190, 65),
    "tower": (255, 80, 80),
}


def load_latest_run() -> Path:
    latest_file = LOG_ROOT / "LATEST_RUN.txt"
    if not latest_file.exists():
        raise FileNotFoundError(f"Missing latest run pointer: {latest_file}")
    text = latest_file.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise RuntimeError(f"Empty latest run pointer: {latest_file}")
    path = Path(text)
    return path if path.is_absolute() else (LOG_ROOT / path)


def iter_events(path: Path) -> Any:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event["_line_no"] = line_no
            yield event


def normalize_detections(event: dict[str, Any]) -> list[dict[str, Any]]:
    detections = event.get("detections") or []
    normalized: list[dict[str, Any]] = []
    for det in detections:
        if not isinstance(det, dict):
            continue
        typ = str(det.get("type") or det.get("class") or det.get("name") or "").lower()
        bbox = det.get("bbox") or det.get("xyxy") or det.get("box")
        if not typ or bbox is None:
            continue
        try:
            if isinstance(bbox, dict):
                if all(key in bbox for key in ("x1", "y1", "x2", "y2")):
                    coords = [float(bbox[key]) for key in ("x1", "y1", "x2", "y2")]
                elif all(key in bbox for key in ("x", "y", "w", "h")):
                    x = float(bbox["x"])
                    y = float(bbox["y"])
                    coords = [x, y, x + float(bbox["w"]), y + float(bbox["h"])]
                else:
                    continue
            elif isinstance(bbox, list) and len(bbox) >= 4:
                coords = [float(v) for v in bbox[:4]]
            else:
                continue
            conf = float(det.get("confidence", det.get("conf", 0.0)) or 0.0)
        except (TypeError, ValueError):
            continue
        x1, y1, x2, y2 = coords
        if x2 <= x1 or y2 <= y1:
            continue
        clean = dict(det)
        clean["type"] = typ
        clean["bbox"] = [x1, y1, x2, y2]
        clean["confidence"] = conf
        clean["area"] = (x2 - x1) * (y2 - y1)
        normalized.append(clean)
    return normalized


def frame_number(event: dict[str, Any]) -> int | None:
    for key in ("frame", "frame_idx", "frame_index", "frame_id", "image_index"):
        value = event.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    path = str(event.get("image_path") or event.get("frame_path") or "")
    stem = Path(path).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return int(digits) if digits else None


def find_frame_file(frames_dir: Path, frame_no: int) -> Path:
    candidates = [
        frames_dir / f"yolo_{frame_no:06d}.jpg",
        frames_dir / f"yolo_{frame_no:06d}.png",
        frames_dir / f"frame_{frame_no:06d}.jpg",
        frames_dir / f"frame_{frame_no:06d}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    files = sorted(list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png")))
    if not files:
        raise FileNotFoundError(f"No frame images found in {frames_dir}")

    def score(path: Path) -> int:
        digits = "".join(ch for ch in path.stem if ch.isdigit())
        if not digits:
            return 10**9
        return abs(int(digits) - frame_no)

    return min(files, key=score)


def select_event(run_dir: Path, target_types: set[str], forced_frame: int | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    vision_events = run_dir / "vision" / "events.jsonl"
    if not vision_events.exists():
        raise FileNotFoundError(f"Missing vision events: {vision_events}")

    best: tuple[float, dict[str, Any], list[dict[str, Any]]] | None = None
    for event in iter_events(vision_events):
        if event.get("kind") != "vision_frame":
            continue
        no = frame_number(event)
        if forced_frame is not None and no != forced_frame:
            continue
        detections = normalize_detections(event)
        target = [det for det in detections if det["type"] in target_types]
        if not target:
            continue
        max_target = max(target, key=lambda det: det["area"] * max(det["confidence"], 0.05))
        score = max_target["area"] * max(max_target["confidence"], 0.05)
        if forced_frame is not None:
            score += 10**12
        if best is None or score > best[0]:
            best = (score, event, detections)

    if best is None:
        forced = f" at frame {forced_frame}" if forced_frame is not None else ""
        raise RuntimeError(f"No target detections found{forced} in {vision_events}")
    return best[1], best[2]


def draw_overlay(source: Path, out_path: Path, event: dict[str, Any], detections: list[dict[str, Any]], target_types: set[str]) -> None:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()
    frame_no = frame_number(event)

    for det in detections:
        typ = det["type"]
        color = COLORS.get(typ, (90, 170, 255))
        width = 4 if typ in target_types else 3
        x1, y1, x2, y2 = det["bbox"]
        draw.rectangle((x1, y1, x2, y2), outline=(*color, 255), width=width)
        label = f"{typ} {det['confidence']:.2f}"
        text_box = draw.textbbox((x1, y1), label, font=font)
        pad = 3
        label_h = text_box[3] - text_box[1] + pad * 2
        y_label = max(0, y1 - label_h)
        draw.rectangle((x1, y_label, x1 + (text_box[2] - text_box[0]) + pad * 2, y_label + label_h), fill=(*color, 220))
        draw.text((x1 + pad, y_label + pad), label, fill=(0, 0, 0), font=font)

    header = "YOLO detections | real Unreal frame"
    if frame_no is not None:
        header += f" | frame {frame_no}"
    draw.rectangle((12, 12, 12 + 360, 40), fill=(0, 0, 0, 170))
    draw.text((22, 20), header, fill=(255, 255, 255), font=font)
    image.save(out_path)


def build_video(
    frames_dir: Path,
    events_by_frame: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]],
    selected_frame: int,
    out_path: Path,
    radius: int,
    fps: int,
    target_types: set[str],
) -> str:
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local environment
        return f"skipped: cv2 unavailable ({exc})"

    frame_paths: list[tuple[int, Path]] = []
    for no in range(max(0, selected_frame - radius), selected_frame + radius + 1):
        try:
            frame_paths.append((no, find_frame_file(frames_dir, no)))
        except FileNotFoundError:
            continue

    deduped: list[tuple[int, Path]] = []
    seen: set[Path] = set()
    for no, path in frame_paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append((no, path))
    if not deduped:
        return "skipped: no frames in selected window"

    first = cv2.imread(str(deduped[0][1]))
    if first is None:
        return "skipped: first frame could not be read"
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        return "skipped: VideoWriter could not open output"

    tmp_overlay = out_path.with_suffix(".overlay_tmp.png")
    try:
        for no, path in deduped:
            event, detections = events_by_frame.get(no, ({}, []))
            if detections:
                draw_overlay(path, tmp_overlay, event, detections, target_types)
                frame = cv2.imread(str(tmp_overlay))
            else:
                frame = cv2.imread(str(path))
            if frame is not None:
                writer.write(frame)
    finally:
        writer.release()
        if tmp_overlay.exists():
            tmp_overlay.unlink()
    return "written"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract final Figure 2 assets from real YOLO vision events.")
    parser.add_argument("--run", type=Path, default=None, help="Run directory. Defaults to zero_trust/LATEST_RUN.txt.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--target-types", default="biker,person,bicycle")
    parser.add_argument("--frame", type=int, default=None)
    parser.add_argument("--video-radius", type=int, default=36)
    parser.add_argument("--video-fps", type=int, default=8)
    args = parser.parse_args()

    run_dir = args.run or load_latest_run()
    run_dir = run_dir.resolve()
    frames_dir = run_dir / "vision" / "frames"
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    target_types = {item.strip().lower() for item in args.target_types.split(",") if item.strip()}

    event, detections = select_event(run_dir, target_types, args.frame)
    selected_frame = frame_number(event)
    if selected_frame is None:
        raise RuntimeError("Selected event does not expose a frame number")
    source_frame = find_frame_file(frames_dir, selected_frame)

    raw_path = out_dir / RAW_NAME
    overlay_path = out_dir / OVERLAY_NAME
    video_path = out_dir / VIDEO_NAME
    shutil.copy2(source_frame, raw_path)
    draw_overlay(source_frame, overlay_path, event, detections, target_types)

    events_by_frame: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    counts: dict[str, int] = defaultdict(int)
    for item in iter_events(run_dir / "vision" / "events.jsonl"):
        if item.get("kind") != "vision_frame":
            continue
        no = frame_number(item)
        if no is None:
            continue
        dets = normalize_detections(item)
        if dets:
            events_by_frame[no] = (item, dets)
            for det in dets:
                counts[det["type"]] += 1

    video_status = build_video(
        frames_dir=frames_dir,
        events_by_frame=events_by_frame,
        selected_frame=selected_frame,
        out_path=video_path,
        radius=args.video_radius,
        fps=args.video_fps,
        target_types=target_types,
    )

    selected_targets = [det for det in detections if det["type"] in target_types]
    manifest = {
        "source_run": str(run_dir),
        "source_frame": str(source_frame),
        "selected_frame": selected_frame,
        "selected_event_line": event.get("_line_no"),
        "target_types": sorted(target_types),
        "selected_target_detections": selected_targets,
        "all_selected_detections": detections,
        "run_detection_counts": dict(sorted(counts.items())),
        "outputs": {
            "raw": str(raw_path),
            "overlay": str(overlay_path),
            "video": str(video_path) if video_path.exists() else None,
            "video_status": video_status,
        },
        "notes": "Overlay and video boxes are postprocessed from YOLO events; no Unreal ghost/prediction actors are used.",
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
