# 海康 MVS SDK 配置

## 安装检查

1. 安装 MVS 客户端和 SDK，并勾选 USB 3.0 驱动。
2. 用 Micro USB3.0 B 型线缆直连电脑 USB3 接口，不使用普通 USB2 线或无源转接头。
3. Windows 设备管理器中确认存在 `USB3 Vision Camera`。
4. 打开 MVS 客户端，确认能枚举、连接并连续预览 MV-CS050-10UC。

## Python 模块路径

适配层需要厂商示例中的 `MvCameraControl_class.py`。常见目录之一为：

```text
C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport
```

如果安装路径不同，在启动程序前设置：

```powershell
$env:HIKROBOT_MVS_PYTHON_PATH='D:\your-mvs-sdk\Development\Samples\Python\MvImport'
```

检查模块是否可加载：

```powershell
python -c "from angle_measurement.acquisition.mvs import load_mvs_module; print(load_mvs_module())"
```

检查相机连接与软件触发：

```powershell
python -c "from angle_measurement.acquisition import MvsCameraSource; s=MvsCameraSource(); s.open(); f=s.read(); print(f.image.shape, f.metadata); s.close()"
```

## 适配层设置

连接时程序设置：

- PixelFormat = Mono8
- TriggerMode = On
- TriggerSource = Software
- ExposureTime = 界面值
- Gain = 界面值

程序不复制或修改厂商 SDK 文件。若不同 MVS 版本的类名、函数签名或目录结构发生变化，只修改 `src/angle_measurement/acquisition/mvs.py`，不影响算法层。

## 本开发环境状态

开发时尚未在常见安装目录和下载目录发现 `MvCameraControl_class.py`，因此已经完成“SDK 缺失时的诊断”和离线模式测试，实机枚举、取流和 500 帧稳定性仍需在 SDK 安装后验收。
