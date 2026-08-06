import json

import numpy as np
import pytest

from angle_measurement.calibration.model import CalibrationData, PlatformPose


def _calibration():
    return CalibrationData(
        camera_matrix=np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=float),
        distortion_coefficients=np.array([0.01, -0.02, 0.0, 0.0, 0.0]),
        image_size=(640, 480),
        rms_reprojection_error=0.2,
        square_size_mm=5.0,
        per_view_errors=[0.18, 0.22],
    )


def test_calibration_round_trip(tmp_path):
    calibration = _calibration()
    path = calibration.save(tmp_path / "camera.json")
    restored = CalibrationData.load(path)
    assert np.allclose(restored.camera_matrix, calibration.camera_matrix)
    assert np.allclose(restored.distortion_coefficients, calibration.distortion_coefficients)
    assert restored.image_size == (640, 480)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_calibration_rejects_wrong_resolution():
    calibration = _calibration()
    with pytest.raises(ValueError, match="分辨率"):
        calibration.undistort(np.zeros((100, 100), dtype=np.uint8))


def test_platform_pose_round_trip(tmp_path):
    calibration = _calibration()
    calibration.platform_pose = PlatformPose(
        rotation_vector=np.array([0.01, -0.02, 0.03]),
        translation_vector=np.array([1.0, 2.0, 200.0]),
        reprojection_error_px=0.15,
    )
    restored = CalibrationData.load(calibration.save(tmp_path / "pose.json"))
    assert restored.platform_pose is not None
    assert np.allclose(restored.platform_pose.translation_vector, [1, 2, 200])
