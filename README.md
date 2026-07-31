# NegativeCutter

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/1055112915winter-ctrl/NegativeCutter-135)](https://github.com/1055112915winter-ctrl/NegativeCutter-135/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

> Lightroom Classic 插件与 standalone APP，自动识别 135 和单排 120 胶片扫描中的帧边界。

---

## 功能

- **自动帧检测**：识别胶片帧之间的间隙，无需手动标记
- **批量处理**：同时处理多张照片，适合整卷胶片Workflow
- **虚拟副本**：为每帧创建独立虚拟副本，保留原始扫描文件
- **精确裁剪**：基于图像分析生成像素级精确的裁剪框
- **边界清理**：0.3% 微小内收，消除扫描脏边和bleed
- **开箱即用**：内置检测引擎，无需安装 Python 或 pip
- **SubIFD DNG 解码**：直接解析 DNG RAW 像素，无需 rawpy
- **严格 3:2 比例**：middle frames 自动锁定精确比例
- **120 各画幅**：支持单排 645、6×6、6×7、6×8、6×9
- **旋转安全**：不可信或超过 3° 的角度不会写入最终裁切
- **单一检测核心**：APP 与 Lightroom 使用同一份算法源码
- **边缘白边消除**：收紧-only 约束 + 安全边距
- **赞助支持**：内置赞赏码入口，支持插件持续开发
- **问题反馈**：一键提交使用反馈

## 系统要求

- macOS 14.0+；下载与设备匹配的 `arm64` 或 `x86_64` 安装器。只有 Release 清单明确标为 `universal2` 时才可混用架构。
- Adobe Lightroom Classic 10.0+
- 135 或单排 120 胶片扫描长条图（DNG / TIFF）

> **注意**：120 仅支持单排扫描；多排/网格、110 等规格尚未支持。

## 安装

### 一键安装（推荐）

1. 从 [Releases](https://github.com/1055112915winter-ctrl/NegativeCutter-135/releases) 下载匹配架构、已公证的 `.pkg`
2. 双击安装器并完成安装；安装前会执行引擎自检
3. 重启 Lightroom Classic
4. 菜单：`文件 → 增效工具管理器`，确认状态为「正在运行」

若 Release 仅提供 ZIP，按 [插件安装指南](NegativeCutter-135.lrplugin/INSTALL.md) 使用其顶层 `install.sh`；ZIP 不是 stapled 安装器，不要手动清除 quarantine。

### 手动安装

见 [INSTALL.md](INSTALL.md)

## 使用

### 单次检测

1. 在 Lightroom Classic **图库模块**或**修改照片模块**中选中扫描文件
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 检测胶片帧`
3. 选择胶片画幅；自动检测画幅时帧数默认自动，也可手动指定
4. 点击「开始检测」

### 批量处理

1. 选中多张照片
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 批量处理`
3. 保持自动检测，或手动指定整批使用的帧数
4. 点击「开始批量处理」

### 快捷键（macOS 手动设置）

Lightroom SDK 不支持插件内置全局快捷键。通过 macOS 系统设置手动绑定：

**系统设置 → 键盘 → 键盘快捷键 → App 快捷键**

- `文件->增效工具额外命令->NegativeCutter->检测胶片帧`
- `文件->增效工具额外命令->NegativeCutter->批量处理`

## 技术架构

```
Lightroom Classic (Lua SDK)
    ↓ 缩略图路径
negativecutter_core (Python + NumPy + Pillow)
    ↓ JSON 结果
Lightroom (创建虚拟副本 + 应用裁剪)
```

检测引擎通过 PyInstaller 打包为独立可执行文件，无需用户安装 Python 环境。

维护者请先阅读 [架构](docs/ARCHITECTURE.md)、[检测管线](docs/DETECTION_PIPELINE.md)、
[测试](docs/TESTING.md)、[新增画幅](docs/ADDING_FILM_FORMATS.md) 与
[仓库卫生](docs/REPOSITORY_HYGIENE.md)。

## 故障排除

| 问题 | 解决方式 |
|------|----------|
| "检测引擎不存在" | 确认插件文件夹中包含 `NegativeCutter` 可执行文件 |
| "检测失败 / 未检测到帧" | 检查是否选中了图片；查看日志 `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log` |
| 检测帧数不正确 | 调整预期帧数；黑白负片效果最好 |

## 开发

```bash
# 本地开发环境
pip install numpy pillow

# 非 Computer Use 全部验证（确定性 + 真实素材）
scripts/verify_non_computer_use.sh all

# 只跑确定性门禁
scripts/verify_non_computer_use.sh quick

# 仅运行真实素材门（需要本地 test_files/ 或 FILMCROP_FIXTURE_ROOT）
scripts/verify_non_computer_use.sh fixtures
```

这套流程只覆盖源码、真实素材和本地静态检查，不包含 Lightroom 真实界面验收、Standalone 发布包重建或插件发布 staging。

## 开源协议

本项目采用 [GPL v3](LICENSE) 许可证开源。

使用的第三方库：
- [NumPy](https://numpy.org/) — BSD-3-Clause
- [Pillow](https://python-pillow.org/) — HPND

## 作者

**李冬天** — 小红书 [@李冬天 SimplyWinter](https://www.xiaohongshu.com)

基于 [FilmCrop](https://github.com/JanneM/Filmcrop)（GPL v3）开发。
