# 海康工业相机狭缝—平台夹角测量

本项目使用 HIKROBOT MV-CS050-10UC 相机和 MVL-MF2518M-5MPE 25 mm 镜头，测量圆柱顶部亮狭缝中心线与矩形底座两条长外边平均方向之间的夹角。系统面向静止、人工放置的零件。

正式算法使用三个局部 ROI：亮狭缝中心线、平台长边 1、平台长边 2。两条平台边分别进行亚像素边缘定位，狭缝由成对边缘的中点定位，随后使用 RANSAC/总最小二乘拟合。通过相机内参、平台姿态和固定高度差，把两层像素线反投影到平行物理平面后计算 `0°～90°` 较小夹角。

## 目录导航

- [项目知识库](docs/knowledge-base/README.md)
- [双平面测量规格](docs/superpowers/specs/2026-08-05-bright-slit-platform-dual-plane-design.md)
- [双平面实施计划](docs/superpowers/plans/2026-08-06-bright-slit-platform-dual-plane-implementation.md)
- [标定指南](docs/guides/calibration.md)
- [MVS SDK 配置](docs/guides/mvs-sdk-setup.md)
- [操作指南](docs/guides/operator-guide.md)
- [MVS 实机采集验收](docs/validation/2026-08-05-mvs-hardware-validation.md)

## 安装与启动

推荐 Python 3.11 或 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gui,pdf,dev]"
angle-gui
```

MVS SDK 和 USB 驱动单独安装；当前机器已验证 `D:\MVS`。未安装 SDK 时，本地图片模式仍可使用。

先用仓库自带的 20° 三 ROI 合成图验证程序：

```powershell
angle-measure examples/synthetic-20deg.png --recipe configs/synthetic-demo.json --no-save
```

## 正式测量的必要条件

正式配方默认 `require_height_compensation=true`。以下条件缺一时，程序只显示 `projected_angle_deg` 诊断值，不输出正式 `angle_deg`：

1. 三个 ROI 均正确覆盖目标，平台两个 ROI 是矩形底座的两条长外边。
2. 已完成相机内参与畸变标定。
3. 已用与底座参考面共面的棋盘格图建立平台姿态。
4. 已输入从底座参考面到狭缝平面、沿平台法向测得的高度差。

圆柱轮廓、安装孔、底座短边、圆角/倒角和右侧缺口均不得作为平台基准。

## 输出解释

- `angle_deg`：完成双平面补偿后的正式角度；条件不足或质量不合格时为空。
- `projected_angle_deg`：图像平面诊断角，不代替正式结果。
- `platform_parallelism_deg`：平台双边平行度，用于发现 ROI 错位或边缘污染。
- `height_compensated`：是否实际执行了平台姿态和高度补偿。
- `confidence`：综合亮线、双边、点数、跨度、内点率和残差的置信度。
- `failure_reasons`：中文结构化失败原因。

自动保存会按日期生成原图、叠加图、逐帧 JSON 和汇总 CSV。

## 当前硬件状态

MVS 4.5.1、MV-CS050-10UC 枚举、Mono 8、软件触发、单帧取流以及两轮连续 500 帧均已验证。正式零件照片已确认；下一步是使用工业相机采集俯视原图，调整景深、照明和三个 ROI。
