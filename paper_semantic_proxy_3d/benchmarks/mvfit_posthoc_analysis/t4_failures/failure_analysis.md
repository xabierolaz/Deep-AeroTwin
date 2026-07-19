# T4 — Failure analysis and local-search convergence

**exploratory post-hoc analysis (not confirmatory)**

Failure = voxel IoU < 0.25, method sppa_mvfit, condition clean (n = 240).

## (a) Failure rate by family × stratum

| Family | Stratum | n | Failures | Rate | Case ids |
|---|---|---|---|---|---|
| compact_vehicle | csg_id | 20 | 0 | 0.000 | — |
| compact_vehicle | implicit_ood | 20 | 0 | 0.000 | — |
| articulated_vehicle | csg_id | 20 | 0 | 0.000 | — |
| articulated_vehicle | implicit_ood | 20 | 0 | 0.000 | — |
| quadruped | csg_id | 20 | 0 | 0.000 | — |
| quadruped | implicit_ood | 20 | 0 | 0.000 | — |
| branching_vertical | csg_id | 20 | 0 | 0.000 | — |
| branching_vertical | implicit_ood | 20 | 0 | 0.000 | — |
| lattice_tower | csg_id | 20 | 5 | 0.250 | test-csg_id-lattice_tower-017, test-csg_id-lattice_tower-007, test-csg_id-lattice_tower-011, test-csg_id-lattice_tower-018, test-csg_id-lattice_tower-008 |
| lattice_tower | implicit_ood | 20 | 0 | 0.000 | — |
| rider_cycle | csg_id | 20 | 0 | 0.000 | — |
| rider_cycle | implicit_ood | 20 | 0 | 0.000 | — |

## (a2) Ten worst cases per family (sppa_mvfit, clean)

### compact_vehicle

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-csg_id-compact_vehicle-018 | csg_id | 0.5146 | 0.0123 | 0.8597 |
| 2 | test-csg_id-compact_vehicle-014 | csg_id | 0.5545 | 0.0122 | 0.4855 |
| 3 | test-csg_id-compact_vehicle-009 | csg_id | 0.5771 | 0.0108 | 0.3774 |
| 4 | test-csg_id-compact_vehicle-006 | csg_id | 0.6142 | 0.0106 | 0.2323 |
| 5 | test-csg_id-compact_vehicle-007 | csg_id | 0.6213 | 0.0087 | 0.5245 |
| 6 | test-csg_id-compact_vehicle-000 | csg_id | 0.6407 | 0.0094 | 0.0691 |
| 7 | test-csg_id-compact_vehicle-015 | csg_id | 0.6472 | 0.0083 | 0.1011 |
| 8 | test-csg_id-compact_vehicle-012 | csg_id | 0.6573 | 0.0084 | 0.1351 |
| 9 | test-csg_id-compact_vehicle-004 | csg_id | 0.6836 | 0.0078 | 0.1528 |
| 10 | test-implicit_ood-compact_vehicle-018 | implicit_ood | 0.6872 | 0.0080 | 0.3498 |

### articulated_vehicle

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-csg_id-articulated_vehicle-017 | csg_id | 0.4475 | 0.0207 | 0.7972 |
| 2 | test-csg_id-articulated_vehicle-006 | csg_id | 0.4491 | 0.0186 | 0.6692 |
| 3 | test-csg_id-articulated_vehicle-001 | csg_id | 0.4574 | 0.0173 | 0.6743 |
| 4 | test-csg_id-articulated_vehicle-010 | csg_id | 0.4711 | 0.0180 | 0.7965 |
| 5 | test-csg_id-articulated_vehicle-012 | csg_id | 0.4712 | 0.0181 | 0.9393 |
| 6 | test-csg_id-articulated_vehicle-003 | csg_id | 0.4876 | 0.0190 | 0.7560 |
| 7 | test-csg_id-articulated_vehicle-019 | csg_id | 0.4918 | 0.0159 | 0.5404 |
| 8 | test-csg_id-articulated_vehicle-005 | csg_id | 0.4989 | 0.0167 | 0.7555 |
| 9 | test-csg_id-articulated_vehicle-004 | csg_id | 0.5020 | 0.0187 | 0.8475 |
| 10 | test-csg_id-articulated_vehicle-009 | csg_id | 0.5146 | 0.0174 | 0.6742 |

### quadruped

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-implicit_ood-quadruped-002 | implicit_ood | 0.5137 | 0.0076 | 0.5913 |
| 2 | test-csg_id-quadruped-015 | csg_id | 0.5224 | 0.0076 | 0.6347 |
| 3 | test-csg_id-quadruped-011 | csg_id | 0.5420 | 0.0080 | 0.7156 |
| 4 | test-implicit_ood-quadruped-009 | implicit_ood | 0.5451 | 0.0074 | 0.7115 |
| 5 | test-csg_id-quadruped-008 | csg_id | 0.5461 | 0.0090 | 0.6492 |
| 6 | test-csg_id-quadruped-001 | csg_id | 0.5491 | 0.0062 | 0.7892 |
| 7 | test-implicit_ood-quadruped-003 | implicit_ood | 0.5678 | 0.0057 | 0.4832 |
| 8 | test-csg_id-quadruped-014 | csg_id | 0.5679 | 0.0087 | 0.7155 |
| 9 | test-implicit_ood-quadruped-000 | implicit_ood | 0.5685 | 0.0076 | 0.5965 |
| 10 | test-csg_id-quadruped-013 | csg_id | 0.5887 | 0.0062 | 0.5311 |

