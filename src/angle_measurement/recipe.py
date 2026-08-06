from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .models import (
    BrightLineExtractionConfig,
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
class BrightBandConfig:
    name: str
    roi: RotatedRoi
    bright: BrightLineExtractionConfig = field(default_factory=BrightLineExtractionConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "roi": self.roi.to_dict(),
            "bright": asdict(self.bright),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrightBandConfig":
        return cls(
            name=str(data["name"]),
            roi=RotatedRoi.from_dict(data["roi"]),
            bright=BrightLineExtractionConfig(**data.get("bright", {})),
        )


@dataclass(frozen=True)
class MeasurementRecipe:
    name: str
    slit_center: BrightBandConfig
    platform_left: BandConfig
    platform_right: BandConfig
    line_fit: LineFitConfig = field(default_factory=LineFitConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    height_difference_mm: float | None = None
    require_height_compensation: bool = True
    calibration_file: str | None = None
    platform_right_confirmed: bool = True
    version: int = 2

    def __post_init__(self) -> None:
        if self.version != 2:
            raise ValueError(f"Unsupported recipe version: {self.version}")
        if not self.name.strip():
            raise ValueError("Recipe name cannot be empty")
        if self.height_difference_mm is not None and self.height_difference_mm < 0:
            raise ValueError("height_difference_mm cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "slit_center": self.slit_center.to_dict(),
            "platform_left": self.platform_left.to_dict(),
            "platform_right": self.platform_right.to_dict(),
            "height_difference_mm": self.height_difference_mm,
            "require_height_compensation": self.require_height_compensation,
            "platform_right_confirmed": self.platform_right_confirmed,
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
    def _migrate_v1(cls, data: dict[str, Any]) -> "MeasurementRecipe":
        old_slit = BandConfig.from_dict(data["slit"])
        old_platform = BandConfig.from_dict(data["platform"])
        bright = BrightLineExtractionConfig(
            scan_step_px=old_slit.edge.scan_step_px,
            profile_step_px=old_slit.edge.profile_step_px,
            gaussian_sigma=old_slit.edge.gaussian_sigma,
            min_gradient=old_slit.edge.min_gradient,
            center_bias=old_slit.edge.center_bias,
            max_direction_deviation_deg=old_slit.edge.max_direction_deviation_deg,
        )
        return cls(
            name=str(data["name"]),
            slit_center=BrightBandConfig("slit_center", old_slit.roi, bright),
            platform_left=replace(old_platform, name="platform_left"),
            platform_right=replace(old_platform, name="platform_right"),
            line_fit=LineFitConfig(**data.get("line_fit", {})),
            quality=QualityConfig(**data.get("quality", {})),
            calibration_file=data.get("calibration_file"),
            height_difference_mm=None,
            require_height_compensation=True,
            platform_right_confirmed=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeasurementRecipe":
        version = int(data.get("version", 1))
        if version == 1:
            return cls._migrate_v1(data)
        if version != 2:
            raise ValueError(f"Unsupported recipe version: {version}")
        return cls(
            version=version,
            name=str(data["name"]),
            slit_center=BrightBandConfig.from_dict(data["slit_center"]),
            platform_left=BandConfig.from_dict(data["platform_left"]),
            platform_right=BandConfig.from_dict(data["platform_right"]),
            line_fit=LineFitConfig(**data.get("line_fit", {})),
            quality=QualityConfig(**data.get("quality", {})),
            height_difference_mm=(
                None
                if data.get("height_difference_mm") is None
                else float(data["height_difference_mm"])
            ),
            require_height_compensation=bool(data.get("require_height_compensation", True)),
            calibration_file=data.get("calibration_file"),
            platform_right_confirmed=bool(data.get("platform_right_confirmed", True)),
        )

    @classmethod
    def load(cls, path: str | Path) -> "MeasurementRecipe":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


def default_recipe(width: int = 2448, height: int = 2048) -> MeasurementRecipe:
    """Create a three-band starting recipe that must be aligned to the real image."""

    length = width * 0.35
    slit_width = max(50.0, height * 0.05)
    edge_width = max(40.0, height * 0.04)
    return MeasurementRecipe(
        name="MV-CS050-10UC-bright-slit-example",
        slit_center=BrightBandConfig(
            name="slit_center",
            roi=RotatedRoi(width * 0.50, height * 0.38, length * 0.45, slit_width, 0.0),
        ),
        platform_left=BandConfig(
            name="platform_left",
            roi=RotatedRoi(width * 0.50, height * 0.64, length, edge_width, 0.0),
        ),
        platform_right=BandConfig(
            name="platform_right",
            roi=RotatedRoi(width * 0.50, height * 0.76, length, edge_width, 0.0),
        ),
    )
