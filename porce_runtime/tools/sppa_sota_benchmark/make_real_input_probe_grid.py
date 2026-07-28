from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_real_input_probe_grid.png"
TEXT3D_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_text3d_prompt_baselines"
SPPA_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DETECTOR_RUN = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_yoloe26s_universal_open_vocab_cpu"
)
ANNOTATION_MANIFEST = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)

CASES = [
    {
        "label": "biker",
        "input": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "biker_real_road_crop_512.png",
        "detector": DETECTOR_RUN / "cyclist_road_input_yoloe26s_open_vocab.png",
        "detector_note": "YOLOE mask: person+motorcycle",
        "semantic_note": "tag: cyclist/biker",
        "run": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_cyclist_sppa_triposr_hunyuan",
    },
    {
        "label": "tower",
        "input": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "tower_real_mountain_crop_512.png",
        "detector": DETECTOR_RUN / "tower_mountain_raw_input_yoloe26s_open_vocab.png",
        "detector_note": "YOLOE mask: electric pylon",
        "semantic_note": "tag: tower/pylon",
        "run": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tower_sppa_triposr_hunyuan",
    },
    {
        "label": "tractor",
        "mesh_label": "tractor",
        "input": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "tractor_real_mountain_crop_512.png",
        "detector": DETECTOR_RUN / "tractor_mountain_raw_input_yoloe26s_open_vocab.png",
        "detector_note": "YOLOE mask: agricultural vehicle",
        "semantic_note": "tag: tractor/farm",
        "run": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tractor_sppa_triposr_hunyuan",
    },
    {
        "label": "tractor+trailer",
        "annotation_label": "tractor_trailer",
        "mesh_label": "tractor",
        "sppa_mesh_label": "tractor_trailer",
        "optional_mesh_label": "tractor_trailer",
        "text_mesh_label": "tractor_trailer",
        "input": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "tractor_trailer_real_mountain_crop_512.png",
        "detector": DETECTOR_RUN / "tractor_trailer_mountain_raw_input_yoloe26s_open_vocab.png",
        "detector_note": "YOLOE mask: vehicle",
        "semantic_note": "tag: tractor_trailer",
        "run": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tractor_trailer_sppa_triposr_hunyuan",
    },
]

METHODS = [
    ("input", "Input evidence", "real crop, not GT", None),
    ("detector", "Detector probe", "YOLOE image evidence", None),
    ("sppa", "SPPA", "complete proxy", ("sppa", "iso.png")),
    ("shap_e_text_k16_6gb", "Shap-E", "text-only workflow", ("shap_e_text_k16_6gb", "iso.png")),
    ("point_e_text_sdf32_4096_6gb", "Point-E", "text-only workflow", ("point_e_text_sdf32_4096_6gb", "iso.png")),
    ("triposr_warm", "TripoSR", "image/crop workflow", ("triposr_warm_r128_6gb", "iso.png")),
    ("hunyuan3d_2mini_turbo_shape", "Hunyuan3D", "image/crop workflow", ("hunyuan3d_2mini_turbo_rgba_6gb", "iso.png")),
]

OPTIONAL_IMAGE_METHODS = [
    ("sf3d_warm", "SF3D", "image/crop workflow", ("sf3d_warm", "iso.png")),
    ("spar3d_warm", "SPAR3D", "image/crop workflow", ("spar3d_warm", "iso.png")),
    ("trellis2_4b", "TRELLIS.2", "image/crop workflow", ("trellis2_4b", "iso.png")),
    ("pixal3d", "Pixal3D", "image/crop workflow", ("pixal3d", "iso.png")),
    ("direct3d_s2", "Direct3D-S2", "image/crop workflow", ("direct3d_s2", "iso.png")),
    ("triposg_or_tripo_p1", "TripoSG/P1", "image/crop workflow", ("triposg_or_tripo_p1", "iso.png")),
    ("rodin_gen_2_5", "Rodin 2.5", "image/crop workflow", ("rodin_gen_2_5", "iso.png")),
]

OPTIONAL_METHOD_STATUS = {
    "sf3d_warm": "not reproduced\nload timeout",
    "spar3d_warm": "not reproduced\ngated weights",
    "trellis2_4b": "not reproduced\nnative deps",
    "pixal3d": "not reproduced\no_voxel wheel",
    "direct3d_s2": "not reproduced\ntorchsparse",
    "triposg_or_tripo_p1": "not reproduced\nuntil local run",
    "rodin_gen_2_5": "not run\ncommercial/API",
}


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
    ]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def read_rows(run_dir: Path, label: str | None = None) -> dict[str, dict[str, str]]:
    path = run_dir / "objects.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = {}
        for row in csv.DictReader(f):
            if label is not None and str(row.get("label") or "") != str(label):
                continue
            rows[row.get("model", "")] = row
        return rows


