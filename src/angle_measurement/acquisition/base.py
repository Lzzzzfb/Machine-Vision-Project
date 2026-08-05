from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np


class FrameSourceError(RuntimeError):
    pass


@dataclass
class Frame:
    image: np.ndarray
    frame_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class FrameSource(ABC):
    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self, timeout_ms: int = 1000) -> Frame:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
