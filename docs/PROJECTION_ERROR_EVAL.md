# Projection Error Evaluation (Zero-Trust)

This document evaluates the **pixel -> ground** projection used by Vision:
* Implementation: `pipeline/vision_system.py` (`GeoProjector.pixel_to_gps`)
* Evaluation tool: `tools/eval_projection_error.py`

Important:
* This does **not** query Unreal ground-truth object positions.
* This is a **controlled geometric evaluation** that measures projection accuracy and sensitivity.

## Method

For each sample:
1. Pick a ground point (north/east offset from the drone) within `max_range_m` and visible in the image.
2. Forward-project it to a pixel `(u,v)` using the **true** camera model (`true_vfov_deg`, `true_mount_*`).
3. Add configurable noise:
   * Pixel jitter `px_sigma` (proxy for bbox jitter at the bottom of the detection)
   * Telemetry noise (`yaw/pitch/roll_sigma`, `alt_sigma`)
4. Run `GeoProjector.pixel_to_gps()` with the **estimated** camera model (`vfov_deg`, `mount_*`) and noisy telemetry.
5. Compare predicted `(lat,lon,dist)` to the known ground-truth point.

Metrics:
* `pos_err` (m): horizontal position error on the ground (meters)
* `dist_err` (m): `abs(pred_dist - true_horizontal_dist)`

## Runs (2026-02-14)

All runs below used:
* `image=640x640`, `vfov=45deg`, `mount_pitch=-30deg`, `alt_agl=30m`
* sampled points with `min_range=5m`, `max_range=75m`, `max_east=40m`
* `samples=20000`

### Perfect Calibration, No Telemetry Noise

Command:
```powershell
python tools\eval_projection_error.py --samples 20000 `
  --yaw-sigma-deg 0 --pitch-sigma-deg 0 --roll-sigma-deg 0 --alt-sigma-m 0 `
  --px-sigmas 0,2,5,10,20 --max-range-m 75 --min-range-m 5 --max-east-m 40
```

Output:
```text
scenario  invalid%  pos_p50  pos_p95  pos_p99  pos_max  dist_p50  dist_p95  dist_p99  dist_max
px0          0.00     0.00     0.00     0.00     0.08      0.00      0.00      0.00      0.05
px2          0.00     0.25     0.74     1.02     1.76      0.19      0.71      1.01      1.69
px5          0.00     0.62     1.81     2.54     4.28      0.47      1.75      2.49      4.11
px10         0.00     1.23     3.54     4.92     8.19      0.93      3.42      4.84      7.83
px20         0.00     2.42     6.78     9.25    17.65      1.82      6.49      9.07     17.07
```

### Perfect Calibration, Mild Telemetry Noise (0.5deg, 0.5m)

Command:
```powershell
python tools\eval_projection_error.py --samples 20000 `
  --yaw-sigma-deg 0.5 --pitch-sigma-deg 0.5 --roll-sigma-deg 0.5 --alt-sigma-m 0.5 `
  --px-sigmas 0,2,5,10,20 --max-range-m 75 --min-range-m 5 --max-east-m 40
```

Output:
```text
scenario  invalid%  pos_p50  pos_p95  pos_p99  pos_max  dist_p50  dist_p95  dist_p99  dist_max
px0          0.00     1.03     3.10     4.25     7.45      0.86      3.04      4.19      7.40
px2          0.00     1.06     3.16     4.34     8.14      0.88      3.09      4.27      8.08
px5          0.00     1.20     3.56     4.80     8.30      0.97      3.46      4.75      8.30
px10         0.00     1.60     4.64     6.33    10.37      1.26      4.51      6.18     10.15
px20         0.00     2.61     7.35    10.06    15.81      2.00      7.06      9.79     15.70
```

### Miscalibration Example: Mount Pitch Off By +2 Deg

Ground-truth mount pitch is `-30deg`, but the estimator uses `-28deg`.

Command:
```powershell
python tools\eval_projection_error.py --samples 20000 `
  --yaw-sigma-deg 0 --pitch-sigma-deg 0 --roll-sigma-deg 0 --alt-sigma-m 0 `
  --px-sigmas 0,5 --max-range-m 75 --min-range-m 5 --max-east-m 40 `
  --mount-pitch-deg -28 --true-mount-pitch-deg -30
```

Output:
```text
scenario  invalid%  pos_p50  pos_p95  pos_p99  pos_max  dist_p50  dist_p95  dist_p99  dist_max
px0          0.00     3.95     6.50     6.82     6.98      3.94      6.49      6.82      6.98
px5          0.00     3.84     7.01     8.04     9.97      3.81      6.99      8.02      9.97
```

### Miscalibration Example: VFOV Off By +5 Deg

Ground-truth VFOV is `45deg`, but the estimator uses `50deg`.

Command:
```powershell
python tools\eval_projection_error.py --samples 20000 `
  --yaw-sigma-deg 0 --pitch-sigma-deg 0 --roll-sigma-deg 0 --alt-sigma-m 0 `
  --px-sigmas 0 --max-range-m 75 --min-range-m 5 --max-east-m 40 `
  --vfov-deg 50 --true-vfov-deg 45
```

Output:
```text
scenario  invalid%  pos_p50  pos_p95  pos_p99  pos_max  dist_p50  dist_p95  dist_p99  dist_max
px0          0.00     2.04     3.86     4.43     4.89      1.28      3.13      3.45      3.71
```

## Takeaways

* With perfect calibration and good telemetry, the math itself is accurate; error is dominated by bbox jitter.
* Small systematic calibration errors (mount pitch, VFOV) can dominate:
  * `+2deg` mount pitch error caused ~`4m` median position error (at `30m` AGL).
* For real-world robustness, the most important next steps are:
  * correct ROI (only the camera viewport, not the whole screen)
  * calibrate VFOV and mount pitch (or estimate them)
  * incorporate a terrain model (not a single flat plane)