def mesh_label_for(case: dict) -> str:
    return case.get("mesh_label", case["label"])


def text_mesh_label_for(case: dict) -> str:
    return case.get("text_mesh_label", mesh_label_for(case))


def method_mesh_label_for(case: dict, method_key: str) -> str:
    if method_key == "sppa":
        return case.get("annotation_label", case.get("sppa_mesh_label", mesh_label_for(case)))
    if method_key in {method[0] for method in OPTIONAL_IMAGE_METHODS}:
        return case.get("optional_mesh_label", mesh_label_for(case))
    return mesh_label_for(case)


def candidate_view_paths(case: dict, method_key: str, view_spec: tuple[str, str]) -> list[Path]:
    model_dir, view_name = view_spec
    mesh_label = method_mesh_label_for(case, method_key)
    base_run = SPPA_RUN if method_key == "sppa" else case["run"]
    paths = [base_run / "views" / "models" / model_dir / mesh_label / view_name]
    runs_root = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs"
    if runs_root.exists():
        for run_dir in sorted(runs_root.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True):
            candidate = run_dir / "views" / "models" / model_dir / mesh_label / view_name
            if candidate not in paths:
                paths.append(candidate)
    return paths


def first_existing_view(case: dict, method_key: str, view_spec: tuple[str, str]) -> Path | None:
    for path in candidate_view_paths(case, method_key, view_spec):
        if path.exists():
            return path
    return None


def optional_method_complete(method: tuple[str, str, str, tuple[str, str]]) -> bool:
    method_key, _, _, view_spec = method
    return all(first_existing_view(case, method_key, view_spec) is not None for case in CASES)


def active_methods() -> list[tuple[str, str, str, tuple[str, str] | None]]:
    methods: list[tuple[str, str, str, tuple[str, str] | None]] = list(METHODS)
    methods.extend(OPTIONAL_IMAGE_METHODS)
    return methods


def find_method_row(case: dict, method_key: str, label: str) -> dict[str, str] | None:
    base_run = SPPA_RUN if method_key == "sppa" else case["run"]
    direct = read_rows(base_run, label).get(method_key)
    if direct:
        return direct
    runs_root = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs"
    if not runs_root.exists():
        return None
    for run_dir in sorted(runs_root.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True):
        row = read_rows(run_dir, label).get(method_key)
        if row:
            return row
    return None


def read_annotations(path: Path = ANNOTATION_MANIFEST) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(item.get("label")): item for item in data.get("items", [])}


def metric_text(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    status = str(row.get("status") or "")
    if status and status != "ok":
        return "no mesh\nno gen time"
    try:
        time_key = "generation_sec" if row.get("generation_sec") else "wall_sec"
        gen_ms = float(row.get(time_key) or 0.0) * 1000.0
        tris = int(float(row.get("triangles") or row.get("faces") or 0.0))
        vram = row.get("torch_peak_reserved_mb")
        time = f"gen {gen_ms:.1f} ms" if gen_ms < 1000.0 else f"gen {gen_ms / 1000.0:.2f} s"
        tri_text = f"{tris:,} tris" if tris else "tris n/a"
        if vram:
            vram_gb = float(vram) / 1024.0
            return f"{time}\n{tri_text}\nVRAM {vram_gb:.1f} GB"
        return f"{time}\n{tri_text}"
    except ValueError:
        return ""

def sppa_metric_text(row: dict[str, str] | None) -> str:
    base = metric_text(row)
    if not row:
        return base
    gate = str(row.get("observation_gate") or "").strip()
    applied = str(row.get("observation_applied") or "").strip().lower() in {"true", "1", "yes"}
    source = str(row.get("observation_fusion_source") or "").strip()
    if not gate:
        return base
    gate_label = {
        "shape_low_confidence": "low-conf reject",
        "vehicle_metric_aspect_implausible": "vehicle aspect reject",
        "vertical_height_only_low_confidence_shape": "height-only obs",
        "vehicle_soft_low_confidence_fusion": "soft scale fusion",
        "vehicle_soft_aspect_fusion": "aspect fusion",
        "vehicle_soft_constraint_fusion": "constraint fusion",
        "accepted_dims_low_mask_quality": "dims only",
        "accepted": "obs accepted",
    }.get(gate, gate.replace("_", " "))
    state = "obs fused" if applied and "fused" in source else ("obs applied" if applied else "obs rejected")
    return f"{state}\n{gate_label}\n{base}" if base else f"{state}\n{gate_label}"


def crop_nonwhite(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    diff = Image.new("L", rgba.size, 0)
    pixels = rgba.load()
    out = diff.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a > 20 and (abs(r - 255) > 10 or abs(g - 255) > 10 or abs(b - 255) > 10):
                out[x, y] = 255
    bbox = diff.getbbox()
    if bbox is None:
        return rgba
    pad = 8
    return rgba.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(rgba.width, bbox[2] + pad),
            min(rgba.height, bbox[3] + pad),
        )
    )


