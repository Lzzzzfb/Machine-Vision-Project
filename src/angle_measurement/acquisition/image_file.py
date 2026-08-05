from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .base import Frame, FrameSource, FrameSourceError


SUPPORTED_EXTENSIONS = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def read_image_unicode(path: str | Path, flags: int = cv2.IMREAD_UNCHANGED) -> np.ndarray:
    source = Path(path)
    try:
        encoded = np.fromfile(source, dtype=np.uint8)
    except OSError as exc:
        raise FrameSourceError(f"无法读取图片文件: {source}: {exc}") from exc
    image = cv2.imdecode(encoded, flags)
    if image is None:
        raise FrameSourceError(f"无法解码图片: {source}")
    return image


class ImageFileSource(FrameSource):
    def __init__(self, path: str | Path, loop: bool = False) -> None:
        self.path = Path(path)
        self.loop = loop
        self._files: list[Path] = []
        self._index = 0
        self._opened = False

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(self._files)

    def open(self) -> None:
        if self.path.is_file():
            files = [self.path]
        elif self.path.is_dir():
            files = sorted(
                file
                for file in self.path.iterdir()
                if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        else:
            raise FrameSourceError(f"图片路径不存在: {self.path}")
        if not files:
            raise FrameSourceError(f"未找到支持的图片: {self.path}")
        self._files = files
        self._index = 0
        self._opened = True

    def read(self, timeout_ms: int = 1000) -> Frame:
        del timeout_ms
        if not self._opened:
            raise FrameSourceError("图片源尚未打开")
        if self._index >= len(self._files):
            if not self.loop:
                raise EOFError("图片序列已结束")
            self._index = 0
        path = self._files[self._index]
        self._index += 1
        return Frame(
            image=read_image_unicode(path),
            frame_id=path.stem,
            metadata={"source_path": str(path), "source_type": "image_file"},
        )

    def close(self) -> None:
        self._opened = False
