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

适配层按以下顺序自动查找：

1. `HIKROBOT_MVS_PYTHON_PATH` 指定的 `MvImport` 目录。
2. MVS 安装程序创建的 `MVCAM_COMMON_RUNENV` 环境变量。
3. `HIKROBOT_MVS_ROOT` 指定的 MVS 安装根目录。
4. `Program Files` 下的常见安装目录。

本机安装在 `D:\MVS`，安装程序已设置 `MVCAM_COMMON_RUNENV=D:\MVS\Development`，因此无需额外配置。如果自动检测失败，可任选一种方式显式设置：

```powershell
$env:HIKROBOT_MVS_PYTHON_PATH='D:\MVS\Development\Samples\Python\MvImport'
# 或
$env:HIKROBOT_MVS_ROOT='D:\MVS'
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
- ExposureAuto = Off
- GainAuto = Off
- ExposureTime = 界面值
- Gain = 界面值

程序不复制或修改厂商 SDK 文件。若不同 MVS 版本的类名、函数签名或目录结构发生变化，只修改 `src/angle_measurement/acquisition/mvs.py`，不影响算法层。

## 本开发环境状态

2026-08-05 已在 `D:\MVS` 检测到 MVS 4.5.1，Python 模块加载成功，SDK 版本调用返回 `0x04050102`，设备枚举返回成功。验证时相机尚未连接，设备数为 0；接通相机后仍需完成单帧取流、连续 500 帧和曝光参数验收。
