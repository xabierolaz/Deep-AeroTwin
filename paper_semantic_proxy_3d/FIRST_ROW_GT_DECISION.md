# First-Row Ground-Truth Decision

Generated during the SPPA submission audit on 2026-07-03.

## Decision

Do not label the first row of the comparative figure as ground truth in the current paper.

The six-case visual grid currently uses synthetic proxy crops. The current real probes (biker, tower, tractor, and tractor with trailer) use user-supplied images with manually reviewed 2D bounding boxes. Those assets are useful input evidence for detector/crop provenance, but they are not 3D ground truth.

## Why A Detector Image Is Not Enough

A detector crop can be the common input row for all image-to-3D methods. It becomes ground truth only if the manifest also provides reference evidence, for example:

- reviewed 2D box plus segmentation mask or oriented footprint;
- camera/scale calibration sufficient for metric comparison;
- reference mesh, CAD asset, LiDAR/photogrammetry reconstruction, or structured human-preference task;
- detector output, reviewed semantic tag, and GT/reference fields stored as separate columns.

## Current Evidence

- Six proxy-grid items: 6 synthetic proxy crops, 0 detector crops, 0 GT items.
- Real probes: 4 readable images, 4 manual 2D boxes, 0 masks, 0 reference meshes, 0 3D GT items.
- YOLO target-class evidence: no valid repository/COCO target hit for biker, tower, tractor, or tractor_trailer under the recorded probes.

## Paper Policy

Use `Proxy input (not GT)` for the current six-case visual grid.

Use detector crops as a future first row only when every method receives the same frozen crops and the manifest separates detector output from reviewed tags.

Use `Ground truth` only after every displayed item has explicit mask/footprint/reference-mesh/preference evidence and the metric table consumes that same manifest.
