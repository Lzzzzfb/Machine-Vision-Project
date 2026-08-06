import numpy as np

from angle_measurement.calibration.model import CalibrationData, PlatformPose
from angle_measurement.measurement.plane import backproject_pixels_to_parallel_plane


def test_backproject_pixels_to_offset_plane():
    calibration = CalibrationData(
        camera_matrix=np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=float),
        distortion_coefficients=np.zeros(5),
        image_size=(640, 480),
        rms_reprojection_error=0.1,
        square_size_mm=5,
        platform_pose=PlatformPose(
            rotation_vector=np.zeros(3),
            translation_vector=np.array([0, 0, 200], dtype=float),
            reprojection_error_px=0.1,
        ),
    )
    expected = np.array([[-10.0, 2.0, -20.0], [15.0, 2.0, -20.0]])
    camera = expected + np.array([0.0, 0.0, 200.0])
    pixels = np.column_stack(
        (
            800 * camera[:, 0] / camera[:, 2] + 320,
            800 * camera[:, 1] / camera[:, 2] + 240,
        )
    )
    restored = backproject_pixels_to_parallel_plane(pixels, calibration, 20.0)
    assert np.allclose(restored, expected)