### branching_vertical

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-csg_id-branching_vertical-010 | csg_id | 0.4374 | 0.0125 | 0.1913 |
| 2 | test-csg_id-branching_vertical-001 | csg_id | 0.4397 | 0.0120 | 0.7655 |
| 3 | test-csg_id-branching_vertical-009 | csg_id | 0.4532 | 0.0135 | 0.3094 |
| 4 | test-implicit_ood-branching_vertical-001 | implicit_ood | 0.4564 | 0.0138 | 0.5884 |
| 5 | test-implicit_ood-branching_vertical-008 | implicit_ood | 0.4798 | 0.0131 | 0.4795 |
| 6 | test-implicit_ood-branching_vertical-013 | implicit_ood | 0.4826 | 0.0128 | 0.3866 |
| 7 | test-implicit_ood-branching_vertical-017 | implicit_ood | 0.4830 | 0.0115 | 0.2036 |
| 8 | test-implicit_ood-branching_vertical-012 | implicit_ood | 0.4835 | 0.0131 | 0.1176 |
| 9 | test-implicit_ood-branching_vertical-016 | implicit_ood | 0.4855 | 0.0133 | 0.3280 |
| 10 | test-implicit_ood-branching_vertical-018 | implicit_ood | 0.4889 | 0.0118 | 0.3128 |

### lattice_tower

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-csg_id-lattice_tower-017 | csg_id | 0.1473 | 0.0097 | 1.3636 |
| 2 | test-csg_id-lattice_tower-007 | csg_id | 0.1481 | 0.0100 | 1.4000 |
| 3 | test-csg_id-lattice_tower-011 | csg_id | 0.1726 | 0.0091 | 1.0765 |
| 4 | test-csg_id-lattice_tower-018 | csg_id | 0.1822 | 0.0117 | 1.2436 |
| 5 | test-csg_id-lattice_tower-008 | csg_id | 0.2391 | 0.0083 | 0.2279 |
| 6 | test-implicit_ood-lattice_tower-015 | implicit_ood | 0.2513 | 0.0063 | 0.3790 |
| 7 | test-csg_id-lattice_tower-000 | csg_id | 0.2565 | 0.0068 | 0.4492 |
| 8 | test-implicit_ood-lattice_tower-013 | implicit_ood | 0.2566 | 0.0067 | 0.6101 |
| 9 | test-csg_id-lattice_tower-005 | csg_id | 0.2611 | 0.0086 | 0.0047 |
| 10 | test-implicit_ood-lattice_tower-009 | implicit_ood | 0.2652 | 0.0078 | 0.8558 |

### rider_cycle

| # | case_id | stratum | voxel IoU | Chamfer | vol. err |
|---|---|---|---|---|---|
| 1 | test-csg_id-rider_cycle-009 | csg_id | 0.3269 | 0.0095 | 1.2128 |
| 2 | test-csg_id-rider_cycle-007 | csg_id | 0.3488 | 0.0086 | 1.1275 |
| 3 | test-csg_id-rider_cycle-017 | csg_id | 0.3618 | 0.0086 | 0.9127 |
| 4 | test-implicit_ood-rider_cycle-017 | implicit_ood | 0.3952 | 0.0053 | 0.5860 |
| 5 | test-implicit_ood-rider_cycle-002 | implicit_ood | 0.4116 | 0.0057 | 0.6768 |
| 6 | test-implicit_ood-rider_cycle-004 | implicit_ood | 0.4204 | 0.0051 | 0.9450 |
| 7 | test-implicit_ood-rider_cycle-000 | implicit_ood | 0.4244 | 0.0043 | 0.9796 |
| 8 | test-implicit_ood-rider_cycle-019 | implicit_ood | 0.4306 | 0.0046 | 0.8476 |
| 9 | test-implicit_ood-rider_cycle-018 | implicit_ood | 0.4425 | 0.0049 | 0.6538 |
| 10 | test-implicit_ood-rider_cycle-008 | implicit_ood | 0.4500 | 0.0043 | 0.6711 |

## (b) lattice_tower failure hypothesis: sub-voxel structure

Voxel cells at 64³: 0.150 (x) × 0.100 (y) × 0.100 (z) world units; cell volume 0.0015. Components thinner than a cell can be missed by cell-centre sampling.

### test-csg_id-lattice_tower-007 (csg_id, 9 components, GT 520 voxels)

