from __future__ import annotations

import argparse
import csv
import importlib.util
import math
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

METHODS = ('box', 'ellipsoid', 'capsule_proxy', 'billboard', 'sppa_fixed', 'sppa_global_scaled', 'sppa_parametric')

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

def triangle_count(mesh):
    return sum(max(0, len(face[0]) - 2) for face in mesh.faces)

def align_ground(mesh):
    if not mesh.vertices:
        return mesh
    xmin, xmax, ymin, ymax, zmin, zmax = mesh_bounds(mesh)
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    mesh.vertices = [(x - cx, y - cy, z - zmin) for x, y, z in mesh.vertices]
    return mesh

def scale_to_dims(mesh, dims):
    align_ground(mesh)
    bounds = mesh_bounds(mesh)
    sx, sy, sz = extents_from_bounds(bounds)
    tx, ty, tz = dims
    fx = tx / sx if sx > 1e-9 else 1.0
    fy = ty / sy if sy > 1e-9 else 1.0
    fz = tz / sz if sz > 1e-9 else 1.0
    mesh.vertices = [(x * fx, y * fy, z * fz) for x, y, z in mesh.vertices]
    return align_ground(mesh)

def build_box(module, dims):
    m = module.Mesh()
    x, y, z = dims
    m.box((0, 0, z / 2.0), dims, 'gray')
    return m

def build_ellipsoid(module, dims):
    m = module.Mesh()
    x, y, z = dims
    m.sphere((0, 0, z / 2.0), (x / 2.0, y / 2.0, z / 2.0), 'gray', rings=6, segments=12)
    return m

def build_capsule_proxy(module, dims):
    m = module.Mesh()
    x, y, z = dims
    core = max(0.05, x - y)
    m.box((0, 0, z / 2.0), (core, y, z), 'gray')
    m.sphere((core / 2.0, 0, z / 2.0), (y / 2.0, y / 2.0, z / 2.0), 'gray', rings=5, segments=10)
    m.sphere((-core / 2.0, 0, z / 2.0), (y / 2.0, y / 2.0, z / 2.0), 'gray', rings=5, segments=10)
    return m

def build_billboard(module, dims):
    m = module.Mesh()
    x, y, z = dims
    verts = [(-0.01, -y/2, 0), (-0.01, y/2, 0), (-0.01, y/2, z), (-0.01, -y/2, z)]
    ids = [m.add_vertex(*v) for v in verts]
    m.add_face(ids, 'yellow')
    return m

def build_sppa_fixed(module, label, dims):
    m = module.Mesh()
    module.build_label(m, label)
    return align_ground(m)

def build_sppa_global_scaled(module, label, dims):
    m = build_sppa_fixed(module, label, dims)
    return scale_to_dims(m, dims)

def build_sppa_parametric(module, label, dims):
    m = module.Mesh()
    if hasattr(module, 'build_label_parametric'):
        module.build_label_parametric(m, label, {
            'length': dims[0],
            'width': dims[1],
            'height': dims[2],
        })
    else:
        module.build_label(m, label)
    return align_ground(m)

def build_mesh(module, method, label, dims):
    if method == 'box':
        return build_box(module, dims)
    if method == 'ellipsoid':
        return build_ellipsoid(module, dims)
    if method == 'capsule_proxy':
        return build_capsule_proxy(module, dims)
    if method == 'billboard':
        return build_billboard(module, dims)
    if method == 'sppa_fixed':
        return build_sppa_fixed(module, label, dims)
    if method == 'sppa_global_scaled':
        return build_sppa_global_scaled(module, label, dims)
    if method == 'sppa_parametric':
        return build_sppa_parametric(module, label, dims)
    raise KeyError(method)

