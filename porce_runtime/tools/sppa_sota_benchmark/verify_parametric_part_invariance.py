from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def load_generator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_parts(module: Any, label: str, dims: tuple[float, float, float]) -> list[dict[str, Any]]:
    mesh = module.Mesh()
    module.build_label_parametric(mesh, label, {"length": dims[0], "width": dims[1], "height": dims[2]})
    return mesh.parts


def rounded(values: list[float] | tuple[float, ...], ndigits: int = 6) -> list[float]:
    return [round(float(value), ndigits) for value in values]


def parts_by_role(parts: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return [part for part in parts if part.get("role") == role]


def cargo_box(parts: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        part
        for part in parts
        if part.get("material") == "vehicle_neutral_body_prior" and part.get("primitive") == "box"
    ]
    if len(candidates) != 1:
        raise AssertionError(f"Expected one cargo box, found {len(candidates)}")
    return candidates[0]


def unique_scales(parts: list[dict[str, Any]], role: str) -> list[list[float]]:
    values = sorted({tuple(rounded(part["scale"])) for part in parts_by_role(parts, role)})
    return [list(value) for value in values]


def max_abs_delta(left: list[list[float]], right: list[list[float]]) -> float | None:
    if len(left) != len(right):
        return None
    deltas: list[float] = []
    for left_values, right_values in zip(left, right):
        if len(left_values) != len(right_values):
            return None
        deltas.extend(abs(float(a) - float(b)) for a, b in zip(left_values, right_values))
    return max(deltas) if deltas else 0.0


def verify(short_dims: tuple[float, float, float], long_dims: tuple[float, float, float], tolerance: float) -> dict[str, Any]:
    module = load_generator(DEFAULT_GENERATOR)
    short_parts = build_parts(module, "truck", short_dims)
    long_parts = build_parts(module, "truck", long_dims)

    short_cab_scales = unique_scales(short_parts, "vehicle_cab")
    long_cab_scales = unique_scales(long_parts, "vehicle_cab")
    short_tire_scales = unique_scales(short_parts, "vehicle_tire")
    long_tire_scales = unique_scales(long_parts, "vehicle_tire")
    short_cargo = cargo_box(short_parts)
    long_cargo = cargo_box(long_parts)

    failures: list[str] = []
    if short_dims[1:] != long_dims[1:]:
        failures.append("width_height_must_match_for_invariance_check")
    if short_dims[0] >= long_dims[0]:
        failures.append("long_length_must_exceed_short_length")
    if short_cab_scales != long_cab_scales:
        failures.append("cab_scale_changed")
    if short_tire_scales != long_tire_scales:
        failures.append("tire_scale_changed")

    short_cargo_length = float(short_cargo["scale"][0])
    long_cargo_length = float(long_cargo["scale"][0])
    cargo_length_delta = long_cargo_length - short_cargo_length
    if not long_cargo_length > short_cargo_length + tolerance:
        failures.append("cargo_length_did_not_increase")

    short_tire_count = len(parts_by_role(short_parts, "vehicle_tire"))
    long_tire_count = len(parts_by_role(long_parts, "vehicle_tire"))
    if long_tire_count < short_tire_count:
        failures.append("long_truck_lost_tires")

    return {
        "status": "ok" if not failures else "failed",
        "failures": failures,
        "short_dims_m": list(short_dims),
        "long_dims_m": list(long_dims),
        "short_cab_scales": short_cab_scales,
        "long_cab_scales": long_cab_scales,
        "short_tire_scales": short_tire_scales,
        "long_tire_scales": long_tire_scales,
        "cab_scale_max_abs_delta": max_abs_delta(short_cab_scales, long_cab_scales),
        "tire_scale_max_abs_delta": max_abs_delta(short_tire_scales, long_tire_scales),
        "short_cargo_length_m": round(short_cargo_length, 6),
        "long_cargo_length_m": round(long_cargo_length, 6),
        "cargo_length_delta_m": round(cargo_length_delta, 6),
        "short_tire_count": short_tire_count,
        "long_tire_count": long_tire_count,
        "tire_count_delta": long_tire_count - short_tire_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify that SPPA truck length adaptation changes cargo layout without scaling cab or tire parts."
    )
    parser.add_argument("--short-length", type=float, default=5.2)
    parser.add_argument("--long-length", type=float, default=8.2)
    parser.add_argument("--width", type=float, default=2.3)
    parser.add_argument("--height", type=float, default=2.7)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = verify(
        (args.short_length, args.width, args.height),
        (args.long_length, args.width, args.height),
        args.tolerance,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
