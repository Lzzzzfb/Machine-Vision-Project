狭缝与平台二维夹角测量 v0.3.1（Windows 64 位）
====================================================

一、启动
1. 解压整个 ZIP，不能只从压缩包中单独运行 EXE。
2. 双击“Launch.cmd”或“AngleMeasurement.exe”。
3. 本程序已包含 Python、PySide6、OpenCV、NumPy、MVS Python 接口及 MVS 用户态运行库，目标电脑无需安装 Python。

二、使用海康相机前的系统要求
1. Windows 10/11 64 位。
2. 目标电脑必须安装海康机器人官方 MVS 64 位软件或 USB3 相机驱动。USB 内核驱动不能通过普通免安装目录加载，因此未包含在本应用包内。
3. 建议使用已验证的 MVS 4.5.1 或兼容版本。
4. 若 MVS 客户端正在独占相机，请先在 MVS 中停止采集并关闭相机连接，再启动本程序。

三、默认文件
- 默认配方：configs\backlight_recipe.json
- 备用示例配方：configs\example_recipe.json
- 测量输出：data\output
- 设置和上次使用路径由 Windows 当前用户保存。

四、重要说明
- 当前交付包没有相机内参/畸变/平台姿态标定文件。未完成标定时，程序可以显示“投影诊断角”，但正式的高度补偿夹角会保持为空。
- 三个 ROI 的位置需要根据每次人工放置后的工件位置调整；配方中的坐标只是启动位置。
- 当前保留的是背光源亮狭缝测量方案，尚未加入环形 LED 暗线方案。
- 如 Windows 安全提示拦截未知发布者，请确认文件来源后选择“仍要运行”。当前 EXE 未做代码签名。

五、交付完整性
- ZIP 同目录的 .sha256.txt 文件记录 SHA-256，可用于检查传输后文件是否完整。
- MVS 用户态运行库的第三方许可见“MVS-THIRD-PARTY-NOTICES.txt”。
- Python 包版本见“PYTHON-DEPENDENCIES.txt”。
