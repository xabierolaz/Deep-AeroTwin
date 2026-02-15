import math
import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from geo_projector import GeoProjector


class TestGeoProjector(unittest.TestCase):
    def test_center_pixel_mount_pitch_minus_30(self):
        # Level drone, camera pitched 30deg down, center pixel should hit ground at ~alt/tan(30deg).
        H = 640
        W = 640
        alt_agl = 10.0
        vfov = 45.0
        mount_pitch = -30.0

        out = GeoProjector.pixel_to_gps(
            H / 2,
            W / 2,
            image_height=H,
            image_width=W,
            drone_lat=42.0,
            drone_lon=-1.0,
            drone_yaw_deg=0.0,
            drone_pitch_deg=0.0,
            drone_roll_deg=0.0,
            alt_agl_m=alt_agl,
            camera_vfov_deg=vfov,
            mount_roll_deg=0.0,
            mount_pitch_deg=mount_pitch,
            mount_yaw_deg=0.0,
            max_range_m=1000.0,
        )
        self.assertIsNotNone(out)
        lat, lon, dist_h = out  # noqa: F841
        expected = alt_agl / math.tan(math.radians(30.0))
        self.assertLess(abs(dist_h - expected), 0.75)

    def test_no_intersection_when_camera_level_and_pixel_looks_up(self):
        # If camera is level (mount_pitch=0) and we look towards the top of the image,
        # the ray can point above the horizon => no ground intersection.
        H = 640
        W = 640
        out = GeoProjector.pixel_to_gps(
            0.0,
            W / 2,
            image_height=H,
            image_width=W,
            drone_lat=42.0,
            drone_lon=-1.0,
            drone_yaw_deg=0.0,
            drone_pitch_deg=0.0,
            drone_roll_deg=0.0,
            alt_agl_m=10.0,
            camera_vfov_deg=45.0,
            mount_roll_deg=0.0,
            mount_pitch_deg=0.0,
            mount_yaw_deg=0.0,
            max_range_m=1000.0,
        )
        self.assertIsNone(out)

    def test_distance_monotonic_in_y(self):
        H = 640
        W = 640
        out_far = GeoProjector.pixel_to_gps(
            H * 0.55,
            W / 2,
            image_height=H,
            image_width=W,
            drone_lat=42.0,
            drone_lon=-1.0,
            drone_yaw_deg=0.0,
            drone_pitch_deg=0.0,
            drone_roll_deg=0.0,
            alt_agl_m=10.0,
            camera_vfov_deg=45.0,
            mount_roll_deg=0.0,
            mount_pitch_deg=-30.0,
            mount_yaw_deg=0.0,
            max_range_m=1000.0,
        )
        out_near = GeoProjector.pixel_to_gps(
            H * 0.90,
            W / 2,
            image_height=H,
            image_width=W,
            drone_lat=42.0,
            drone_lon=-1.0,
            drone_yaw_deg=0.0,
            drone_pitch_deg=0.0,
            drone_roll_deg=0.0,
            alt_agl_m=10.0,
            camera_vfov_deg=45.0,
            mount_roll_deg=0.0,
            mount_pitch_deg=-30.0,
            mount_yaw_deg=0.0,
            max_range_m=1000.0,
        )
        self.assertIsNotNone(out_far)
        self.assertIsNotNone(out_near)
        self.assertGreater(out_far[2], out_near[2])

    def test_right_pixel_projects_to_positive_east(self):
        # yaw=0 => forward=north, right=east. Pixel to the right should yield lon increasing.
        H = 640
        W = 640
        drone_lat = 42.0
        drone_lon = -1.0
        out = GeoProjector.pixel_to_gps(
            H / 2,
            W * 0.75,
            image_height=H,
            image_width=W,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_yaw_deg=0.0,
            drone_pitch_deg=0.0,
            drone_roll_deg=0.0,
            alt_agl_m=10.0,
            camera_vfov_deg=45.0,
            mount_roll_deg=0.0,
            mount_pitch_deg=-30.0,
            mount_yaw_deg=0.0,
            max_range_m=1000.0,
        )
        self.assertIsNotNone(out)
        lat, lon, dist_h = out  # noqa: F841
        self.assertGreater(lon, drone_lon)


if __name__ == "__main__":
    unittest.main()
