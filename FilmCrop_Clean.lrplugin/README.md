# FilmCrop — Standalone Engine + Lightroom Plugin

FilmCrop 胶片扫描自动裁剪工具。v2.0.0 重构为**独立引擎 + 可选 Lightroom 插件**双层架构。

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                 独立引擎 (Standalone)                  │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │  PyQt6 GUI  │───▶│  detector   │───▶│  export  │ │
│  │  (可视化)    │    │  (帧检测)    │    │(JSON/XMP)│ │
│  └─────────────┘    └─────────────┘    └──────────┘ │
│         │                                           │
│         ▼                                           │
│  ┌─────────────┐                                    │
│  │  FastAPI    │  ← 本地 HTTP API (127.0.0.1:8765) │
│  └─────────────┘                                    │
└──────────────────────────────────────────────────────┘
                          │
                          ▼ 三种集成方式
┌──────────────────────────────────────────────────────┐
│              Lightroom 插件 (可选)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ XMP 边车导入 │  │ HTTP API    │  │ JSON 监视   │  │
│  │ ImportXMP   │  │ ImportHTTP  │  │ ImportWatch │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                      │
│  保留原有功能: 检测胶片帧 / 批量处理 / 预览编辑器        │
└──────────────────────────────────────────────────────┘
```

## 安装

### Python 依赖

```bash
pip install numpy Pillow
# 可选 (DNG 支持)
pip install rawpy
# 可选 (API 服务器)
pip install fastapi uvicorn
# 可选 (GUI)
pip install PyQt6
```

### Lightroom 插件

1. 打开 Lightroom Classic
2. 菜单: `文件 > 增效工具管理器`
3. 点击 `添加`，选择 `FilmCrop_Clean.lrplugin` 文件夹
4. 确保插件已启用

## 使用方式

### 方式一：独立 GUI（推荐）

不依赖 Lightroom，直接处理 TIFF/DNG/JPEG/PNG。

```bash
cd FilmCrop_Clean.lrplugin
python -m filmcrop.gui
```

操作步骤：
1. `文件 > 打开` 选择扫描图像（支持 .tif/.tiff/.jpg/.png/.dng）
2. 在右侧面板设置**预期帧数**（0 = 自动检测）
3. 点击 **检测帧 (Detect)** 或按 `Ctrl+D`
4. 在画布上**拖拽红色/绿色边界线**微调帧位置
5. 右侧面板精确调整像素坐标（Top/Bottom/Left/Right）
6. 导出：
   - `文件 > 导出 JSON 边车` (`Ctrl+J`)
   - `文件 > 导出 XMP 边车` (`Ctrl+Shift+J`)
   - `文件 > 导出裁切图像`

快捷键：
- `Ctrl+O` — 打开图像
- `Ctrl+D` — 检测帧
- `Ctrl+J` — 导出 JSON
- `Ctrl+Shift+J` — 导出 XMP
- `Ctrl+Z` / `Ctrl+Shift+Z` — 撤销/重做
- `Ctrl+0` — 重置缩放
- 滚轮 — 缩放画布

### 方式二：CLI（向后兼容）

```bash
python detect_thumb.py <image_path> [--frames N] [--cleanup-scale X.X] [--original <path>]
```

输出 JSON 到 stdout，与 v1.x 格式完全兼容。

### 方式三：HTTP API

从 GUI 菜单 `工具 > 启动 API 服务器`，或独立运行：

```bash
python -m filmcrop.api
# 默认监听 http://127.0.0.1:8765
```

端点：
- `GET  /health`  — 服务状态
- `POST /analyze` — 检测帧（参数: `image_path`, `expected_frames`）
- `POST /crop`    — 裁切导出（参数: `image_path`, `frames[]`, `output_dir`）

### 方式四：Lightroom 插件

#### 原有功能（本地检测）

1. 在**修改照片模块**中选中扫描文件
2. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 检测胶片帧`
3. 在预览对话框确认/调整边界
4. 自动生成虚拟副本

#### 新：导入独立引擎结果

**XMP 边车导入**：
1. 在图库模块选中原始图像
2. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 导入 FilmCrop XMP...`
3. 选择独立引擎导出的 `.filmcrop.xmp` 文件
4. 自动为每帧创建虚拟副本并应用裁剪

**HTTP API 检测**：
1. 确保独立引擎 GUI 已启动且 API 服务器运行
2. 选中扫描文件
3. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 通过 FilmCrop 引擎检测...`
4. 输入 API 地址（默认 `http://localhost:8765`）
5. 检测由独立引擎执行，结果自动导入 Lightroom