def summarize(values):
    values = sorted(values)
    if not values:
        return {'p50_ms': 0.0, 'p95_ms': 0.0, 'max_ms': 0.0}
    p95_index = min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)
    return {
        'p50_ms': statistics.median(values) * 1000.0,
        'p95_ms': values[p95_index] * 1000.0,
        'max_ms': values[-1] * 1000.0,
    }

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

def measure_method(module, out_dir, label, dims, method, reps):
    times = []
    mesh = None
    for _ in range(reps):
        start = time.perf_counter()
        mesh = build_mesh(module, method, label, dims)
        times.append(time.perf_counter() - start)
    assert mesh is not None
    method_dir = out_dir / 'outputs' / method / label
    method_dir.mkdir(parents=True, exist_ok=True)
    obj_path = method_dir / f'{label}.obj'
    mtl_path = method_dir / f'{label}.mtl'
    export_start = time.perf_counter()
    module.write_mtl(str(mtl_path))
    module.write_obj(mesh, str(obj_path), mtl_path.name)
    export_ms = (time.perf_counter() - export_start) * 1000.0
    bx = mesh_bounds(mesh)
    ex, ey, ez = extents_from_bounds(bx)
    tx, ty, tz = dims
    target_volume = tx * ty * tz
    aabb_volume = ex * ey * ez
    row = {
        'label': label,
        'method': method,
        'reps': reps,
        'target_length_m': tx,
        'target_width_m': ty,
        'target_height_m': tz,
        'aabb_length_m': ex,
        'aabb_width_m': ey,
        'aabb_height_m': ez,
        'mean_dim_rel_error': (abs(ex-tx)/tx + abs(ey-ty)/ty + abs(ez-tz)/tz) / 3.0,
        'aabb_volume_ratio': aabb_volume / target_volume if target_volume > 0 else 0.0,
        'vertices': len(mesh.vertices),
        'faces': len(mesh.faces),
        'triangles': triangle_count(mesh),
        'mesh_bytes': obj_path.stat().st_size,
        'export_ms': export_ms,
        'mesh_path': str(obj_path).replace('\\', '/'),
    }
    row.update(summarize(times))
    return row

def write_summary(path, rows):
    by_method = {}
    for row in rows:
        by_method.setdefault(row['method'], []).append(row)
    lines = ['# Lightweight Baseline Benchmark', '']
    lines.append('Measured data. This is not a user study and not an Unreal frame-time benchmark.')
    lines.append('')
    lines.append('| Method | n classes | median build ms | p95 build ms | triangle range | mean dimension error |')
    lines.append('|---|---:|---:|---:|---:|---:|')
    for method, items in sorted(by_method.items()):
        med = statistics.median(item['p50_ms'] for item in items)
        p95 = statistics.median(item['p95_ms'] for item in items)
        tri_min = min(item['triangles'] for item in items)
        tri_max = max(item['triangles'] for item in items)
        err = statistics.mean(item['mean_dim_rel_error'] for item in items)
        lines.append(f'| {method} | {len(items)} | {med:.4f} | {p95:.4f} | {tri_min}-{tri_max} | {err:.4f} |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='experiments/sppa_lightweight_baselines/latest')
    parser.add_argument('--generator', default=str(ROOT / 'XYT-xabi-yolo-telemetry' / 'xyt_generate_3d.py'))
    parser.add_argument('--reps', type=int, default=50)
    args = parser.parse_args()
    out_dir = ROOT / args.output_dir if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    module = load_generator(Path(args.generator))
    rows = []
    for label, dims in TARGET_DIMS_M.items():
        for method in METHODS:
            rows.append(measure_method(module, out_dir, label, dims, method, args.reps))
    write_csv(out_dir / 'lightweight_baseline_metrics.csv', rows)
    write_summary(out_dir / 'lightweight_baseline_summary.md', rows)
    print('wrote ' + str(out_dir / 'lightweight_baseline_metrics.csv'))
    print('wrote ' + str(out_dir / 'lightweight_baseline_summary.md'))

if __name__ == '__main__':
    main()
