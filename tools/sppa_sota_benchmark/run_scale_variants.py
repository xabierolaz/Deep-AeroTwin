from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from run_lightweight_baselines import ROOT, build_mesh, extents_from_bounds, load_generator, mesh_bounds, triangle_count, write_csv

VARIANTS = [
    ('car_compact', 'car', (3.60, 1.75, 1.50)),
    ('car_long', 'car', (5.10, 1.90, 1.70)),
    ('truck_short', 'truck', (5.20, 2.30, 2.70)),
    ('truck_long', 'truck', (8.20, 2.55, 3.05)),
    ('tractor_small', 'tractor', (3.10, 1.80, 2.10)),
    ('tractor_large', 'tractor', (4.80, 2.35, 2.80)),
    ('cow_small', 'cow', (1.80, 0.75, 1.25)),
    ('cow_large', 'cow', (3.00, 1.10, 1.85)),
    ('tree_short', 'tree', (1.40, 1.35, 2.10)),
    ('tree_tall', 'tree', (2.20, 1.85, 4.80)),
    ('biker_child', 'biker', (1.35, 0.52, 1.55)),
    ('biker_adult', 'biker', (1.95, 0.70, 2.25)),
]

METHODS = ('sppa_fixed', 'sppa_global_scaled', 'sppa_parametric', 'box')

def summarize(values):
    values = sorted(values)
    p95_index = min(len(values) - 1, int(0.95 * len(values)))
    return statistics.median(values) * 1000.0, values[p95_index] * 1000.0

def measure(module, out_dir, display_label, base_label, dims, method, reps):
    times = []
    mesh = None
    for _ in range(reps):
        start = time.perf_counter()
        mesh = build_mesh(module, method, base_label, dims)
        times.append(time.perf_counter() - start)
    method_dir = out_dir / 'outputs_scale' / method / display_label
    method_dir.mkdir(parents=True, exist_ok=True)
    obj_path = method_dir / f'{display_label}.obj'
    mtl_path = method_dir / f'{display_label}.mtl'
    module.write_mtl(str(mtl_path))
    module.write_obj(mesh, str(obj_path), mtl_path.name)
    ex, ey, ez = extents_from_bounds(mesh_bounds(mesh))
    tx, ty, tz = dims
    p50, p95 = summarize(times)
    return {
        'variant': display_label,
        'base_label': base_label,
        'method': method,
        'target_length_m': tx,
        'target_width_m': ty,
        'target_height_m': tz,
        'aabb_length_m': ex,
        'aabb_width_m': ey,
        'aabb_height_m': ez,
        'mean_dim_rel_error': (abs(ex-tx)/tx + abs(ey-ty)/ty + abs(ez-tz)/tz) / 3.0,
        'p50_build_ms': p50,
        'p95_build_ms': p95,
        'triangles': triangle_count(mesh),
        'mesh_path': str(obj_path).replace('\\', '/'),
    }

def write_summary(path, rows):
    lines = ['# SPPA Scale Variant Benchmark', '']
    lines.append('Synthetic dimension variants. `sppa_global_scaled` is the trivial baseline that scales every part. `sppa_parametric` uses evidence-calibrated part layout for supported vehicle archetypes. This is not silhouette or user-recognition evidence.')
    lines.append('')
    lines.append('## All Archetypes')
    lines.append('')
    lines.append('| Method | n variants | median dim error | median build ms | triangle range |')
    lines.append('|---|---:|---:|---:|---:|')
    for method in METHODS:
        items = [r for r in rows if r['method'] == method]
        err = statistics.median(r['mean_dim_rel_error'] for r in items)
        build = statistics.median(r['p50_build_ms'] for r in items)
        tri_min = min(r['triangles'] for r in items)
        tri_max = max(r['triangles'] for r in items)
        lines.append(f'| {method} | {len(items)} | {err:.4f} | {build:.4f} | {tri_min}-{tri_max} |')
    lines.append('')
    lines.append('## Supported Vehicle Archetypes Only')
    lines.append('')
    lines.append('| Method | n variants | median dim error | median build ms | triangle range |')
    lines.append('|---|---:|---:|---:|---:|')
    vehicle_rows = [r for r in rows if r['base_label'] in ('car', 'truck')]
    for method in METHODS:
        items = [r for r in vehicle_rows if r['method'] == method]
        err = statistics.median(r['mean_dim_rel_error'] for r in items)
        build = statistics.median(r['p50_build_ms'] for r in items)
        tri_min = min(r['triangles'] for r in items)
        tri_max = max(r['triangles'] for r in items)
        lines.append(f'| {method} | {len(items)} | {err:.4f} | {build:.4f} | {tri_min}-{tri_max} |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='experiments/sppa_scale_variants/latest')
    parser.add_argument('--generator', default=str(ROOT / 'XYT-xabi-yolo-telemetry' / 'xyt_generate_3d.py'))
    parser.add_argument('--reps', type=int, default=50)
    args = parser.parse_args()
    out_dir = ROOT / args.output_dir if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    module = load_generator(Path(args.generator))
    rows = []
    for display_label, base_label, dims in VARIANTS:
        for method in METHODS:
            rows.append(measure(module, out_dir, display_label, base_label, dims, method, args.reps))
    write_csv(out_dir / 'scale_adaptation_metrics.csv', rows)
    write_summary(out_dir / 'scale_adaptation_summary.md', rows)
    print('wrote ' + str(out_dir / 'scale_adaptation_metrics.csv'))
    print('wrote ' + str(out_dir / 'scale_adaptation_summary.md'))

if __name__ == '__main__':
    main()
