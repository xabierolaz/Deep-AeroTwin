from __future__ import annotations

import csv
from pathlib import Path

from collections import deque

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "XYT-xabi-yolo-telemetry" / "_visual_review"
OUT = ROOT / "experiments" / "sppa_sota_benchmark" / "inputs"

OBJECTS = [
    ("cow", "cow"),
    ("biker", "bicycle with rider"),
    ("tree", "tree"),
    ("car", "car"),
    ("truck", "truck"),
    ("tractor", "tractor"),
]


def fit_square(image: Image.Image, size: int = 512) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    # Preserve the source aspect ratio and place it on a clean white square.
    image.thumbnail((size - 32, size - 32), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas.convert("RGB")

def fit_square_rgba(image: Image.Image, size: int = 512) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGBA")
    image = remove_connected_white_background(image)
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    image.thumbnail((size - 32, size - 32), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas

def remove_connected_white_background(image: Image.Image, tolerance: int = 18) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    pixels = image.load()

    def is_background(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 0 and r >= 255 - tolerance and g >= 255 - tolerance and b >= 255 - tolerance

    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if is_background(x, y):
                queue.append((x, y))
                seen.add((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if (x, y) not in seen and is_background(x, y):
                queue.append((x, y))
                seen.add((x, y))

    while queue:
        x, y = queue.popleft()
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and is_background(nx, ny):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, prompt in OBJECTS:
        src_path = SRC / f"{label}.png"
        if not src_path.exists():
            raise FileNotFoundError(src_path)
        image = Image.open(src_path)
        out_path = OUT / f"{label}.png"
        rgba_path = OUT / f"{label}_rgba.png"
        fit_square(image).save(out_path)
        fit_square_rgba(image).save(rgba_path)
        rows.append(
            {
                "label": label,
                "prompt": prompt,
                "image": str(out_path.relative_to(ROOT)).replace("\\", "/"),
                "image_rgb": str(out_path.relative_to(ROOT)).replace("\\", "/"),
                "image_rgba": str(rgba_path.relative_to(ROOT)).replace("\\", "/"),
            }
        )

    with (OUT / "objects.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["label", "prompt", "image", "image_rgb", "image_rgba"])
        writer.writeheader()
        writer.writerows(rows)

    with (OUT / "objects_rgba.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["label", "prompt", "image"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "label": row["label"],
                    "prompt": row["prompt"],
                    "image": row["image_rgba"],
                }
            )


if __name__ == "__main__":
    main()
