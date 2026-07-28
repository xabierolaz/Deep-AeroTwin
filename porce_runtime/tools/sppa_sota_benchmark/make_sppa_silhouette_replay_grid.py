from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_geometric_projection"
    / "20260703_real_image_assumed_flight_replay"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_real_silhouette_replay_grid.png"


def draw_case(row: dict[str, Any], tile_w: int = 520, tile_h: int = 360):
    image_path = ROOT / str(row["image"])
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        image = np.full((tile_h, tile_w, 3), 245, dtype=np.uint8)
    h, w = image.shape[:2]
    scale = min(tile_w / float(w), (tile_h - 54) / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    tile = np.full((tile_h, tile_w, 3), 248, dtype=np.uint8)
    x0 = (tile_w - new_w) // 2
    y0 = 44
    tile[y0 : y0 + new_h, x0 : x0 + new_w] = resized

    bbox = row.get("bbox_xyxy") or []
    if len(bbox) == 4:
        x1, y1, x2, y2 = [int(round(float(v) * scale)) for v in bbox]
        cv2.rectangle(tile, (x0 + x1, y0 + y1), (x0 + x2, y0 + y2), (40, 40, 230), 2)

    native = row.get("native_detector_mask") or {}
    proxy = row.get("silhouette_proxy") or {}
    mask_source = "YOLOE native mask" if native.get("polygon") else "silhouette proxy"
    mask_payload = native if native.get("polygon") else proxy
    polygon = mask_payload.get("polygon") or []
    if len(polygon) >= 3:
        pts = np.array(
            [[int(round(x0 + float(x) * scale)), int(round(y0 + float(y) * scale))] for x, y in polygon],
            dtype=np.int32,
        )
        overlay = tile.copy()
        cv2.fillPoly(overlay, [pts], (60, 190, 70))
        tile = cv2.addWeighted(overlay, 0.28, tile, 0.72, 0.0)
        cv2.polylines(tile, [pts], True, (30, 145, 45), 2)

    case_id = str(row.get("case_id") or "case")
    q = mask_payload.get("quality_score")
    q_text = "-" if q is None else f"{float(q):.2f}"
    cv2.putText(tile, case_id, (12, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(tile, f"bbox + {mask_source} q={q_text}", (12, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (20, 20, 20), 1, cv2.LINE_AA)
    return tile


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a real-image SPPA bbox/silhouette evidence grid.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out = args.out if args.out.is_absolute() else ROOT / args.out
    report = json.loads(replay_json.read_text(encoding="utf-8"))
    rows = list(report.get("rows") or [])
    tiles = [draw_case(row) for row in rows]
    if not tiles:
        raise SystemExit("No rows to render")
    while len(tiles) < 4:
        tiles.append(np.full_like(tiles[0], 248))
    top = np.hstack(tiles[:2])
    bottom = np.hstack(tiles[2:4])
    grid = np.vstack([top, bottom])
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), grid)
    print(json.dumps({"out": str(out), "rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
