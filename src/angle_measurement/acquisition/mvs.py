from __future__ import annotations

import ctypes
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

from .base import Frame, FrameSource, FrameSourceError


class MvsSdkUnavailable(FrameSourceError):
    pass


def _candidate_sdk_paths() -> list[Path]:
    paths: list[Path] = []
    configured = os.environ.get("HIKROBOT_MVS_PYTHON_PATH")
    if configured:
        paths.append(Path(configured))
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            paths.extend(
                [
                    Path(base) / "MVS" / "Development" / "Samples" / "Python" / "MvImport",
                    Path(base) / "MVS" / "Development" / "Samples" / "Python",
                ]
            )
    return paths


def load_mvs_module() -> ModuleType:
    try:
        return importlib.import_module("MvCameraControl_class")
    except ImportError:
        pass
    for path in _candidate_sdk_paths():
        if not (path / "MvCameraControl_class.py").exists():
            continue
        sys.path.insert(0, str(path))
        try:
            return importlib.import_module("MvCameraControl_class")
        except ImportError:
            sys.path.pop(0)
    searched = "\n".join(f"- {path}" for path in _candidate_sdk_paths())
    raise MvsSdkUnavailable(
        "未找到海康 MVS Python 模块 MvCameraControl_class.py。请安装 MVS SDK，"
        "或设置 HIKROBOT_MVS_PYTHON_PATH 指向 MvImport 目录。已检查:\n"
        f"{searched or '- 无可用默认路径'}"
    )


class MvsCameraSource(FrameSource):
    """Thin adapter for the official HIKROBOT MVS Python sample API."""

    def __init__(
        self,
        device_index: int = 0,
        exposure_us: float = 5000.0,
        gain_db: float = 0.0,
    ) -> None:
        self.device_index = device_index
        self.exposure_us = exposure_us
        self.gain_db = gain_db
        self._module: ModuleType | None = None
        self._camera = None
        self._opened = False
        self._device_opened = False
        self._grabbing = False
        self._frame_number = 0

    @staticmethod
    def _check(ret: int, action: str) -> None:
        if int(ret) != 0:
            raise FrameSourceError(f"{action}失败，MVS 错误码 0x{int(ret) & 0xFFFFFFFF:08X}")

    def _constant(self, name: str, fallback: int | None = None) -> int:
        assert self._module is not None
        value = getattr(self._module, name, fallback)
        if value is None:
            raise MvsSdkUnavailable(f"当前 MVS SDK 缺少常量 {name}")
        return int(value)

    def _enumerate(self):
        assert self._module is not None
        device_list = self._module.MV_CC_DEVICE_INFO_LIST()
        transport = self._constant("MV_GIGE_DEVICE", 0x00000001) | self._constant(
            "MV_USB_DEVICE", 0x00000004
        )
        ret = self._module.MvCamera.MV_CC_EnumDevices(transport, device_list)
        self._check(ret, "枚举相机")
        if int(device_list.nDeviceNum) == 0:
            raise FrameSourceError("未发现相机，请检查 USB3 线缆、供电、驱动和 MVS 客户端")
        if not 0 <= self.device_index < int(device_list.nDeviceNum):
            raise FrameSourceError(
                f"相机索引 {self.device_index} 超出范围，共发现 {device_list.nDeviceNum} 台"
            )
        pointer = device_list.pDeviceInfo[self.device_index]
        return ctypes.cast(
            pointer,
            ctypes.POINTER(self._module.MV_CC_DEVICE_INFO),
        ).contents

    def open(self) -> None:
        if self._opened:
            return
        self._module = load_mvs_module()
        device_info = self._enumerate()
        self._camera = self._module.MvCamera()
        self._check(self._camera.MV_CC_CreateHandle(device_info), "创建相机句柄")
        try:
            self._check(
                self._camera.MV_CC_OpenDevice(self._constant("MV_ACCESS_Exclusive", 1), 0),
                "打开相机",
            )
            self._device_opened = True
            self._check(
                self._camera.MV_CC_SetEnumValue(
                    "PixelFormat", self._constant("PixelType_Gvsp_Mono8", 0x01080001)
                ),
                "设置 Mono 8",
            )
            self._check(self._camera.MV_CC_SetEnumValue("TriggerMode", 1), "开启触发模式")
            self._check(
                self._camera.MV_CC_SetEnumValue(
                    "TriggerSource", self._constant("MV_TRIGGER_SOURCE_SOFTWARE", 7)
                ),
                "设置软件触发",
            )
            self._check(
                self._camera.MV_CC_SetFloatValue("ExposureTime", float(self.exposure_us)),
                "设置曝光时间",
            )
            self._check(
                self._camera.MV_CC_SetFloatValue("Gain", float(self.gain_db)),
                "设置增益",
            )
            self._check(self._camera.MV_CC_StartGrabbing(), "开始取流")
            self._grabbing = True
            self._opened = True
        except Exception:
            self.close()
            raise

    def read(self, timeout_ms: int = 1000) -> Frame:
        if not self._opened or self._camera is None or self._module is None:
            raise FrameSourceError("相机尚未打开")
        self._check(self._camera.MV_CC_SetCommandValue("TriggerSoftware"), "执行软件触发")
        frame = self._module.MV_FRAME_OUT()
        ctypes.memset(ctypes.byref(frame), 0, ctypes.sizeof(frame))
        self._check(self._camera.MV_CC_GetImageBuffer(frame, int(timeout_ms)), "获取图像")
        try:
            info = frame.stFrameInfo
            width, height = int(info.nWidth), int(info.nHeight)
            length = int(info.nFrameLen)
            if width <= 0 or height <= 0 or length < width * height:
                raise FrameSourceError(
                    f"无效帧尺寸: {width}x{height}, payload={length}"
                )
            buffer = np.ctypeslib.as_array(frame.pBufAddr, shape=(length,))
            image = np.array(buffer[: width * height], copy=True).reshape(height, width)
            self._frame_number += 1
            return Frame(
                image=image,
                frame_id=f"mvs-{self._frame_number:08d}",
                metadata={
                    "source_type": "mvs",
                    "device_index": self.device_index,
                    "width": width,
                    "height": height,
                    "frame_number": int(getattr(info, "nFrameNum", self._frame_number)),
                    "exposure_us": self.exposure_us,
                    "gain_db": self.gain_db,
                    "pixel_format": "Mono8",
                    "trigger_mode": "Software",
                },
            )
        finally:
            self._camera.MV_CC_FreeImageBuffer(frame)

    def close(self) -> None:
        camera = self._camera
        if camera is not None:
            if self._grabbing:
                camera.MV_CC_StopGrabbing()
            if self._device_opened:
                camera.MV_CC_CloseDevice()
            camera.MV_CC_DestroyHandle()
        self._camera = None
        self._opened = False
        self._device_opened = False
        self._grabbing = False
