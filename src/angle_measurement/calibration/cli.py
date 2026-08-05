from __future__ import annotations

import argparse
from pathlib import Path

from .service import CalibrationError, calibrate_from_images


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从棋盘格图像标定相机")
    parser.add_argument("images", type=Path, help="标定图片目录")
    parser.add_argument("--glob", default="*.png", help="图片匹配规则，默认 *.png")
    parser.add_argument("--square-mm", type=float, required=True, help="实测方格边长，单位 mm")
    parser.add_argument("--corners-x", type=int, default=9, help="横向内角点数量")
    parser.add_argument("--corners-y", type=int, default=6, help="纵向内角点数量")
    parser.add_argument("--minimum-images", type=int, default=8, help="最少有效图片数")
    parser.add_argument("--output", type=Path, default=Path("calibration/camera.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = sorted(args.images.glob(args.glob))
    try:
        calibration = calibrate_from_images(
            paths,
            square_size_mm=args.square_mm,
            inner_corners=(args.corners_x, args.corners_y),
            minimum_images=args.minimum_images,
        )
    except (CalibrationError, ValueError) as exc:
        print(f"标定失败: {exc}")
        return 2
    calibration.save(args.output)
    print(f"标定文件: {args.output}")
    print(f"有效图像: {len(calibration.source_images)}")
    print(f"RMS 重投影误差: {calibration.rms_reprojection_error:.4f} px")
    if calibration.rms_reprojection_error > 0.5:
        print("警告: RMS 超过 0.5 px，建议重新采图标定")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
