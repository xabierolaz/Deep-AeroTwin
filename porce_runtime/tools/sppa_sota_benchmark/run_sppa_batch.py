from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

from bench_common import ROOT, emit, gpu_snapshot, mesh_stats, read_objects


def load_generator(generator_path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {generator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_optional_json(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return json.loads(text)


def item_dims(module, item):
    if item.get("dims_m"):
        return module.parse_dims_cli(item["dims_m"]) if hasattr(module, "parse_dims_cli") else item["dims_m"]
    keys = ("target_length_m", "target_width_m", "target_height_m")
    if all(item.get(key) for key in keys):
        return {
            "length": float(item["target_length_m"]),
            "width": float(item["target_width_m"]),
            "height": float(item["target_height_m"]),
        }
    return None


def item_metric_scale(module, item):
    payload = item.get("metric_scale_json") or item.get("scale_json")
    if payload:
        loaded = load_optional_json(payload)
        return module.normalize_metric_scale(loaded) if hasattr(module, "normalize_metric_scale") else loaded
    if item.get("meters_per_pixel"):
        return {"meters_per_pixel": float(item["meters_per_pixel"]), "source": item.get("metric_scale_source") or "csv_meters_per_pixel"}
    if item.get("pixels_per_meter"):
        return {"pixels_per_meter": float(item["pixels_per_meter"]), "source": item.get("metric_scale_source") or "csv_pixels_per_meter"}
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark current SPPA procedural templates in-process.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--generator",
        default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"),
    )
    args = parser.parse_args()

    objects = read_objects(Path(args.objects_csv))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    module = load_generator(Path(args.generator))

    emit("SPPA_BENCH_RUN", {"model": "sppa", "gpu_before": gpu_snapshot()})
    for item in objects:
        label = item["label"]
        out = output_dir / label
        out.mkdir(parents=True, exist_ok=True)
        mesh = module.Mesh()
        start = time.perf_counter()
        dims = item_dims(module, item)
        bbox = load_optional_json(item.get("bbox_json"))
        mask = load_optional_json(item.get("mask_json"))
        world_pose = load_optional_json(item.get("world_json"))
        prev_world_pose = load_optional_json(item.get("prev_world_json"))
        metric_scale = item_metric_scale(module, item)
        if hasattr(module, "build_label_observed"):
            resolution = module.build_label_observed(
                mesh,
                label,
                dims_m=dims,
                bbox=bbox,
                mask=mask,
                metric_scale=metric_scale,
                height_m=item.get("height_m") or None,
            )
        elif hasattr(module, "build_label_parametric"):
            resolution = module.build_label_parametric(mesh, label, dims)
        elif hasattr(module, 'build_label'):
            resolution = module.build_label(mesh, label)
        else:
            builder = module.BUILDERS.get(label)
            if builder is None:
                builder = module.BUILDERS.get('unknown')
            if builder is None:
                raise KeyError(f'No SPPA builder or fallback for label {label}')
            builder(mesh)
            resolution = {'input_label': label, 'archetype': label, 'resolution_status': 'legacy_exact_or_unknown'}
        build_sec = time.perf_counter() - start
        mtl_path = out / f"{label}.mtl"
        obj_path = out / f"{label}.obj"
        manifest_path = out / f"{label}.materials.json"
        descriptor_path = out / f"{label}.descriptor.json"
        confidence = float(item.get("confidence") or 1.0)
        material_manifest = None
        start = time.perf_counter()
        if hasattr(module, "write_material_manifest"):
            material_manifest = module.write_material_manifest(str(manifest_path), mesh, resolution, confidence)
        try:
            module.write_mtl(str(mtl_path), material_manifest=material_manifest)
        except TypeError:
            module.write_mtl(str(mtl_path))
        module.write_obj(mesh, str(obj_path), mtl_path.name)
        export_sec = time.perf_counter() - start
        descriptor = None
        if hasattr(module, "write_sppa_descriptor"):
            descriptor = module.write_sppa_descriptor(
                str(descriptor_path),
                mesh,
                resolution,
                confidence,
                bbox=bbox,
                mask=mask,
                world_pose=world_pose,
                prev_world_pose=prev_world_pose,
                image_width=item.get("image_width") or item.get("img_width") or None,
                image_height=item.get("image_height") or item.get("img_height") or None,
                dims_m=resolution.get("effective_dims_m") or dims,
                yaw_deg=item.get("yaw_deg") or None,
                heading_deg=item.get("heading_deg") or None,
                track_id=item.get("track_id") or None,
                timestamp=item.get("timestamp") or None,
                frame_id=item.get("frame_id") or None,
                source_log=item.get("source_log") or None,
                source_event_index=item.get("source_event_index") or None,
                create_cpu_us=build_sec * 1_000_000.0,
                export_cpu_us_if_any=export_sec * 1_000_000.0,
            )
        payload = {
            "model": "sppa",
            "label": label,
            "prompt": item["prompt"],
            'archetype': resolution.get('archetype'),
            'resolution_status': resolution.get('resolution_status'),
            "shape_policy": resolution.get("shape_policy"),
            "metric_dims_source": resolution.get("metric_dims_source"),
            "status": "ok",
            "build_sec": build_sec,
            "export_sec": export_sec,
            "wall_sec": build_sec + export_sec,
            "gpu_after": gpu_snapshot(),
            "material_manifest_path": str(manifest_path).replace('\\', '/'),
            "material_descriptor_schema": material_manifest.get("descriptor_schema") if material_manifest else None,
            "material_policy": material_manifest.get("material_policy") if material_manifest else None,
            "material_count": len(material_manifest.get("materials", [])) if material_manifest else 0,
            "fallback_material_count": sum(1 for m in material_manifest.get("materials", []) if m.get("evidence_source") == "fallback_unknown") if material_manifest else 0,
            "descriptor_path": str(descriptor_path).replace('\\', '/') if descriptor else None,
            "descriptor_schema": descriptor.get("descriptor_schema") if descriptor else None,
            "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes") if descriptor else None,
            "descriptor_yaw_source": descriptor.get("pose", {}).get("yaw_source") if descriptor else None,
            "descriptor_scale_source": descriptor.get("scale", {}).get("scale_source") if descriptor else None,
        }
        payload.update(mesh_stats(obj_path))
        emit("SPPA_BENCH_OBJECT", payload)


if __name__ == "__main__":
    main()