| kind | min dim (world) | min dim / cell | voxels hit @64³ | expected cells | capture ratio |
|---|---|---|---|---|---|
| box | 0.203 | 2.03 | 188 | 118.4 | 1.587 |
| cylinder | 0.127 | 1.27 | 45 | 38.4 | 1.172 |
| cylinder | 0.127 | 1.27 | 45 | 38.4 | 1.172 |
| cylinder | 0.127 | 1.27 | 45 | 38.4 | 1.172 |
| cylinder | 0.127 | 1.27 | 45 | 38.4 | 1.172 |
| box | 0.095 | 0.95 | 60 | 64.1 | 0.936 |
| box | 0.095 | 0.95 | 48 | 49.5 | 0.970 |
| box | 0.095 | 0.95 | 36 | 30.6 | 1.176 |
| box | 0.095 | 0.95 | 24 | 27.0 | 0.889 |

### test-csg_id-lattice_tower-008 (csg_id, 9 components, GT 1088 voxels)

| kind | min dim (world) | min dim / cell | voxels hit @64³ | expected cells | capture ratio |
|---|---|---|---|---|---|
| box | 0.373 | 3.73 | 312 | 369.1 | 0.845 |
| cylinder | 0.233 | 2.33 | 114 | 109.7 | 1.039 |
| cylinder | 0.233 | 2.33 | 114 | 109.7 | 1.039 |
| cylinder | 0.233 | 2.33 | 114 | 109.7 | 1.039 |
| cylinder | 0.233 | 2.33 | 114 | 109.7 | 1.039 |
| box | 0.175 | 1.75 | 120 | 127.0 | 0.945 |
| box | 0.175 | 1.75 | 120 | 97.1 | 1.236 |
| box | 0.175 | 1.75 | 96 | 70.0 | 1.371 |
| box | 0.175 | 1.75 | 48 | 55.1 | 0.871 |

### test-csg_id-lattice_tower-011 (csg_id, 9 components, GT 680 voxels)

| kind | min dim (world) | min dim / cell | voxels hit @64³ | expected cells | capture ratio |
|---|---|---|---|---|---|
| box | 0.227 | 2.27 | 216 | 181.8 | 1.188 |
| cylinder | 0.142 | 1.42 | 52 | 53.2 | 0.977 |
| cylinder | 0.142 | 1.42 | 52 | 53.2 | 0.977 |
| cylinder | 0.142 | 1.42 | 52 | 53.2 | 0.977 |
| cylinder | 0.142 | 1.42 | 52 | 53.2 | 0.977 |
| box | 0.106 | 1.06 | 96 | 95.6 | 1.004 |
| box | 0.106 | 1.06 | 80 | 79.5 | 1.006 |
| box | 0.106 | 1.06 | 48 | 59.8 | 0.803 |
| box | 0.106 | 1.06 | 48 | 44.9 | 1.070 |

### All methods on the failing lattice_tower cases (clean voxel IoU)

| case_id | SPPA-MVFit | Generic-MVFit | SPPA text-only | Visual hull | Axis-aligned box | Ellipsoid | Capsule | Billboard |
|---|---|---|---|---|---|---|---|---|
| test-csg_id-lattice_tower-007 | 0.148 | 0.099 | 0.165 | 0.209 | 0.087 | 0.106 | 0.100 | 0.144 |
| test-csg_id-lattice_tower-008 | 0.239 | 0.184 | 0.167 | 0.431 | 0.190 | 0.183 | 0.177 | 0.135 |
| test-csg_id-lattice_tower-011 | 0.173 | 0.098 | 0.114 | 0.210 | 0.085 | 0.092 | 0.089 | 0.146 |
| test-csg_id-lattice_tower-017 | 0.147 | 0.109 | 0.163 | 0.247 | 0.076 | 0.101 | 0.091 | 0.136 |
| test-csg_id-lattice_tower-018 | 0.182 | 0.090 | 0.240 | 0.182 | 0.083 | 0.090 | 0.086 | 0.135 |

**Interpretation (b).** The failing lattice_tower actors are built from
legs and ring plates whose thickness (0.09–0.23 world units) is at or below
the voxel cell size (0.10–0.15). The 512³-reference capture ratios are close
to 1.0, so the components do NOT vanish at 64³ — but they are only 1–2 voxels
thick, the whole GT occupies ~500–1100 voxels (0.2–0.4 % of the grid), and
the IoU denominator is tiny. For 1-voxel-thick structures a one-cell
misalignment destroys overlap, so voxel IoU is inherently unstable at this
resolution; the failure is a sub-voxel / thin-shell resolution effect, not a
graph-prior miss (the SPPA lattice_tower graph has the right topology).

## (c) Local-search convergence (clean, from sealed metadata.trace)

### sppa_mvfit (n = 240)

- Cases with improvement in the last sweep (step fraction 0.05): 213/240 = 0.887
- Cases with final θ on a bound: 0/240 = 0.000
- Cases where the initial θ was already the best: 1/240 = 0.004
- Mean objective: init 0.3039 → final 0.2357 (mean improvement 0.0682, median 0.0541)

### generic_mvfit (n = 240)

- Cases with improvement in the last sweep (step fraction 0.05): 221/240 = 0.921
- Cases with final θ on a bound: 139/240 = 0.579
- Cases where the initial θ was already the best: 0/240 = 0.000
- Mean objective: init 0.4166 → final 0.3478 (mean improvement 0.0688, median 0.0616)
