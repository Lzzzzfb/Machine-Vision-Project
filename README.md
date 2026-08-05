# 海康工业相机二维夹角测量

本项目使用 HIKROBOT MV-CS050-10UC 相机和 MVL-MF2518M-5MPE 25 mm 镜头，测量狭缝边缘与窄平台边缘在图像平面内的较小夹角。系统面向静态、人工放置的目标，采用两个可旋转测量带、亚像素边缘定位、RANSAC 和总最小二乘直线拟合。

> 当前结果是二维投影夹角。若两条边高度差明显，必须保证相机尽量垂直于平台；它不等同于三维空间夹角。

## 目录导航

- [项目知识库](docs/knowledge-base/README.md)
- [系统设计](docs/superpowers/specs/2026-08-05-angle-measurement-design.md)
- [实施计划](docs/superpowers/plans/2026-08-05-angle-measurement-implementation.md)
- [标定指南](docs/guides/calibration.md)
- [MVS SDK 配置](docs/guides/mvs-sdk-setup.md)
- [操作指南](docs/guides/operator-guide.md)

## 安装

推荐 Python 3.11 或 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gui,pdf,dev]"
```

海康 MVS SDK 和 USB 驱动需单独安装，厂商安装包和二进制不进入本仓库。未安装 SDK 时，本地图片模式仍可使用。

安装完成后可先用仓库自带的 20° 合成图验证算法链路：

```powershell
angle-measure examples/synthetic-20deg.png --recipe configs/synthetic-demo.json --no-save
```

## 最短离线使用路径

1. 把一张原始图片放入 `data/input/`。
2. 复制并修改 `configs/example_recipe.json` 中的两个测量带位置。
3. 运行：

```powershell
angle-measure data/input/example.png --recipe configs/example_recipe.json --output data/output
```

也可启动图形界面：

```powershell
angle-gui
```

首次使用实机前，请按照标定指南打印棋盘格并完成畸变标定。没有标定文件时程序可以运行，但结果会被明确标记为“未标定”。

## 结果解释

- `angle_deg`：0°～90°的较小夹角。
- `confidence`：基于边缘强度、点数、跨度、内点率和拟合残差的综合指标。
- `valid`：只有两条边均满足质量要求时才为 `true`。
- `failure_reasons`：无效结果的结构化原因；无效时 `angle_deg` 为空。

## 当前实机接入状态

已检测到 `D:\MVS` 中的 MVS 4.5.1，程序可通过厂商设置的 `MVCAM_COMMON_RUNENV` 自动找到 Python SDK。SDK 模块加载和设备枚举调用已经验证；验证时相机未连接，设备数为 0。接通相机后还需完成真实取流、曝光调节和连续 500 帧稳定性验证。
