# FilmCrop — Lightroom 胶片扫描自动裁剪插件（精简版）

自动识别长条扫描胶片中的单帧，并创建带精确裁剪的虚拟副本。

## 安装

1. 打开 Lightroom Classic
2. 菜单: `文件 > 增效工具管理器`
3. 点击 `添加`，选择 `FilmCrop_Clean.lrplugin` 文件夹
4. 确保插件已启用

## 使用

### 单次检测（单张照片）

1. 在**修改照片模块**中选中扫描文件
2. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 检测胶片帧`
3. 输入预期帧数（默认 6，填 0 自动检测）
4. 点击「开始检测」，自动创建虚拟副本并应用裁剪

### 批量处理（多张照片）

1. 在**修改照片模块**中选中多张照片
2. 菜单: `文件 > 增效工具额外命令 > FilmCrop > 批量处理`
3. 输入预期帧数，所有照片使用相同帧数
4. 点击「开始批量处理」，无预览直接创建虚拟副本

### 快捷键（macOS 手动设置）

Lightroom SDK 不支持插件内置全局快捷键。如需快捷操作，请通过 macOS 系统偏好设置手动绑定：

**系统设置 → 键盘 → 键盘快捷键 → App 快捷键**
1. 点 `+`，应用程序选「Adobe Lightroom Classic」
2. 菜单标题填完整路径（精确匹配，包括 `->`）：
   - `文件->增效工具额外命令->FilmCrop->检测胶片帧`
   - `文件->增效工具额外命令->FilmCrop->批量处理`
3. 按你想要的组合键（建议 `⌘M` 和 `⌘⇧M`）

> 如果匹配不上，尝试在菜单标题前加 3 个空格：`   检测胶片帧`。部分 macOS 版本和 Lightroom 语言包需要这个前缀才能正确命中子菜单项。

## 文件结构

```
FilmCrop_Clean.lrplugin/
├── filmcrop/              # Python 核心检测包
│   ├── detector.py        # 帧检测引擎
│   ├── export.py          # JSON/XMP/图像导出
│   └── api.py             # FastAPI HTTP 服务器（可选）
├── detect_thumb.py        # CLI 入口
├── json.lua               # 内嵌 JSON 解码器
├── Info.lua               # 插件信息 + 菜单注册
├── DetectFrames.lua       # 单次检测流程
├── BatchProcess.lua       # 批量处理流程
├── ProcessAgent.lua       # 共享核心：Python 调用 + 方向对齐
├── ApplierAgent.lua       # 裁剪应用
├── ThumbnailAgent.lua     # 缩略图提取
├── ImportAgent.lua        # XMP/JSON 导入（保留代码，当前未注册菜单）
└── tests/                 # 测试与验证工具
```

## 配置

### 预期帧数

- 35mm 标准: 6 帧
- 半格相机: 12 帧
- 其他格式: 相应调整

### 检测参数

`cleanup_scale` 控制帧间隙宽度，当前固定为 `0.50`（由 `ProcessAgent.lua` 传入），在间隙可见性与边界精确度之间取得平衡。

## 故障排除

### "找不到 Python 解释器"
- `ProcessAgent.lua` 按以下顺序查找 Python 3：`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3` → `/usr/bin/python3` → `/usr/local/bin/python3` → `/opt/homebrew/bin/python3` → `python3`
- 确保 Python 3 已安装: `python3 --version`

### "检测失败 / 未检测到帧"
- 检查 `filmcrop/detector.py` 是否存在
- 查看 Lightroom 日志: `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/FilmCrop.log`
- 确认当前在**修改照片模块**运行（`applyDevelopSettings` 在图库模块中对虚拟副本无效）

### "DNG 读取失败"
- 安装 rawpy: `pip install rawpy`
- DNG 文件需包含去马赛克后的 RGB 数据

### 检测帧数不正确
- 调整预期帧数设置
- 检测算法基于亮度峰值，黑白负片效果最好

## 版本历史

### v2.2.0 (2026-05-05)
- **UI 精简**: 菜单从 10 个缩减至 2 个，只保留核心检测与批量处理
- **流程优化**: 移除预览对话框，输入帧数后直接检测并创建虚拟副本
- **快捷键**: 移除 Info.lua 中不支持的 `shortcut` 字段，改为文档引导用户通过 macOS 系统偏好设置手动绑定
- **检测改进**: plateau-walk gap 边界 + 长边对称回退 + confidence-based mirroring
- **解析修复**: `parseJSON` 改用 `json.decode`，增加 stderr 前缀剥离防御

### v2.0.0 (2026-04-28)
- **架构重构**: 核心算法提取为独立 Python 包 `filmcrop`
- **独立 GUI**: PyQt6 图形界面（可选）
- **HTTP API**: FastAPI 本地服务器（可选）
- **三种 Lightroom 集成**: XMP 边车 / HTTP API / JSON 监视（v2.2.0 起精简为纯本地检测）

### v1.5.1 (2026-04-18)
- 方向对齐坐标污染修复
- 缩略图分辨率不足时用原图补长边检测
- 扫描边缘自动检测

### v1.0.0 (2026-03-26)
- 初始版本
- 水平投影峰值检测
- 批量处理支持
