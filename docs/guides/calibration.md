# 相机标定指南

## 打印标定板

使用仓库中的 `output/pdf/checkerboard-9x6-5mm.pdf`：

1. 普通 A4 复印纸即可。
2. 打印选择“实际大小”或 100%，关闭“适合页面”。
3. 平整粘贴到刚性平板，避免折痕、气泡和翘曲。
4. 用卡尺测量参考线或连续多个方格，计算实际平均格距。

如需重新生成其他格距：

```powershell
python tools/generate_checkerboard.py --square-mm 5 --output output/pdf/checkerboard-9x6-5mm.pdf
```

## 采集标定图片

- 锁定最终接圈、工作距离、光圈和焦点后再采图。
- 使用与测量相同的分辨率 2448 × 2048。
- 拍摄 15～25 张，覆盖画面中心、四角和边缘。
- 包含轻度水平和垂直倾斜，不要全部正对相机。
- 排除模糊、过曝、强反光、棋盘弯曲或角点太小的图片。
- 标定时环形灯产生高光可暂时降低亮度或改用均匀侧光。

## 运行标定

假设图片位于 `data/input/calibration`，实测平均格距为 5.01 mm：

```powershell
angle-calibrate data/input/calibration --glob "*.png" --square-mm 5.01 --output calibration/camera.json
```

输出包含相机矩阵、畸变系数、分辨率、每张图的重投影误差和整体 RMS。首版要求 RMS 不超过 0.5 px；超限时检查棋盘平整度、角点覆盖、模糊和曝光，然后重新采图。

标定文件只适用于对应的分辨率、接圈、工作距离和对焦状态。更换这些条件后重新标定。
