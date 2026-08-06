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
        "projected_angle_deg",
        "height_compensated",
        "platform_parallelism_deg",
        "confidence",
        "failure_reasons",
        "slit_rms_px",
        "slit_inlier_ratio",
        "slit_span_px",
        "platform_rms_px",
        "platform_inlier_ratio",
        "platform_span_px",
        "platform_left_rms_px",
        "platform_left_inlier_ratio",
        "platform_right_rms_px",
        "platform_right_inlier_ratio",
        "slit_mean_width_px",
        "slit_focus_status",
        "slit_focus_blur_width_px",
        "platform_left_focus_status",
        "platform_left_focus_blur_width_px",
        "platform_right_focus_status",
        "platform_right_focus_blur_width_px",
        "stability_status",
        "stability_stable",
        "stability_window_size",
        "stability_valid_count",
        "stability_median_deg",
        "stability_mean_deg",
        "stability_stddev_deg",
        "stability_range_deg",
        "camera_fps",
        "measurement_fps",
        "exposure_us",
        "gain_db",
        "raw_image",
        "overlay_image",
        "result_json",
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
        result_path = folder / f"{safe_id}-result.json"
        write_image_unicode(raw_path, image)
        write_image_unicode(overlay_path, overlay)
        metadata = metadata or {}
        result_payload = result.to_dict()
        result_payload["frame_id"] = frame_id
        result_payload["source_name"] = source_name
        result_payload["recipe_name"] = recipe_name
        result_payload["timestamp"] = timestamp
        result_payload["stability"] = metadata.get("stability")
        result_payload["runtime"] = {
            key: metadata.get(key)
            for key in (
                "camera_fps",
                "measurement_fps",
                "exposure_us",
                "gain_db",
            )
        }
        result_payload["metadata"] = metadata
        try:
            result_path.write_text(
                json.dumps(result_payload, ensure_ascii=False, indent=2, default=_json_default)
                + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ResultStorageError(f"JSON 保存失败: {result_path}: {exc}") from exc
        csv_path = folder / "measurements.csv"
        stability = _mapping(metadata.get("stability"))
        slit_focus = _mapping(result.diagnostics.get("slit_focus"))
        left_focus = _mapping(result.diagnostics.get("platform_left_focus"))
        right_focus = _mapping(result.diagnostics.get("platform_right_focus"))
        row = {
            "timestamp": timestamp,
            "frame_id": frame_id,
            "source_name": source_name,
            "recipe_name": recipe_name,
            "valid": result.valid,
            "calibrated": result.calibrated,
            "angle_deg": "" if result.angle_deg is None else f"{result.angle_deg:.8f}",
            "projected_angle_deg": ""
            if result.projected_angle_deg is None
            else f"{result.projected_angle_deg:.8f}",
            "height_compensated": result.height_compensated,
            "platform_parallelism_deg": ""
            if result.platform_parallelism_deg is None
            else f"{result.platform_parallelism_deg:.8f}",
            "confidence": f"{result.confidence:.6f}",
            "failure_reasons": " | ".join(result.failure_reasons),
            "slit_rms_px": "" if result.line_slit is None else f"{result.line_slit.rms_px:.6f}",
            "slit_inlier_ratio": "" if result.line_slit is None else f"{result.line_slit.inlier_ratio:.6f}",
            "slit_span_px": "" if result.line_slit is None else f"{result.line_slit.span_px:.3f}",
            "platform_rms_px": "" if result.line_platform is None else f"{result.line_platform.rms_px:.6f}",
            "platform_inlier_ratio": "" if result.line_platform is None else f"{result.line_platform.inlier_ratio:.6f}",
            "platform_span_px": "" if result.line_platform is None else f"{result.line_platform.span_px:.3f}",
            "platform_left_rms_px": ""
            if result.line_platform_left is None
            else f"{result.line_platform_left.rms_px:.6f}",
            "platform_left_inlier_ratio": ""
            if result.line_platform_left is None
            else f"{result.line_platform_left.inlier_ratio:.6f}",
            "platform_right_rms_px": ""
            if result.line_platform_right is None
            else f"{result.line_platform_right.rms_px:.6f}",
            "platform_right_inlier_ratio": ""
            if result.line_platform_right is None
            else f"{result.line_platform_right.inlier_ratio:.6f}",
            "slit_mean_width_px": result.diagnostics.get("slit_mean_width_px", ""),
            "slit_focus_status": slit_focus.get("status", ""),
            "slit_focus_blur_width_px": _csv_number(
                slit_focus.get("median_blur_width_px")
            ),
            "platform_left_focus_status": left_focus.get("status", ""),
            "platform_left_focus_blur_width_px": _csv_number(
                left_focus.get("median_blur_width_px")
            ),
            "platform_right_focus_status": right_focus.get("status", ""),
            "platform_right_focus_blur_width_px": _csv_number(
                right_focus.get("median_blur_width_px")
            ),
            "stability_status": stability.get("status", ""),
            "stability_stable": stability.get("stable", ""),
            "stability_window_size": stability.get("window_size", ""),
            "stability_valid_count": stability.get("valid_count", ""),
            "stability_median_deg": _csv_number(stability.get("median_deg")),
            "stability_mean_deg": _csv_number(stability.get("mean_deg")),
            "stability_stddev_deg": _csv_number(stability.get("stddev_deg")),
            "stability_range_deg": _csv_number(stability.get("range_deg")),
            "camera_fps": _csv_number(metadata.get("camera_fps")),
            "measurement_fps": _csv_number(metadata.get("measurement_fps")),
            "exposure_us": _csv_number(metadata.get("exposure_us")),
            "gain_db": _csv_number(metadata.get("gain_db")),
            "raw_image": str(raw_path.relative_to(self.root)),
            "overlay_image": str(overlay_path.relative_to(self.root)),
            "result_json": str(result_path.relative_to(self.root)),
            "metadata_json": json.dumps(
                metadata, ensure_ascii=False, separators=(",", ":"), default=_json_default
            ),
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
            "result_json": str(result_path),
            "csv": str(csv_path),
        }


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _csv_number(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.8f}"
    except (TypeError, ValueError):
        return ""
