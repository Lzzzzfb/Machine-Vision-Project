from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import MeasurementResult


class ResultStorageError(RuntimeError):
    pass


def write_image_unicode(path: str | Path, image: np.ndarray) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = destination.suffix or ".png"
    success, encoded = cv2.imencode(suffix, image)
    if not success:
        raise ResultStorageError(f"图像编码失败: {destination}")
    try:
        encoded.tofile(destination)
    except OSError as exc:
        raise ResultStorageError(f"图像保存失败: {destination}: {exc}") from exc
    return destination


class ResultWriter:
    CSV_FIELDS = [
        "timestamp",
        "frame_id",
        "source_name",
        "recipe_name",
        "valid",
        "calibrated",
        "angle_deg",
        "confidence",
        "failure_reasons",
        "slit_rms_px",
        "slit_inlier_ratio",
        "slit_span_px",
        "platform_rms_px",
        "platform_inlier_ratio",
        "platform_span_px",
        "raw_image",
        "overlay_image",
        "metadata_json",
    ]

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(
        self,
        image: np.ndarray,
        overlay: np.ndarray,
        result: MeasurementResult,
        frame_id: str,
        source_name: str,
        recipe_name: str,
        timestamp: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        day = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        folder = self.root / day
        safe_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in frame_id)
        raw_path = folder / f"{safe_id}-raw.png"
        overlay_path = folder / f"{safe_id}-result.png"
        write_image_unicode(raw_path, image)
        write_image_unicode(overlay_path, overlay)
        csv_path = folder / "measurements.csv"
        row = {
            "timestamp": timestamp,
            "frame_id": frame_id,
            "source_name": source_name,
            "recipe_name": recipe_name,
            "valid": result.valid,
            "calibrated": result.calibrated,
            "angle_deg": "" if result.angle_deg is None else f"{result.angle_deg:.8f}",
            "confidence": f"{result.confidence:.6f}",
            "failure_reasons": " | ".join(result.failure_reasons),
            "slit_rms_px": "" if result.line_slit is None else f"{result.line_slit.rms_px:.6f}",
            "slit_inlier_ratio": "" if result.line_slit is None else f"{result.line_slit.inlier_ratio:.6f}",
            "slit_span_px": "" if result.line_slit is None else f"{result.line_slit.span_px:.3f}",
            "platform_rms_px": "" if result.line_platform is None else f"{result.line_platform.rms_px:.6f}",
            "platform_inlier_ratio": "" if result.line_platform is None else f"{result.line_platform.inlier_ratio:.6f}",
            "platform_span_px": "" if result.line_platform is None else f"{result.line_platform.span_px:.3f}",
            "raw_image": str(raw_path.relative_to(self.root)),
            "overlay_image": str(overlay_path.relative_to(self.root)),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":")),
        }
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not csv_path.exists()
        try:
            with csv_path.open("a", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.CSV_FIELDS)
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            raise ResultStorageError(f"CSV 保存失败: {csv_path}: {exc}") from exc
        return {
            "raw_image": str(raw_path),
            "overlay_image": str(overlay_path),
            "csv": str(csv_path),
        }
