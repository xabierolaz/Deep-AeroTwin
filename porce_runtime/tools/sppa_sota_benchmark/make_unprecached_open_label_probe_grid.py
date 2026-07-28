from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
PROBE_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_open_label_probe" / "20260704_unprecache_probe" / "probe_outputs"
SUMMARY_JSON = PROBE_DIR / "unprecached_open_label_probe.json"
OUT = PROBE_DIR / "unprecached_open_label_probe_grid.png"


def safe_name(text: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip()).strip("_") or "model"


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    out = text
    while out and draw.textlength(out + "...", font=font) > max_width:
        out = out[:-1]
    return out + "..." if out else "..."


def tile_for(label: str, mode: str, row: dict, size: int) -> Image.Image:
    safe = safe_name(label)
    image_path = PROBE_DIR / mode / "views" / "models" / "sppa" / safe / "iso.png"
    tile = Image.new("RGB", (size, size + 54), "white")
    draw = ImageDraw.Draw(tile)
    if image_path.exists():
        img = Image.open(image_path).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        tile.paste(img, (0, 0))
    else:
        draw.rectangle((0, 0, size - 1, size - 1), outline=(180, 180, 180), fill=(245, 245, 245))
        draw.text((10, size // 2 - 8), "missing render", fill=(80, 80, 80), font=load_font(12))
    font = load_font(12)
    bold = load_font(12, bold=True)
    status = f"{mode}: {row.get('generator_archetype')}/{row.get('resolution_status')}"
    roles = str(row.get("roles") or "")
    draw.text((8, size + 6), fit_text(draw, status, bold, size - 16), fill=(20, 20, 20), font=bold)
    draw.text((8, size + 28), fit_text(draw, roles, font, size - 16), fill=(70, 70, 70), font=font)
    return tile


def main() -> None:
    data = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    rows_by_label: dict[str, dict[str, dict]] = {}
    for row in data["rows"]:
        rows_by_label.setdefault(row["raw_label"], {})[row["mode"]] = row
    labels = list(rows_by_label)
    tile_size = 220
    label_w = 190
    row_h = tile_size + 54
    header_h = 42
    width = label_w + tile_size * 2
    height = header_h + row_h * len(labels)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(16, bold=True)
    label_font = load_font(12, bold=True)
    draw.text((10, 10), "Uncached open-label probe: raw tag vs normalized tag", fill=(20, 20, 20), font=title_font)
    draw.text((label_w + 70, 14), "Raw", fill=(20, 20, 20), font=label_font)
    draw.text((label_w + tile_size + 52, 14), "Normalized", fill=(20, 20, 20), font=label_font)
    for idx, label in enumerate(labels):
        y = header_h + idx * row_h
        fill = (248, 248, 248) if idx % 2 else (255, 255, 255)
        draw.rectangle((0, y, width, y + row_h), fill=fill)
        draw.text((10, y + 12), fit_text(draw, label, label_font, label_w - 20), fill=(20, 20, 20), font=label_font)
        raw = rows_by_label[label].get("raw", {})
        norm = rows_by_label[label].get("normalized", {})
        sheet.paste(tile_for(label, "raw", raw, tile_size), (label_w, y))
        sheet.paste(tile_for(label, "normalized", norm, tile_size), (label_w + tile_size, y))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
