from __future__ import annotations

import argparse
import json
from pathlib import Path

from .acquisition import FrameSourceError, ImageFileSource
from .calibration.model import CalibrationData
from .measurement.overlay import draw_measurement_overlay
from .measurement.service import AngleMeasurementService
from .recipe import MeasurementRecipe
from .storage import ResultStorageError, ResultWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测量亮狭缝中心线与平台双边平均方向的较小夹角")
    parser.add_argument("input", type=Path, help="图片文件或图片目录")
    parser.add_argument("--recipe", type=Path, required=True, help="测量配方 JSON")
    parser.add_argument("--calibration", type=Path, help="相机标定 JSON")
    parser.add_argument("--output", type=Path, default=Path("data/output"))
    parser.add_argument("--no-save", action="store_true", help="只输出 JSON，不保存图片和 CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        recipe = MeasurementRecipe.load(args.recipe)
        calibration = CalibrationData.load(args.calibration) if args.calibration else None
        service = AngleMeasurementService(recipe, calibration)
        writer = None if args.no_save else ResultWriter(args.output)
        source = ImageFileSource(args.input)
        source.open()
    except (OSError, ValueError, FrameSourceError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    invalid_count = 0
    try:
        while True:
            try:
                frame = source.read()
            except EOFError:
                break
            result = service.measure(frame.image)
            overlay = draw_measurement_overlay(frame.image, recipe, result)
            output_paths = None
            if writer is not None:
                try:
                    output_paths = writer.write(
                        frame.image,
                        overlay,
                        result,
                        frame_id=frame.frame_id,
                        source_name=str(frame.metadata.get("source_path", args.input)),
                        recipe_name=recipe.name,
                        timestamp=frame.timestamp,
                        metadata=frame.metadata,
                    )
                except ResultStorageError as exc:
                    result.failure_reasons.append(str(exc))
            payload = result.to_dict()
            payload.update({"frame_id": frame.frame_id, "output": output_paths})
            print(json.dumps(payload, ensure_ascii=False))
            if not result.valid:
                invalid_count += 1
    finally:
        source.close()
    return 1 if invalid_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
