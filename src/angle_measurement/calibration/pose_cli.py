from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from .model import CalibrationData
from .service import CalibrationError, estimate_platform_pose


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从与平台参考面共面的棋盘格图像计算平台姿态")
    parser.add_argument("calibration", type=Path, help="已有相机内参标定 JSON")
    parser.add_argument("image", type=Path, help="平台平面棋盘格图片")
    parser.add_argument("--output", type=Path, default=Path("calibration/camera-with-pose.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        calibration = CalibrationData.load(args.calibration)
        image = cv2.imdecode(np.fromfile(args.image, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise CalibrationError(f"无法读取平台姿态图片: {args.image}")
        pose = estimate_platform_pose(calibration, image, str(args.image))
        replace(calibration, platform_pose=pose).save(args.output)
    except (OSError, ValueError, CalibrationError) as exc:
        print(f"平台姿态标定失败: {exc}")
        return 2
    print(f"标定文件: {args.output}")
    print(f"平台姿态重投影误差: {pose.reprojection_error_px:.4f} px")
    if pose.reprojection_error_px > 0.5:
        print("警告: 平台姿态 RMS 超过 0.5 px，建议重新采图")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
