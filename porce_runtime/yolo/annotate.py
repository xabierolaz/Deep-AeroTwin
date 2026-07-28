#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class Box:
    class_id: int
    x1: int
    y1: int
    x2: int
    y2: int


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _norm_yolo(box: Box, w: int, h: int) -> tuple[int, float, float, float, float]:
    x1 = _clamp(min(box.x1, box.x2), 0, w - 1)
    x2 = _clamp(max(box.x1, box.x2), 0, w - 1)
    y1 = _clamp(min(box.y1, box.y2), 0, h - 1)
    y2 = _clamp(max(box.y1, box.y2), 0, h - 1)

    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    xc = x1 + bw / 2.0
    yc = y1 + bh / 2.0

    return (
        int(box.class_id),
        xc / float(w),
        yc / float(h),
        bw / float(w),
        bh / float(h),
    )


def _read_classes(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"missing_classes_file:{path}")
    classes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        classes.append(s)
    if not classes:
        raise SystemExit(f"empty_classes_file:{path}")
    return classes


def _list_images(src_dir: Path) -> list[Path]:
    if not src_dir.exists():
        raise SystemExit(f"missing_source_dir:{src_dir}")
    files = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    files.sort(key=lambda p: p.name.lower())
    if not files:
        raise SystemExit(f"no_images_found_in:{src_dir}")
    return files


def _label_path(labels_dir: Path, image_path: Path) -> Path:
    return labels_dir / f"{image_path.stem}.txt"


def _load_labels(labels_file: Path, w: int, h: int) -> list[Box]:
    if not labels_file.exists():
        return []
    boxes: list[Box] = []
    for line in labels_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(parts[0])
            xc = float(parts[1]) * w
            yc = float(parts[2]) * h
            bw = float(parts[3]) * w
            bh = float(parts[4]) * h
        except Exception:
            continue
        x1 = int(round(xc - bw / 2.0))
        y1 = int(round(yc - bh / 2.0))
        x2 = int(round(xc + bw / 2.0))
        y2 = int(round(yc + bh / 2.0))
        boxes.append(Box(class_id=class_id, x1=x1, y1=y1, x2=x2, y2=y2))
    return boxes


def _save_labels(labels_file: Path, boxes: list[Box], w: int, h: int) -> None:
    labels_file.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for b in boxes:
        class_id, xc, yc, bw, bh = _norm_yolo(b, w, h)
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    labels_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simple YOLO bbox annotator (next/prev + autosave).")
    p.add_argument("--src", type=Path, default=(Path(__file__).resolve().parent / "source"))
    p.add_argument("--labels", type=Path, default=(Path(__file__).resolve().parent / "labels"))
    p.add_argument("--classes", type=Path, default=(Path(__file__).resolve().parent / "yolo_classes.txt"))
    p.add_argument("--window", type=str, default="Deep-AeroTwin Annotator")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    src_dir: Path = args.src
    labels_dir: Path = args.labels
    classes_file: Path = args.classes
    classes = _read_classes(classes_file)

    images = _list_images(src_dir)
    idx = 0
    current_class = 0

    drawing = False
    start_xy: tuple[int, int] | None = None
    mouse_xy: tuple[int, int] | None = None

    frame = None
    frame_h = 0
    frame_w = 0
    boxes: list[Box] = []
    dirty = False

    def status_text() -> str:
        name = images[idx].name
        return f"[{idx + 1}/{len(images)}] {name} | class {current_class + 1}:{classes[current_class]} | boxes:{len(boxes)}"

    def help_lines() -> list[str]:
        return [
            "Mouse: drag to draw box (saved automatically)",
            "Keys: n next, p prev, 1/2/3 class, u undo, c clear, q quit",
            "Tip: labels saved to yolo/labels/<image>.txt (YOLO format)",
        ]

    def load_image(new_idx: int) -> None:
        nonlocal idx, frame, frame_h, frame_w, boxes, dirty
        if dirty and frame is not None:
            _save_labels(_label_path(labels_dir, images[idx]), boxes, frame_w, frame_h)
            dirty = False

        idx = _clamp(new_idx, 0, len(images) - 1)
        img_path = images[idx]
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            raise SystemExit(f"failed_to_read_image:{img_path}")
        frame = img
        frame_h, frame_w = frame.shape[:2]
        boxes = _load_labels(_label_path(labels_dir, img_path), frame_w, frame_h)
        dirty = False

    def draw_ui() -> None:
        if frame is None:
            return
        canvas = frame.copy()

        # Existing boxes
        for b in boxes:
            color = (0, 255, 0) if b.class_id == current_class else (0, 200, 255)
            cv2.rectangle(canvas, (b.x1, b.y1), (b.x2, b.y2), color, 2)
            label = classes[b.class_id] if 0 <= b.class_id < len(classes) else f"class{b.class_id}"
            cv2.putText(canvas, label, (b.x1, max(15, b.y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Current drawing preview
        if drawing and start_xy and mouse_xy:
            cv2.rectangle(canvas, start_xy, mouse_xy, (255, 0, 255), 2)

        # Status + help
        cv2.rectangle(canvas, (0, 0), (frame_w, 70), (0, 0, 0), -1)
        cv2.putText(canvas, status_text(), (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        y = 50
        for line in help_lines():
            cv2.putText(canvas, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
            y += 18

        cv2.imshow(args.window, canvas)

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata) -> None:
        nonlocal drawing, start_xy, mouse_xy, boxes, dirty
        if frame is None:
            return
        x = _clamp(int(x), 0, frame_w - 1)
        y = _clamp(int(y), 0, frame_h - 1)
        mouse_xy = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            start_xy = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            pass
        elif event == cv2.EVENT_LBUTTONUP:
            if drawing and start_xy:
                x1, y1 = start_xy
                new_box = Box(class_id=current_class, x1=x1, y1=y1, x2=x, y2=y)
                # Ignore tiny boxes
                if abs(new_box.x2 - new_box.x1) >= 2 and abs(new_box.y2 - new_box.y1) >= 2:
                    boxes.append(new_box)
                    dirty = True
                    _save_labels(_label_path(labels_dir, images[idx]), boxes, frame_w, frame_h)
                    dirty = False
            drawing = False
            start_xy = None

    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(args.window, on_mouse)
    load_image(0)

    while True:
        draw_ui()
        k = cv2.waitKey(20) & 0xFF

        if k == 255:
            continue

        if k in (ord("q"), 27):  # q or ESC
            break
        if k == ord("n"):
            load_image(idx + 1)
            continue
        if k == ord("p"):
            load_image(idx - 1)
            continue
        if k in (ord("1"), ord("2"), ord("3")):
            sel = int(chr(k)) - 1
            if 0 <= sel < len(classes):
                current_class = sel
            continue
        if k == ord("u"):  # undo last
            if boxes:
                boxes.pop()
                dirty = True
                _save_labels(_label_path(labels_dir, images[idx]), boxes, frame_w, frame_h)
                dirty = False
            continue
        if k == ord("c"):  # clear all
            if boxes:
                boxes.clear()
                dirty = True
                _save_labels(_label_path(labels_dir, images[idx]), boxes, frame_w, frame_h)
                dirty = False
            continue

    if dirty and frame is not None:
        _save_labels(_label_path(labels_dir, images[idx]), boxes, frame_w, frame_h)
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

