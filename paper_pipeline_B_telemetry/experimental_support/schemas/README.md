# Schemas

These schemas document the current Pipeline B runtime contract without changing
the Brain implementation.

## `post_obstacles.schema.json`

Recommended contract for `POST /api/obstacles`.

The current Brain accepts obstacle objects with:

- `source`
- `source_id` or `id`
- `type`
- `confidence`
- `distance`
- `lat` / `lon`
- `world_m` or `world_north_m` / `world_east_m` / `world_up_m`
- `yaw_deg` or compatible heading fields
- `bbox`

For the paper, `world_m` is important because Unreal prioritizes local world
coordinates when available. This lets us test the display contract without
claiming that calibrated camera-to-world georeferencing has already been
validated.

## `ui_data.schema.json`

Recommended contract for `GET /api/ui/data`.

The current Brain exposes:

- `telemetry`
- `home`
- `waypoints`
- `obstacles`
- `obstacle_tracks_count`
- `evasion`

Each obstacle should expose stable identifiers and display semantics:

- `entity_id`
- `object_id`
- `type` / `object_type`
- `confidence`
- `world_m` when available
- `track_age_s`
- `track_seen_count`
- `track_static`

## Forward-compatible fields

The schemas include `uncertainty` even if the current Brain ignores it. This is
intentional: it preserves the publication route without forcing a breaking code
change today. The field can later be implemented by Brain/Unreal when
`TBD-SAFETY` and `TBD-GEO` are resolved.
