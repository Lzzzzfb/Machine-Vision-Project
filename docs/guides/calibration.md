# 相机与平台姿态标定指南

正式双平面测量分为两步：多图内参标定和单图平台姿态标定。打印纸可以使用普通纸，但必须平整粘贴到刚性平板。

## 1. 打印标定板

使用 `output/pdf/checkerboard-9x6-5mm.pdf`：

1. 打印选择“实际大小”或 100%，关闭“适合页面”。
2. 平整粘贴到刚性平板，避免折痕、气泡和翘曲。
3. 用卡尺连续测量多个方格并除以格数，得到实际平均格距。

重新生成：

```powershell
python tools/generate_checkerboard.py --square-mm 5 --output output/pdf/checkerboard-9x6-5mm.pdf
```

## 2. 内参与畸变标定

锁定最终工作距离、光圈和焦点，使用 2448 × 2048 分辨率拍摄 15～25 张棋盘格：覆盖中心、四角和边缘，包含轻度水平/垂直倾斜，排除模糊、过曝、反光和弯曲图片。

```powershell
angle-calibrate data/input/calibration --glob "*.png" --square-mm 5.01 `
  --output calibration/camera.json
```

整体 RMS 目标不超过 0.5 px。

## 3. 平台参考姿态

相机保持固定，把棋盘格表面放到“矩形底座长边所在参考平面”。如果底座太小，可使用更大的刚性参考板，但必须用机械基准、卡尺或量块保证棋盘表面与该平面同高且平行。只保证平行而高度未知不合格。

采集一张棋盘清晰、覆盖范围较大且不过曝的图，例如 `platform-pose.png`，然后运行：

```powershell
angle-calibrate-pose calibration/camera.json platform-pose.png `
  --output calibration/camera-with-pose.json
```

平台姿态 RMS 目标同样不超过 0.5 px。GUI 正式测量时加载 `camera-with-pose.json`。

## 4. 高度差

用卡尺或深度尺测量从平台参考面到实际狭缝平面的垂直高度，取多次读数平均值，填入配方的 `height_difference_mm` 或 GUI“狭缝高度差”。高度固定后不需要每次重新测量。

## 5. 失效条件

更换或移动相机、镜头、接圈、工作距离、焦点，或者改变平台参考面位置后，必须重新执行内参与平台姿态标定。只改变曝光、增益和灯光亮度通常不需要重新标定。
