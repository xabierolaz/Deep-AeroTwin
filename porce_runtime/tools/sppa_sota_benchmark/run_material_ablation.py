from __future__ import annotations

import argparse
import csv
import importlib.util
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGET_DIMS_M = {
    'cow': (2.45, 0.95, 1.65),
    'biker': (1.85, 0.65, 2.20),
    'tree': (1.85, 1.65, 3.20),
    'car': (4.35, 1.85, 1.60),
    'truck': (6.60, 2.45, 2.85),
    'tractor': (3.80, 2.05, 2.45),
}

CLASS_COLOR = {
    'cow': 'white',
    'biker': 'yellow',
    'tree': 'green',
    'car': 'red',
    'truck': 'blue',
    'tractor': 'green',
}

METHODS = ('sppa_flat', 'sppa_class_color', 'sppa_part_material', 'sppa_part_material_metadata_low_conf')


def load_generator(path: Path):
    spec = importlib.util.spec_from_file_location('xyt_generate_3d', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mesh_bounds(mesh):
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def extents_from_bounds(bounds):
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    return (xmax - xmin, ymax - ymin, zmax - zmin)


def align_ground(mesh):
    xmin, xmax, ymin, ymax, zmin, zmax = mesh_bounds(mesh)
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    mesh.vertices = [(x - cx, y - cy, z - zmin) for x, y, z in mesh.vertices]
    return mesh


def scale_to_dims(mesh, dims):
    align_ground(mesh)
    sx, sy, sz = extents_from_bounds(mesh_bounds(mesh))
    tx, ty, tz = dims
    fx = tx / sx if sx > 1e-9 else 1.0
    fy = ty / sy if sy > 1e-9 else 1.0
    fz = tz / sz if sz > 1e-9 else 1.0
    mesh.vertices = [(x * fx, y * fy, z * fz) for x, y, z in mesh.vertices]
    return align_ground(mesh)


def triangle_count(mesh):
    return sum(max(0, len(indices) - 2) for indices, _material in mesh.faces)


def material_count(mesh):
    return len({material for _indices, material in mesh.faces})


def replace_materials(mesh, material):
    mesh.faces = [(indices, material) for indices, _old in mesh.faces]
    return mesh


def build_base_mesh(module, label, dims):
    mesh = module.Mesh()
    meta = module.build_label(mesh, label)
    scale_to_dims(mesh, dims)
    return mesh, meta


def build_method(module, label, dims, method):
    mesh, meta = build_base_mesh(module, label, dims)
    if method == 'sppa_flat':
        replace_materials(mesh, 'gray')
        meta = dict(meta, material_ablation='flat_gray')
    elif method == 'sppa_class_color':
        replace_materials(mesh, CLASS_COLOR.get(label, 'gray'))
        meta = dict(meta, material_ablation='class_color')
    elif method == 'sppa_part_material':
        meta = dict(meta, material_ablation='semantic_part_material')
    elif method == 'sppa_part_material_metadata_low_conf':
        meta = dict(meta, material_ablation='semantic_part_material_metadata_low_conf')
    else:
        raise KeyError(method)
    return mesh, meta


def summarize(values):
    values = sorted(values)
    if not values:
        return (0.0, 0.0)
    p95_index = min(len(values) - 1, int(0.95 * (len(values) - 1)))
    return statistics.median(values) * 1000.0, values[p95_index] * 1000.0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def measure(module, out_dir, label, dims, method, reps):
    build_times = []
    export_times = []
    manifest_times = []
    mesh = None
    meta = None
    manifest = None
    method_dir = out_dir / 'outputs' / method / label
    method_dir.mkdir(parents=True, exist_ok=True)
    obj_path = method_dir / f'{label}.obj'
    mtl_path = method_dir / f'{label}.mtl'
    manifest_path = method_dir / f'{label}.materials.json'
    confidence = 0.25 if method.endswith('metadata_low_conf') else 0.95

    for _ in range(reps):
        start = time.perf_counter()
        mesh, meta = build_method(module, label, dims, method)
        build_times.append(time.perf_counter() - start)
        assert mesh is not None and meta is not None

        start = time.perf_counter()
        if hasattr(module, 'write_material_manifest') and method.startswith('sppa_part_material'):
            manifest = module.write_material_manifest(str(manifest_path), mesh, meta, confidence)
        else:
            manifest = None
        manifest_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        module.write_mtl(str(mtl_path))
        module.write_obj(mesh, str(obj_path), mtl_path.name)
        export_times.append(time.perf_counter() - start)

    assert mesh is not None and meta is not None
    p50_build_ms, p95_build_ms = summarize(build_times)
    p50_export_ms, p95_export_ms = summarize(export_times)
    p50_manifest_ms, p95_manifest_ms = summarize(manifest_times)
    return {
        'label': label,
        'method': method,
        'reps': reps,
        'p50_build_ms': p50_build_ms,
        'p95_build_ms': p95_build_ms,
        'p50_export_ms': p50_export_ms,
        'p95_export_ms': p95_export_ms,
        'p50_manifest_ms': p50_manifest_ms,
        'p95_manifest_ms': p95_manifest_ms,
        'vertices': len(mesh.vertices),
        'faces': len(mesh.faces),
        'triangles': triangle_count(mesh),
        'material_count': material_count(mesh),
        'descriptor_schema': manifest.get('descriptor_schema') if manifest else '',
        'material_policy': manifest.get('material_policy') if manifest else 'flat_or_class_color_control',
        'fallback_material_count': sum(1 for item in manifest.get('materials', []) if item.get('evidence_source') == 'fallback_unknown') if manifest else 0,
        'mesh_bytes': obj_path.stat().st_size,
        'manifest_bytes': manifest_path.stat().st_size if manifest_path.exists() else 0,
        'mesh_path': str(obj_path).replace('\\', '/'),
        'manifest_path': str(manifest_path).replace('\\', '/') if manifest_path.exists() else '',
    }


def write_summary(path, rows):
    lines = ['# SPPA Material Ablation Benchmark', '']
    lines.append('Measured data. This benchmark isolates debug-path proxy construction/export and material-manifest overhead. It is not a user study, not a perceptual-discriminability test, and not a dense Unreal frame-time benchmark.')
    lines.append('All build, export, and manifest timings are repeated per class/method; the table reports medians across the six class-level medians, with P95 shown the same way.')
    lines.append('')
    lines.append('| Method | n classes | reps/class | build p50 ms | build p95 ms | export p50 ms | export p95 ms | manifest p50 ms | manifest p95 ms | materials | triangles |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for method in METHODS:
        subset = [row for row in rows if row['method'] == method]
        lines.append(
            f"| {method} | {len(subset)} | {int(statistics.median(row['reps'] for row in subset))} | "
            f"{statistics.median(row['p50_build_ms'] for row in subset):.4f} | "
            f"{statistics.median(row['p95_build_ms'] for row in subset):.4f} | "
            f"{statistics.median(row['p50_export_ms'] for row in subset):.4f} | "
            f"{statistics.median(row['p95_export_ms'] for row in subset):.4f} | "
            f"{statistics.median(row['p50_manifest_ms'] for row in subset):.4f} | "
            f"{statistics.median(row['p95_manifest_ms'] for row in subset):.4f} | "
            f"{min(row['material_count'] for row in subset)}-{max(row['material_count'] for row in subset)} | "
            f"{min(row['triangles'] for row in subset)}-{max(row['triangles'] for row in subset)} |"
        )
    lines.append('')
    lines.append('Not measured: Unreal frame time, draw calls, material-instance cost, dense-scene scaling, and user recognition/workload.')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='experiments/sppa_material_ablation/latest')
    parser.add_argument('--generator', default=str(ROOT / 'XYT-xabi-yolo-telemetry' / 'xyt_generate_3d.py'))
    parser.add_argument('--reps', type=int, default=50)
    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    module = load_generator(Path(args.generator))
    rows = []
    for label, dims in TARGET_DIMS_M.items():
        for method in METHODS:
            rows.append(measure(module, out_dir, label, dims, method, args.reps))
    write_csv(out_dir / 'material_ablation_metrics.csv', rows)
    write_summary(out_dir / 'material_ablation_summary.md', rows)
    print(out_dir / 'material_ablation_metrics.csv')
    print(out_dir / 'material_ablation_summary.md')


if __name__ == '__main__':
    main()
