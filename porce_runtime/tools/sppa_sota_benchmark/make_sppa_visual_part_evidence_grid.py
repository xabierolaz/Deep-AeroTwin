from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "real_image_assumed_flight_replay.json"
DEFAULT_PROBE_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_agnostic_image_space_parts_probe.json"
DEFAULT_AUDIT_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_visual_part_evidence_audit.json"
DEFAULT_VIEW_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified" / "views" / "contact_sheets"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_visual_part_evidence_grid.png"
DEFAULT_REPORT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_visual_part_evidence_grid.json"


ROLE_LABELS = {
    "vehicle_tire": "tire",
    "vehicle_metal_or_hub": "hub",
    "bike_frame": "frame",
    "vertical_structure_metal": "tower metal",
    "vehicle_attachment": "attachment",
    "container_detail": "container detail",
}
SCOPE_LABELS = {
    "round_part_pair_candidate": "round-pair cue",
    "multi_line_structure_candidate": "multi-line cue",
    "weak_round_pair_candidate": "weak round-pair cue",
    "image_edge_axis_candidate": "edge-axis cue",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def root_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fit_image(image: Image.Image, size: tuple[int, int], fill=(248, 248, 248)) -> Image.Image:
    image = image.convert("RGB")
    out = Image.new("RGB", size, fill)
    scale = min(size[0] / image.width, size[1] / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    x = (size[0] - resized.width) // 2
    y = (size[1] - resized.height) // 2
    out.paste(resized, (x, y))
    return out


def crop_with_cues(image_path: Path, probe_row: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    crop_xyxy = [int(round(float(v))) for v in probe_row.get("crop_xyxy") or [0, 0, image.width, image.height]]
    crop = image.crop(tuple(crop_xyxy))
    cues = probe_row.get("image_space_cues") or {}
    scope = str(cues.get("scope") or "")
    overlay = crop.convert("RGBA")
    draw = ImageDraw.Draw(overlay)

    for box in [probe_row.get("mask_bbox_xyxy_crop") or []]:
        if len(box) == 4:
            x1, y1, x2, y2 = [float(v) for v in box]
            draw.rectangle((x1, y1, x2, y2), outline=(255, 230, 0, 220), width=2)

    for line in cues.get("line_primitive_candidates") or []:
        xyxy = line.get("xyxy") or []
        if len(xyxy) == 4:
            draw.line(tuple(float(v) for v in xyxy), fill=(210, 45, 255, 215), width=2)

    draw_round_cues = "round" in scope
    if draw_round_cues:
        for circle in cues.get("round_primitive_candidates") or []:
            center = circle.get("center_xy") or []
            radius = float(circle.get("radius_px") or 0.0)
            if len(center) == 2 and radius > 0:
                cx, cy = [float(v) for v in center]
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(40, 230, 110, 150), width=2)

        for pair in cues.get("validated_round_part_pairs") or []:
            centers = pair.get("centers_xy") or []
            if len(centers) == 2 and len(centers[0]) == 2 and len(centers[1]) == 2:
                x1, y1 = [float(v) for v in centers[0]]
                x2, y2 = [float(v) for v in centers[1]]
                draw.line((x1, y1, x2, y2), fill=(40, 255, 120, 255), width=4)

    return fit_image(overlay.convert("RGB"), size)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font: ImageFont.ImageFont, fill, max_width: int, line_gap: int = 4) -> int:
    x, y = xy
    words = text.split()
    line = ""
    for word in words:
        trial = word if not line else f"{line} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
            continue
        if line:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
        line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def roles_text(roles: list[str]) -> str:
    return ", ".join(ROLE_LABELS.get(role, role.replace("_", " ")) for role in roles)


def scope_text(scope: Any) -> str:
    return SCOPE_LABELS.get(str(scope), str(scope).replace("_", " "))


def profile_text(audit_row: dict[str, Any]) -> str:
    features = audit_row.get("geometry_profile_features") or []
    yaw_deg = audit_row.get("yaw_deg")
    if "round_pair" in features:
        axis = yaw_deg if yaw_deg is not None else audit_row.get("round_pair_axis_angle_deg")
        ratio = audit_row.get("round_pair_radius_ratio")
        sep = audit_row.get("round_pair_separation_radius_ratio")
        parts = ["round"]
        if axis is not None:
            parts.append(f"yaw {float(axis):.1f} deg")
        if ratio is not None:
            parts.append(f"r {float(ratio):.2f}")
        if sep is not None:
            parts.append(f"sep/r {float(sep):.1f}")
        return ", ".join(parts)
    if "line_structure" in features:
        angle = yaw_deg if yaw_deg is not None else audit_row.get("line_dominant_angle_deg")
        length = audit_row.get("line_max_length_px")
        parts = ["line"]
        if angle is not None:
            parts.append(f"yaw {float(angle):.1f} deg")
        if length is not None:
            parts.append(f"max {float(length):.0f} px")
        return ", ".join(parts)
    return "profile: none"


def role_panel(case: str, replay_row: dict[str, Any], audit_row: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    out = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(out)
    title = load_font(18, bold=True)
    body = load_font(13)
    small = load_font(11)
    draw.text((12, 10), case.replace("_", "+"), font=title, fill=(25, 25, 25))
    y = 38
    y = draw_wrapped(draw, f"YOLOE: {replay_row.get('detector_label')}", (12, y), body, (50, 50, 50), size[0] - 24)
    y = draw_wrapped(draw, f"Cue: {scope_text(audit_row.get('scope'))}", (12, y + 4), body, (30, 80, 110), size[0] - 24)
    y = draw_wrapped(draw, f"Roles: {roles_text(audit_row.get('roles') or [])}", (12, y + 4), body, (15, 95, 60), size[0] - 24)
    y = draw_wrapped(draw, f"Profile/yaw: {profile_text(audit_row)}", (12, y + 4), body, (80, 65, 120), size[0] - 24)
    y = draw_wrapped(
        draw,
        f"Budget: {float(audit_row.get('wall_ms') or 0):.3f} ms, {int(audit_row.get('triangles') or 0)} tris",
        (12, y + 4),
        body,
        (80, 60, 35),
        size[0] - 24,
    )
    draw.text((12, size[1] - 42), "No class change. No topology added.", font=small, fill=(145, 45, 45))
    draw.text((12, size[1] - 24), "Image-space profile only.", font=small, fill=(145, 45, 45))
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(220, 220, 220))
    return out


def load_view(case: str, view_dir: Path, size: tuple[int, int]) -> Image.Image:
    path = view_dir / f"{case}_views.png"
    if not path.exists():
        return Image.new("RGB", size, (246, 246, 246))
    return fit_image(Image.open(path).convert("RGB"), size)


def header_cell(title: str, subtitle: str, size: tuple[int, int]) -> Image.Image:
    out = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(out)
    draw.text((10, 8), title, font=load_font(18, bold=True), fill=(20, 20, 20))
    draw.text((10, 33), subtitle, font=load_font(11), fill=(75, 75, 75))
    draw.line((0, size[1] - 1, size[0], size[1] - 1), fill=(210, 210, 210), width=1)
    return out


def build_grid(
    replay: dict[str, Any],
    probe: dict[str, Any],
    audit: dict[str, Any],
    view_dir: Path,
    out_path: Path,
) -> dict[str, Any]:
    replay_rows = {str(row.get("case_id")): row for row in replay.get("rows") or []}
    probe_rows = {str(row.get("case_id")): row for row in probe.get("rows") or []}
    audit_rows = {str(row.get("case")): row for row in audit.get("rows") or []}
    cases = ["biker", "tower", "tractor", "tractor_trailer"]
    col_w = [285, 285, 300]
    row_h = 210
    header_h = 58
    width = sum(col_w)
    height = header_h + row_h * len(cases) + 34
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    x = 0
    for title, subtitle, w in [
        ("Real crop cues", "pixels + bbox + unlabeled mask", col_w[0]),
        ("SPPA descriptor roles", "visual support, no class change", col_w[1]),
        ("Proxy render", "same lightweight mesh budget", col_w[2]),
    ]:
        canvas.paste(header_cell(title, subtitle, (w, header_h)), (x, 0))
        x += w

    summary_rows = []
    y = header_h
    for case in cases:
        replay_row = replay_rows[case]
        probe_row = probe_rows[case]
        audit_row = audit_rows[case]
        crop_tile = crop_with_cues(root_path(replay_row.get("image")), probe_row, (col_w[0], row_h))
        panel = role_panel(case, replay_row, audit_row, (col_w[1], row_h))
        view = load_view(case, view_dir, (col_w[2], row_h))
        x = 0
        for tile, w in [(crop_tile, col_w[0]), (panel, col_w[1]), (view, col_w[2])]:
            canvas.paste(tile, (x, y))
            x += w
        summary_rows.append(
            {
                "case": case,
                "scope": audit_row.get("scope"),
                "roles": audit_row.get("roles"),
                "geometry_profile_features": audit_row.get("geometry_profile_features"),
                "yaw_source": audit_row.get("yaw_source"),
                "yaw_deg": audit_row.get("yaw_deg"),
                "yaw_coordinate_frame": audit_row.get("yaw_coordinate_frame"),
                "wall_ms": audit_row.get("wall_ms"),
                "triangles": audit_row.get("triangles"),
            }
        )
        y += row_h
    draw = ImageDraw.Draw(canvas)
    note = "Green circles/pairs and magenta lines are generic cues; SPPA stores compact image-space profiles for existing proxy roles only."
    draw.text((10, height - 25), note, font=load_font(12), fill=(55, 55, 55))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    return {
        "figure": str(out_path),
        "rows": summary_rows,
        "claim_boundary": (
            "This figure visualizes existing audited artifacts. It shows generic image-space cues and descriptor role "
            "support; it does not claim ground-truth part segmentation, semantic class changes, or added mesh topology."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SPPA visual part evidence grid.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--probe-json", type=Path, default=DEFAULT_PROBE_JSON)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--view-dir", type=Path, default=DEFAULT_VIEW_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    probe_json = args.probe_json if args.probe_json.is_absolute() else ROOT / args.probe_json
    audit_json = args.audit_json if args.audit_json.is_absolute() else ROOT / args.audit_json
    view_dir = args.view_dir if args.view_dir.is_absolute() else ROOT / args.view_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    report = build_grid(load_json(replay_json), load_json(probe_json), load_json(audit_json), view_dir, figure)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"figure": str(figure), "report": str(report_path), "rows": len(report["rows"])}, indent=2))


if __name__ == "__main__":
    main()
