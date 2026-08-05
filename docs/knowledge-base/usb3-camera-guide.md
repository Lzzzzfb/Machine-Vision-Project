# USB3.0 工业面阵相机使用指南

本页提炼通用用户手册中与 MV-CS050-10UC 测角项目最相关的内容。型号范围、曝光范围和像素格式仍以型号规格书为准。

## 安全和安装

- 接线、拆装和维护前断电，不要带电操作。
- 避免水、冷凝、强振动、强电场和强磁场。
- 不要让传感器通过直射或反射方式对准激光等强光。
- 图像窗口需要清洁时，使用柔软干净材料和不高于 75% 的酒精轻拭。
- 控制线、光源电源线、相机电源线和数据线尽量分开布线，并做好接地和屏蔽。

来源：[手册 PDF 第 11～12 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-011)。

## 接口和供电

相机使用 Micro USB3.0 B 型接口传输和 USB 供电。外部直流和 USB 同时存在时，外部直流优先；运行中拔掉外部直流电源可能使相机切换到 USB 供电并重启。

6-pin P7 管脚：[手册 PDF 第 19 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-019)。

| 管脚 | 信号 | I/O | 说明 | 海康线缆颜色 |
|---:|---|---|---|---|
| 1 | DC_PWR | - | 相机电源 | 橙 |
| 2 | OPTO_IN | Line 0+ | 光耦隔离输入 | 黄 |
| 3 | GPIO | Line 2+ | 可配置输入或输出 | 紫 |
| 4 | OPTO_OUT | Line 1+ | 光耦隔离输出 | 蓝 |
| 5 | OPTO_GND | Line 0-/1- | 光耦隔离信号地 | 绿 |
| 6 | GND | Line 2- | 相机电源地 | 灰 |

线芯颜色只适用于海康原厂线缆，第三方线缆必须核对实际线序，不能仅凭颜色接线。本项目首版使用 USB 供电和软件触发，不需要连接 P7。

## MVS 与 USB 驱动

1. 安装 MVS 客户端和 SDK，并勾选 USB 3.0 驱动。
2. 软件已集成硬件驱动，不需要另外寻找通用 USB 相机驱动。
3. Windows 设备管理器中应出现 `USB3 Vision Camera`。
4. 如果驱动异常，从开始菜单打开 `MVS > Tools > Driver_Installation_Tool`，检查或重装 USB 驱动。
5. 打开 MVS，设备列表应能枚举相机；双击连接后先用客户端连续采图验证硬件。

来源：[手册 PDF 第 30～37 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-030)。

## 软件触发

外触发模式下把 `Trigger Mode` 设为 `On`，`Trigger Source` 设为 `Software`，再执行 `Trigger Software`。硬件触发可使用 Line0 或配置为输入的 Line2，但本项目静态人工测量不需要硬件触发。

来源：[手册 PDF 第 48～50 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-048)。

## ROI、像素格式、曝光和增益

- 相机默认输出最大分辨率，只支持一个相机 ROI（Region0）。本项目首版保持全分辨率，并在软件内使用两个算法 ROI。
- 彩色相机原始数据为 Bayer；规格书确认本型号也支持 Mono 8。项目测量使用 Mono 8。
- 手动定时曝光：`Exposure Mode = Timed`、`Exposure Auto = Off`，通过 `Exposure Time` 设置。
- 增亮顺序：先增加曝光时间，再增加模拟增益，最后才考虑数字增益。数字增益对信噪比影响最大。
- 关闭 Gamma、LUT、锐化和自动控制，避免边缘位置随帧变化。

来源：[ROI：PDF 第 66～68 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-066)、[像素格式：第 69～71 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-069)、[曝光与增益：第 76～79 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-076)。

## 高频故障

| 现象 | 检查顺序 |
|---|---|
| MVS 搜不到相机 | 电源/LED → USB3 线缆和接口 → 重新插拔 → 驱动 |
| 能枚举但连接失败 | USB3 驱动 → 是否被其他程序独占 → 重装客户端 |
| 预览全黑 | 打开镜头光圈 → 检查 Trigger Mode → 增加曝光 |
| 触发后无图 | Trigger Mode/Source → 软件触发命令或硬件接线 |
| 算法拿不到所需图像 | 检查 Pixel Format 是否为 Mono 8 |
| 使用中掉线 | 接触和振动 → 线缆规格 → 不用转接头 → 静电/电磁干扰 → 必要时外部直流供电 |

来源：[手册 PDF 第 113～114 页](source-extracts/usb3-camera-manual-raw.md#pdf-page-113)。