**JSON 文件监视**：
1. 选中原始图像
2. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 监视 FilmCrop JSON...`
3. 选择独立引擎导出的 `.filmcrop.json` 文件
4. 插件每 2 秒轮询文件更新，自动同步到虚拟副本

## 文件结构

```
FilmCrop_Clean.lrplugin/
├── filmcrop/                    # Python 核心包
│   ├── __init__.py
│   ├── __main__.py              # python -m filmcrop.gui 入口
│   ├── detector.py              # 帧检测引擎
│   ├── export.py                # JSON/XMP/图像导出
│   ├── api.py                   # FastAPI HTTP 服务器
│   └── gui/                     # PyQt6 GUI
│       ├── __init__.py
│       ├── image_view.py        # 图像画布
│       ├── frame_item.py        # 可拖拽帧边界
│       └── main_window.py       # 主窗口
│
├── detect_thumb.py              # CLI 入口 (向后兼容)
│
├── DetectFrames.lua             # 原有: Lightroom 本地检测
├── BatchProcess.lua             # 原有: 批量处理
├── Editor.lua                   # 原有: 帧编辑器
├── PreviewDialog.lua            # 原有: 预览对话框
│
├── ImportAgent.lua              # 新增: 三种导入模式的统一代理
├── ImportXMP.lua                # 新增: XMP 边车导入入口
├── ImportHTTP.lua               # 新增: HTTP API 检测入口
├── ImportWatch.lua              # 新增: JSON 监视入口
│
├── Info.lua                     # 插件信息 (v2.0.0)
├── Settings.lua                 # 设置对话框
└── README.md                    # 本文件
```

## 配置

### 预期帧数

默认 6 帧，可根据需要调整：
- 35mm 标准: 6 帧
- 半格相机: 12 帧
- 其他格式: 相应调整

### 坐标系

所有坐标基于**原始像素尺寸**，相对坐标 = 像素 / 图像尺寸。方向适配由导入端处理，确保 Lightroom 与独立引擎一致。

## 故障排除

### "找不到 Python 解释器"
- 检查 `Settings.lua` 中的 Python 路径
- 确保 Python 3 已安装: `python3 --version`

### "检测失败"
- 检查 `filmcrop/detector.py` 是否存在
- 查看 Lightroom 日志: `~/Library/Logs/Adobe/Lightroom/FilmCrop.log`

### "DNG 读取失败"
- 安装 rawpy: `pip install rawpy`
- DNG 文件需包含去马赛克后的 RGB 数据

### 检测帧数不正确
- 调整预期帧数设置
- 检测算法基于亮度峰值，黑白负片效果最好

### API 连接失败
- 确认独立引擎 GUI 中 `工具 > 启动 API 服务器` 已点击
- 检查防火墙是否拦截 8765 端口
- 默认只允许 localhost 访问

## 支持格式

| 格式 | 独立引擎 | Lightroom 插件 |
|---|---|---|
| TIFF/TIF | 原生 | 原生 |
| DNG | 需 rawpy | 原生 |
| JPEG/JPG | 原生 | 原生 |
| PNG | 原生 | 原生 |

## 版本历史

### v2.0.0 (2026-04-28)
- **架构重构**: 核心算法提取为独立 Python 包 `filmcrop`
- **独立 GUI**: 新增 PyQt6 图形界面，支持拖拽边界调整
- **DNG 原生支持**: 通过 rawpy 直接读取 DNG，跳过 Lightroom 预览层
- **HTTP API**: FastAPI 本地服务器，支持外部调用
- **三种 Lightroom 集成**: XMP 边车 / HTTP API / JSON 监视
- **撤销/重做**: GUI 中 Ctrl+Z 支持 50 步历史
- **导出增强**: JSON 边车、XMP 边车、高质量 TIFF 裁切

### v1.5.1 (2026-04-18)
- 方向对齐坐标污染修复
- 缩略图分辨率不足时用原图补长边检测
- 扫描边缘自动检测

### v1.0.0 (2026-03-26)
- 初始版本
- 水平投影峰值检测
- 批量处理支持
