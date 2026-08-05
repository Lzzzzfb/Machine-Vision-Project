import ctypes
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from angle_measurement.acquisition import ImageFileSource
from angle_measurement.acquisition import mvs


def _write(path, image):
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    encoded.tofile(path)


def test_image_file_source_handles_unicode_path(tmp_path):
    folder = tmp_path / "样图"
    folder.mkdir()
    _write(folder / "一.png", np.full((20, 30), 42, dtype=np.uint8))
    source = ImageFileSource(folder)
    source.open()
    frame = source.read()
    assert frame.image.shape == (20, 30)
    assert frame.frame_id == "一"
    with pytest.raises(EOFError):
        source.read()
    source.close()


def test_missing_mvs_sdk_has_actionable_error(monkeypatch):
    def missing_module(_name):
        raise ImportError

    monkeypatch.setattr(mvs.importlib, "import_module", missing_module)
    monkeypatch.setattr(mvs, "_candidate_sdk_paths", lambda: [])
    with pytest.raises(mvs.MvsSdkUnavailable, match="HIKROBOT_MVS_PYTHON_PATH"):
        mvs.load_mvs_module()


def test_mvs_sdk_path_uses_official_development_environment(monkeypatch):
    monkeypatch.delenv("HIKROBOT_MVS_PYTHON_PATH", raising=False)
    monkeypatch.delenv("HIKROBOT_MVS_ROOT", raising=False)
    monkeypatch.setenv("MVCAM_COMMON_RUNENV", r"D:\MVS\Development")
    paths = mvs._candidate_sdk_paths()
    assert paths[0] == (
        mvs.Path(r"D:\MVS\Development") / "Samples" / "Python" / "MvImport"
    )


def test_mvs_adapter_finalizes_sdk_when_no_camera_is_found(monkeypatch):
    sdk_calls = []

    class EmptyDeviceList:
        nDeviceNum = 0

    class FakeCamera:
        @staticmethod
        def MV_CC_Initialize():
            sdk_calls.append("initialize")
            return 0

        @staticmethod
        def MV_CC_Finalize():
            sdk_calls.append("finalize")
            return 0

        @staticmethod
        def MV_CC_EnumDevices(_transport, _device_list):
            return 0

    fake_module = SimpleNamespace(
        MV_GIGE_DEVICE=1,
        MV_USB_DEVICE=4,
        MV_CC_DEVICE_INFO_LIST=EmptyDeviceList,
        MvCamera=FakeCamera,
    )
    monkeypatch.setattr(mvs, "load_mvs_module", lambda: fake_module)
    source = mvs.MvsCameraSource()
    with pytest.raises(mvs.FrameSourceError, match="未发现相机"):
        source.open()
    assert sdk_calls == ["initialize", "finalize"]


def test_mvs_adapter_lifecycle_with_official_api_shape(monkeypatch):
    sdk_calls = []

    class DeviceInfo(ctypes.Structure):
        _fields_ = [("nTLayerType", ctypes.c_uint)]

    class FrameInfo(ctypes.Structure):
        _fields_ = [
            ("nWidth", ctypes.c_uint),
            ("nHeight", ctypes.c_uint),
            ("nFrameLen", ctypes.c_uint),
            ("nFrameNum", ctypes.c_uint),
        ]

    class FrameOut(ctypes.Structure):
        _fields_ = [
            ("pBufAddr", ctypes.POINTER(ctypes.c_ubyte)),
            ("stFrameInfo", FrameInfo),
        ]

    device = DeviceInfo(4)

    class DeviceList:
        def __init__(self):
            self.nDeviceNum = 0
            self._items = (ctypes.POINTER(DeviceInfo) * 1)(ctypes.pointer(device))
            self.pDeviceInfo = self._items

    class FakeCamera:
        last = None

        @staticmethod
        def MV_CC_Initialize():
            sdk_calls.append("initialize")
            return 0

        @staticmethod
        def MV_CC_Finalize():
            sdk_calls.append("finalize")
            return 0

        def __init__(self):
            FakeCamera.last = self
            self.buffer = (ctypes.c_ubyte * 12)(*range(12))
            self.calls = []

        @staticmethod
        def MV_CC_EnumDevices(_transport, device_list):
            device_list.nDeviceNum = 1
            return 0

        def __getattr__(self, name):
            if name == "MV_CC_GetImageBuffer":
                def get_buffer(frame, _timeout):
                    frame.pBufAddr = ctypes.cast(self.buffer, ctypes.POINTER(ctypes.c_ubyte))
                    frame.stFrameInfo = FrameInfo(4, 3, 12, 7)
                    self.calls.append(name)
                    return 0

                return get_buffer

            def success(*_args):
                self.calls.append(name)
                return 0

            return success

    fake_module = SimpleNamespace(
        MV_GIGE_DEVICE=1,
        MV_USB_DEVICE=4,
        MV_ACCESS_Exclusive=1,
        PixelType_Gvsp_Mono8=0x01080001,
        MV_TRIGGER_SOURCE_SOFTWARE=7,
        MV_CC_DEVICE_INFO_LIST=DeviceList,
        MV_CC_DEVICE_INFO=DeviceInfo,
        MV_FRAME_OUT=FrameOut,
        MvCamera=FakeCamera,
    )
    monkeypatch.setattr(mvs, "load_mvs_module", lambda: fake_module)
    source = mvs.MvsCameraSource(exposure_us=1000, gain_db=0)
    source.open()
    frame = source.read()
    source.close()
    assert frame.image.shape == (3, 4)
    assert frame.image[2, 3] == 11
    assert frame.metadata["frame_number"] == 7
    assert sdk_calls == ["initialize", "finalize"]
    assert FakeCamera.last.calls.count("MV_CC_SetEnumValue") == 5
    assert "MV_CC_CloseDevice" in FakeCamera.last.calls
    assert "MV_CC_DestroyHandle" in FakeCamera.last.calls