def draw_manual_bbox(image: Image.Image, annotation: dict | None) -> Image.Image:
    if not annotation:
        return image
    bbox = annotation.get("manual_bbox_xyxy")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return image
    image = image.copy()
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = [int(round(float(value))) for value in bbox]
    color = (235, 55, 55, 255)
    for offset in range(4):
        draw.rectangle((x0 - offset, y0 - offset, x1 + offset, y1 + offset), outline=color)
    font = load_font(18, bold=True)
    label = "manual 2D bbox"
    tb = draw.textbbox((0, 0), label, font=font)
    tw = tb[2] - tb[0]
    th = tb[3] - tb[1]
    lx = max(0, min(x0, image.width - tw - 8))
    ly = max(0, y0 - th - 8)
    draw.rectangle((lx, ly, lx + tw + 8, ly + th + 6), fill=(235, 55, 55, 230))
    draw.text((lx + 4, ly + 2), label, font=font, fill=(255, 255, 255, 255))
    return image


def paste_fit(
    canvas: Image.Image,
    path: Path,
    box: tuple[int, int, int, int],
    crop_white: bool,
    annotation: dict | None = None,
) -> None:
    x0, y0, x1, y1 = box
    if not path.exists():
        return
    image = Image.open(path).convert("RGBA")
    image = draw_manual_bbox(image, annotation)
    if crop_white:
        image = crop_nonwhite(image)
    image.thumbnail((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    canvas.alpha_composite(image, (x0 + (x1 - x0 - image.width) // 2, y0 + (y1 - y0 - image.height) // 2))


def centered(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - width) / 2, y0 + (y1 - y0 - height) / 2), text, font=font, fill=fill)


def multiline_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_gap: int = 4,
) -> None:
    lines = text.splitlines()
    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    widths = [bbox[2] - bbox[0] for bbox in metrics]
    heights = [bbox[3] - bbox[1] for bbox in metrics]
    total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
    x0, y0, x1, y1 = box
    y = y0 + (y1 - y0 - total_h) / 2
    for line, width, height in zip(lines, widths, heights):
        draw.text((x0 + (x1 - x0 - width) / 2, y), line, font=font, fill=fill)
        y += height + line_gap


def draw_pending_tile(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(
        (x0 + 8, y0 + 10, x1 - 8, y1 - 10),
        radius=8,
        fill=(252, 246, 246),
        outline=(180, 90, 90),
        width=2,
    )
    multiline_centered(draw, text, (x0 + 12, y0 + 12, x1 - 12, y1 - 12), load_font(16, bold=True), (130, 45, 45))


def image_for(case: dict, method_key: str, view_spec: tuple[str, str] | None) -> Path:
    if method_key == "input":
        return case["input"]
    if method_key == "detector":
        return case["detector"]
    if view_spec is None:
        raise ValueError(method_key)
    model_dir, view_name = view_spec
    if method_key in {"shap_e_text_k16_6gb", "point_e_text_sdf32_4096_6gb"}:
        text_label = text_mesh_label_for(case)
        return TEXT3D_RUN / "views" / "models" / model_dir / text_label / view_name
    dynamic_path = first_existing_view(case, method_key, view_spec)
    if dynamic_path is not None:
        return dynamic_path
    return case["run"] / "views" / "models" / model_dir / method_mesh_label_for(case, method_key) / view_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a two-case real-input probe grid for SPPA.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else ROOT / args.output
    annotations = read_annotations()
    title_font = load_font(21, bold=True)
    subtitle_font = load_font(14)
    row_font = load_font(20, bold=True)
    metric_font = load_font(11)
    note_font = load_font(14)

    left_w = 170
    cell_w = 190
    header_h = 58
    image_h = 162
    metric_h = 52
    row_h = image_h + metric_h + 12
    note_h = 40
    pad = 14
    methods = active_methods()
    width = left_w + pad + cell_w * len(methods) + pad
    height = pad + header_h + row_h * len(CASES) + note_h + pad
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for col, (_, title, subtitle, _) in enumerate(methods):
        x0 = left_w + pad + col * cell_w
        centered(draw, title, (x0, pad, x0 + cell_w, pad + 28), title_font, (20, 20, 20))
        centered(draw, subtitle, (x0, pad + 28, x0 + cell_w, pad + header_h), subtitle_font, (85, 85, 85))

    for row_index, case in enumerate(CASES):
        y0 = pad + header_h + row_index * row_h
        centered(draw, case["label"], (0, y0, left_w, y0 + image_h + metric_h), row_font, (20, 20, 20))
        text_label = text_mesh_label_for(case)
        text_rows = read_rows(TEXT3D_RUN, text_label)
        row_cache: dict[tuple[Path, str], dict[str, dict[str, str]]] = {}
        def rows_for(method_key: str) -> dict[str, dict[str, str]]:
            label = method_mesh_label_for(case, method_key)
            base_run = SPPA_RUN if method_key == "sppa" else case["run"]
            key = (base_run, label)
            if key not in row_cache:
                row_cache[key] = read_rows(base_run, label)
            return row_cache[key]
        for col, (method_key, _, _, view_spec) in enumerate(methods):
            x0 = left_w + pad + col * cell_w
            image_box = (x0 + 10, y0 + 8, x0 + cell_w - 10, y0 + image_h)
            path = image_for(case, method_key, view_spec)
            annotation_key = case.get("annotation_label", case["label"])
            annotation = annotations.get(annotation_key) if method_key == "detector" and bool(case.get("manual_detector_overlay")) else None
            if path.exists():
                paste_fit(canvas, path, image_box, crop_white=method_key not in {"input", "detector"}, annotation=annotation)
            elif method_key in OPTIONAL_METHOD_STATUS:
                draw_pending_tile(draw, image_box, OPTIONAL_METHOD_STATUS[method_key])
            if method_key == "detector":
                metric = case["detector_note"]
            elif method_key == "sppa":
                metric = f"{case['semantic_note']}\n{sppa_metric_text(rows_for(method_key).get('sppa'))}"
            elif method_key in {"shap_e_text_k16_6gb", "point_e_text_sdf32_4096_6gb"}:
                metric_key = {
                    "shap_e_text_k16_6gb": "shap_e_text_k16",
                    "point_e_text_sdf32_4096_6gb": "point_e_text_sdf32",
                }[method_key]
                metric = metric_text(text_rows.get(metric_key))
            elif method_key in {"triposr_warm", "hunyuan3d_2mini_turbo_shape"}:
                metric = metric_text(rows_for(method_key).get(method_key))
            elif method_key in {method[0] for method in OPTIONAL_IMAGE_METHODS}:
                metric = metric_text(find_method_row(case, method_key, method_mesh_label_for(case, method_key)))
                if not metric:
                    metric = "no mesh\nno gen time"
            else:
                metric = ""
            multiline_centered(
                draw,
                metric,
                (x0 + 4, y0 + image_h, x0 + cell_w - 4, y0 + image_h + metric_h),
                metric_font,
                (55, 55, 55),
                line_gap=3,
            )
            draw.rectangle((x0, y0, x0 + cell_w, y0 + image_h + metric_h), outline=(222, 222, 222), width=1)

    optional_count = len(methods) - len(METHODS)
    optional_complete_count = sum(1 for method in OPTIONAL_IMAGE_METHODS if optional_method_complete(method))
    note = (
        "Real-input probes: YOLOE/image-to-3D use images/crops; SPPA is shown once as the complete semantic proxy output. "
        "Detector masks and silhouette evidence are audited separately rather than shown as a competing SPPA column. "
        "Shap-E/Point-E use text prompts. "
        f"Optional image baselines shown as pending until complete local runs exist ({optional_complete_count}/{optional_count} complete). Not 3D ground truth."
    )
    draw.text((pad, height - pad - note_h + 12), note, font=note_font, fill=(45, 45, 45))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=95)
    print(output)


if __name__ == "__main__":
    main()
