from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import (
    EdgeExtractionConfig,
    EdgePolarity,
    LineFitConfig,
    QualityConfig,
    RotatedRoi,
)


@dataclass(frozen=True)
class BandConfig:
    name: str
    roi: RotatedRoi
    edge: EdgeExtractionConfig = field(default_factory=EdgeExtractionConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "roi": self.roi.to_dict(),
            "edge": {**asdict(self.edge), "polarity": self.edge.polarity.value},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BandConfig":
        edge_data = dict(data.get("edge", {}))
        edge_data["polarity"] = EdgePolarity(edge_data.get("polarity", "auto"))
        return cls(
            name=str(data["name"]),
            roi=RotatedRoi.from_dict(data["roi"]),
            edge=EdgeExtractionConfig(**edge_data),
        )


@dataclass(frozen=True)
class MeasurementRecipe:
    name: str
    slit: BandConfig
    platform: BandConfig
    line_fit: LineFitConfig = field(default_factory=LineFitConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    calibration_file: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ValueError(f"Unsupported recipe version: {self.version}")
        if not self.name.strip():
            raise ValueError("Recipe name cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "slit": self.slit.to_dict(),
            "platform": self.platform.to_dict(),
            "line_fit": asdict(self.line_fit),
            "quality": asdict(self.quality),
            "calibration_file": self.calibration_file,
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeasurementRecipe":
        return cls(
            version=int(data.get("version", 1)),
            name=str(data["name"]),
            slit=BandConfig.from_dict(data["slit"]),
            platform=BandConfig.from_dict(data["platform"]),
            line_fit=LineFitConfig(**data.get("line_fit", {})),
            quality=QualityConfig(**data.get("quality", {})),
            calibration_file=data.get("calibration_file"),
        )

    @classmethod
    def load(cls, path: str | Path) -> "MeasurementRecipe":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


def default_recipe(width: int = 2448, height: int = 2048) -> MeasurementRecipe:
    """Create a safe starting recipe that must be aligned to the real image."""

    length = width * 0.45
    band_width = max(40.0, height * 0.06)
    return MeasurementRecipe(
        name="MV-CS050-10UC-example",
        slit=BandConfig(
            name="slit_edge",
            roi=RotatedRoi(width * 0.50, height * 0.40, length, band_width, 0.0),
        ),
        platform=BandConfig(
            name="platform_edge",
            roi=RotatedRoi(width * 0.50, height * 0.62, length, band_width, 10.0),
        ),
    )
