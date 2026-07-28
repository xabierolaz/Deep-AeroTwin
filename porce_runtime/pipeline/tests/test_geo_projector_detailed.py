import sys
from pathlib import Path

import pytest


PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from geo_projector import GeoProjector  # noqa: E402


BASE_ARGS = {
    "image_height": 720,
    "image_width": 1280,
    "drone_lat": 42.2297,
    "drone_lon": -1.2351,
    "drone_yaw_deg": 17.0,
    "drone_pitch_deg": 0.0,
    "drone_roll_deg": 0.0,
    "alt_agl_m": 80.0,
    "camera_vfov_deg": 60.0,
    "mount_roll_deg": 0.0,
    "mount_pitch_deg": -45.0,
    "mount_yaw_deg": 0.0,
}


def test_legacy_tuple_wrapper_matches_detailed_projection():
    detailed = GeoProjector.pixel_to_gps_detailed(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=500.0,
    )
    wrapped = GeoProjector.pixel_to_gps(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=500.0,
    )

    assert detailed is not None
    assert wrapped == pytest.approx(
        (detailed["lat"], detailed["lon"], detailed["distance_m"])
    )
    assert detailed["range_clamped"] is False
    assert detailed["monocular_height_allowed"] is True


def test_wrapper_and_detailed_projection_reject_same_out_of_range_ray():
    detailed = GeoProjector.pixel_to_gps_detailed(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=20.0,
        clamp_to_max_range=False,
    )
    wrapped = GeoProjector.pixel_to_gps(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=20.0,
        clamp_to_max_range=False,
    )

    assert detailed is None
    assert wrapped is None


def test_clamped_projection_preserves_tuple_compatibility_and_degradation_flag():
    detailed = GeoProjector.pixel_to_gps_detailed(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=20.0,
        clamp_to_max_range=True,
    )
    wrapped = GeoProjector.pixel_to_gps(
        360.0,
        640.0,
        **BASE_ARGS,
        max_range_m=20.0,
        clamp_to_max_range=True,
    )

    assert detailed is not None
    assert detailed["distance_m"] == pytest.approx(20.0)
    assert detailed["range_clamped"] is True
    assert detailed["monocular_height_allowed"] is False
    assert wrapped == pytest.approx(
        (detailed["lat"], detailed["lon"], detailed["distance_m"])
    )


def test_wrapper_and_detailed_projection_reject_invalid_geometry():
    invalid_args = dict(BASE_ARGS)
    invalid_args["alt_agl_m"] = 0.0

    assert GeoProjector.pixel_to_gps_detailed(
        360.0,
        640.0,
        **invalid_args,
        max_range_m=500.0,
    ) is None
    assert GeoProjector.pixel_to_gps(
        360.0,
        640.0,
        **invalid_args,
        max_range_m=500.0,
    ) is None
