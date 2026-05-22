# NegativeCutter-135

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/negativecutter/lightroom)](https://github.com/negativecutter/lightroom/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

> Lightroom Classic 插件，自动识别 135 胶片扫描长条图中的单帧边界，并创建带精确裁剪的虚拟副本。

---

## 功能

- **自动帧检测**：识别胶片帧之间的间隙，无需手动标记
- **批量处理**：同时处理多张照片，适合整卷胶片Workflow
- **虚拟副本**：为每帧创建独立虚拟副本，保留原始扫描文件
- **精确裁剪**：基于图像分析生成像素级精确的裁剪框
- **边界清理**：0.3% 微小内收，消除扫描脏边和bleed
- **开箱即用**：内置检测引擎，无需安装 Python 或 pip

## 系统要求

- macOS（Intel / Apple Silicon）
- Adobe Lightroom Classic 10.0+
- 135 胶片扫描长条图（DNG / TIFF）

> **注意**：当前仅适配 135 胶片规格。120、110 等规格尚未支持。

## 安装

### 一键安装（推荐）

1. 从 [Releases](https://github.com/negativecutter/lightroom/releases) 下载最新版 `NegativeCutter-135-v2.4.0.zip`
2. 解压 ZIP 文件
3. 双击运行 `install.sh`
4. 脚本会自动检测 Lightroom 插件目录并安装
5. 重启 Lightroom Classic
6. 菜单：`文件 → 增效工具管理器`，确认状态为「正在运行」

### 手动安装

见 [INSTALL.md](INSTALL.md)

## 使用

### 单次检测

1. 在 Lightroom Classic **图库模块**或**修改照片模块**中选中扫描文件
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 检测胶片帧`
3. 输入预期帧数（默认 6，填 0 自动检测）
4. 点击「开始检测」

### 批量处理

1. 选中多张照片
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 批量处理`
3. 输入预期帧数
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
NegativeCutter 检测引擎 (Python + NumPy + Pillow)
    ↓ JSON 结果
Lightroom (创建虚拟副本 + 应用裁剪)
```

检测引擎通过 PyInstaller 打包为独立可执行文件，无需用户安装 Python 环境。

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

# 重新打包检测引擎
pyinstaller NegativeCutter.spec
```

## 开源协议

本项目采用 [GPL v3](LICENSE) 许可证开源。

使用的第三方库：
- [NumPy](https://numpy.org/) — BSD-3-Clause
- [Pillow](https://python-pillow.org/) — HPND

## 作者

**李冬天** — 小红书 [@李冬天 SimplyWinter](https://www.xiaohongshu.com)

基于 [FilmCrop](https://github.com/JanneM/Filmcrop)（GPL v3）开发。
