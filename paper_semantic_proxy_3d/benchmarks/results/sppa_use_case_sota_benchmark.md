# SPPA use-case SOTA benchmark

Operational score for UAV digital-twin **semantic runtime proxies**.
Not a photoreal image-to-3D leaderboard.

Virtues maximized: low triangles, millisecond build, role-labeled parts,
evidence-aware dims, update/fallback contract, lightness vs neural generators.

| Label | Mode | LOD | Tris | Parts | Build ms | vs neural tris | Speedup vs neural | Use-case score |
|---|---|---|---:|---:|---:|---:|---:|---:|
| biker | tag_only_prior_dims | balanced | 692 | 27 | 0.35 | 0.0308 | 2538.2 | 0.784 |
| biker | tag_plus_metric_dims | balanced | 692 | 27 | 0.24 | 0.0308 | 3743.2 | 0.834 |
| biker | tag_plus_metric_dims | ultra_light | 624 | 25 | 0.21 | 0.0278 | 4315.2 | 0.834 |
| biker | tag_plus_metric_dims | high | 940 | 23 | 0.31 | 0.0419 | 2936.6 | 0.834 |
| tower | tag_only_prior_dims | balanced | 396 | 17 | 0.14 | 0.0163 | 7083.9 | 0.784 |
| tower | tag_plus_metric_dims | balanced | 396 | 17 | 0.15 | 0.0163 | 7016.3 | 0.834 |
| tower | tag_plus_metric_dims | ultra_light | 396 | 17 | 0.14 | 0.0163 | 7573.5 | 0.834 |
| tower | tag_plus_metric_dims | high | 396 | 17 | 0.14 | 0.0163 | 7590.3 | 0.834 |
| tractor | tag_only_prior_dims | balanced | 576 | 28 | 0.19 | 0.0158 | 7090.3 | 0.784 |
| tractor | tag_plus_metric_dims | balanced | 576 | 28 | 0.18 | 0.0158 | 7466.8 | 0.834 |
| tractor | tag_plus_metric_dims | ultra_light | 464 | 24 | 0.15 | 0.0127 | 9000.0 | 0.834 |
| tractor | tag_plus_metric_dims | high | 836 | 20 | 0.23 | 0.0229 | 5902.9 | 0.834 |
| tractor_trailer | tag_only_prior_dims | balanced | 1076 | 49 | 0.34 | 0.0389 | 3482.3 | 0.784 |
| tractor_trailer | tag_plus_metric_dims | balanced | 1076 | 49 | 0.33 | 0.0389 | 3669.7 | 0.834 |
| tractor_trailer | tag_plus_metric_dims | ultra_light | 852 | 41 | 0.27 | 0.0308 | 4491.0 | 0.834 |
| tractor_trailer | tag_plus_metric_dims | high | 1576 | 33 | 0.47 | 0.057 | 2562.5 | 0.834 |

Best row by use-case score: **biker / tag_plus_metric_dims / balanced** (0.834).

Claim boundary: higher use-case score means better operational proxy under budget,
not higher mesh beauty than Trellis/Hunyuan/TripoSR.

