# CHANGELOG — deviations from the pre-registration (`CLASS_MAPPING.md`)

**Label: external sanity check (exploratory, post-hoc).** All deviations were
made before the final analysis numbers were computed, and are recorded here.

1. **`school_bus` added to articulated_vehicle.** The pre-registration listed
   only `trailer_truck` + `bus`. LVIS `bus` candidates yielded too few
   QC-passing meshes, so one `school_bus` (same metric criterion: x = 8.8 m)
   was admitted as an equivalent class. Final: trailer_truck ×5, bus ×2,
   school_bus ×1.
2. **ModelNet40 `plant` cases kept despite sparse GT.** Their foliage is
   billboard geometry that the GT voxelizer covers only partially; they were
   retained (rather than replaced) to avoid selection bias, and the resulting
   downward IoU bias is documented in `README.md`.
3. **`horse-02` is a giraffe** (LVIS mislabel). Kept as an honest OOD case;
   flagged in the README and in `manifest.json`.
4. **GT voxelization convention v3.** `CLASS_MAPPING.md` specified surface
   splat + ray-parity fill. During revoxelization (`revoxelize_gt.py`) a
   1-iteration binary closing (3³, connectivity 1) was added to seal sub-cell
   leaks in open geometry. Justified and documented as a methodological
   finding, not silent tuning.
5. **Final n = 52 vs planned 49.** Per-family finals exceeded the plan
   (10/8/10/8/8/8) because more candidates passed QC than the minimum
   required; the extra cases were kept under the frozen selection seed
   (20260718).
6. **Environment additions**: `pip --user install objaverse==0.1.7
   fast-simplification rtree==1.4.1` (documented in README; the sealed
   package's locked environment was not modified).
7. **Script fixes after pre-registration, before final numbers**:
   `analyze.py` f-string brace bug and a duplicated `\midrule` were fixed;
   `make_qualitative.py` was written after `analyze.py` ran. Neither change
   affects the evaluation rows in `results/results.jsonl`.
