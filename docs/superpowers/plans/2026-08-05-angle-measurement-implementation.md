# 狭缝与窄平台夹角测量系统实施计划

- 日期：2026-08-05
- 依据：`docs/superpowers/specs/2026-08-05-angle-measurement-design.md`
- 目标：交付可离线运行、可接入海康 MVS SDK、可标定、可测试的 Windows Python 应用和配套知识库

## 实施原则

1. 核心测量算法不依赖相机 SDK 和图形界面。
2. 所有无效测量都返回结构化原因，不产生伪角度。
3. 每个阶段先完成自动化测试，再进入下一阶段。
4. MVS SDK 厂商二进制、用户图片、标定结果和测量输出不进入 Git。
5. 实机参数通过配置文件管理，不硬编码到算法中。

## 任务 1：项目骨架与依赖

创建：

- `pyproject.toml`
- `.gitignore`
- `README.md`
- `src/angle_measurement/__init__.py`
- `src/angle_measurement/__main__.py`
- `configs/example_recipe.json`
- `data/input/.gitkeep`
- `data/output/.gitkeep`

要求：

- 核心依赖为 NumPy 和 OpenCV。
- GUI 依赖 PySide6，测试依赖 pytest。
- 提供 `angle-measure` 和 `angle-calibrate` 命令入口。
- README 给出离线最短运行路径和 MVS 接入路径。

验证：构建元数据可被 Python 解析；包可导入；CLI 帮助可显示。

## 任务 2：领域模型与配方

创建：

- `src/angle_measurement/models.py`
- `src/angle_measurement/recipe.py`
- `tests/unit/test_recipe.py`

实现：

- 旋转测量带 ROI
- 边缘提取参数
- 直线拟合参数
- 质量阈值
- 相机参数和结果保存参数
- JSON 配方读写、版本号和输入校验

验证：示例配方可往返保存；非法尺寸、角度、极性和阈值会被拒绝。

## 任务 3：边缘与直线算法

创建：

- `src/angle_measurement/measurement/edge.py`
- `src/angle_measurement/measurement/line.py`
- `src/angle_measurement/measurement/angle.py`
- `src/angle_measurement/measurement/service.py`
- `src/angle_measurement/measurement/overlay.py`
- `tests/unit/test_edge.py`
- `tests/unit/test_line.py`
- `tests/unit/test_angle.py`
- `tests/synthetic/test_measurement_synthetic.py`

实现：

- 旋转坐标映射和一维法向扫描线
- 梯度极性筛选和亚像素峰值定位
- RANSAC 离群点剔除
- 总最小二乘直线拟合
- 0°～90°较小夹角
- 图像质量、拟合质量、置信度和失败原因
- 测量结果叠加图

验证：合成图像覆盖水平、垂直、任意方向、噪声、模糊、断边和离群点；有效样本误差不超过设计目标，不可测样本返回无效。

## 任务 4：相机标定

创建：

- `src/angle_measurement/calibration/model.py`
- `src/angle_measurement/calibration/service.py`
- `src/angle_measurement/calibration/cli.py`
- `tools/generate_checkerboard.py`
- `assets/calibration/checkerboard-9x6-5mm.pdf`
- `docs/guides/calibration.md`
- `tests/unit/test_calibration.py`

实现：

- 棋盘角点检测和亚像素优化
- 相机矩阵、畸变系数和质量元数据保存
- 分辨率一致性校验
- 图像去畸变
- A4、9 × 6 内角点、5 mm 格距的打印 PDF

验证：合成标定模型可往返；错误分辨率被拒绝；PDF 重新打开后页数和尺寸正确；渲染后棋盘、尺寸检查线和打印说明无裁切。

## 任务 5：图像源与 MVS 适配层

创建：

- `src/angle_measurement/acquisition/base.py`
- `src/angle_measurement/acquisition/image_file.py`
- `src/angle_measurement/acquisition/mvs.py`
- `docs/guides/mvs-sdk-setup.md`
- `tests/unit/test_image_source.py`

实现：

- 统一 `FrameSource` 接口
- 单文件和目录顺序回放
- MVS Python 模块路径探测
- 设备枚举、按索引连接、Mono 8 参数设置、软件触发和单帧获取
- 缺失 SDK、无设备、超时和参数设置失败的结构化错误

验证：离线源完整测试；MVS 缺失时错误信息包含安装与路径指导；实机调用通过隔离接口保留后续现场验收点。

## 任务 6：结果存储与命令行

创建：

- `src/angle_measurement/storage.py`
- `src/angle_measurement/cli.py`
- `tests/unit/test_storage.py`
- `tests/integration/test_cli.py`

实现：

- 单图和目录批量测量
- JSON 结果输出
- 原图、叠加图和 CSV 保存
- 每条记录包含配方、标定和质量元数据
- 保存失败不破坏当前测量结果

验证：在临时目录完成批处理，检查输出文件、CSV 字段、无效结果和退出码。

## 任务 7：桌面界面

创建：

- `src/angle_measurement/ui/main_window.py`
- `src/angle_measurement/ui/roi_item.py`
- `src/angle_measurement/ui/worker.py`
- `src/angle_measurement/ui/launcher.py`
- `docs/guides/operator-guide.md`

实现：

- 相机/文件源选择
- 图像打开、连接、预览、单次与连续测量
- 两个可旋转 ROI 的可视化编辑
- 曝光、增益和配方加载/保存
- 原图/结果图显示
- 角度、置信度、残差、内点率和失败原因展示
- MVS/PySide6 缺失时提供可操作提示

验证：模块可导入；无显示器环境下完成窗口构造冒烟测试；核心测量在工作线程执行，界面线程不直接阻塞取帧。

## 任务 8：知识库

创建：

- `docs/knowledge-base/README.md`
- `docs/knowledge-base/camera-spec.md`
- `docs/knowledge-base/lens-spec.md`
- `docs/knowledge-base/usb3-camera-guide.md`
- `docs/knowledge-base/project-tuning.md`
- `docs/knowledge-base/source-index.md`
- `docs/knowledge-base/source-extracts/*.md`
- `tools/extract_pdf_to_markdown.py`

实现：

- 人工整理型号专属技术参数、项目建议和高频操作
- 建立用户手册的章节/页码快速索引
- 为三份源 PDF 生成按 PDF 页码分隔的全文提取，保留源文件名、提取日期和免责声明
- 标出型号规格书优先于通用手册的位置
- 使用 Mermaid 描述项目数据流，避免依赖额外位图示意图

验证：所有知识库内部链接存在；关键数字与源 PDF 交叉核验；原始摘录包含每个 PDF 页码锚点。

## 任务 9：完整验证与交付

执行：

- 全部 pytest
- 合成角度精度统计
- CLI 单图和批处理冒烟测试
- 包安装/导入检查
- PDF 页面尺寸、文本和视觉渲染检查
- Markdown 链接和占位符扫描
- Git diff 和工作区状态检查

提交：

- 一个实施提交，包含代码、知识库、测试和生成的标定板
- 不包含源 PDF、MVS 安装包、厂商二进制、用户数据或临时渲染文件

实机验收在用户安装 MVS SDK 并提供相机连接后执行，重点验证设备枚举、Mono 8、软件触发、超时处理、30 次静态重复性和 500 帧稳定性。
