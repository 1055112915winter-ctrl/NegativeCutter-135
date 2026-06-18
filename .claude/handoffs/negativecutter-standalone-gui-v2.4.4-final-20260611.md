# NegativeCutter Standalone GUI · v2.4.5 Handoff

> 2026-06-11 起始，2026-06-19 最终更新 · 当前独立桌面版 handoff。包含 PyInstaller onedir、签名、GUI 美化、手势简化、Code Review 硬化、版本号展示，以及 16-bit 多通道图像显示修复。

## 2026-06-19 v2.4.5 变更总览

### 1. 下拉框排版修复
- **问题**：导出对话框中格式/色彩空间下拉框文字被压缩截断
- **修复**：`export_dialog.py` QComboBox 添加 `setSizeAdjustPolicy(AdjustToMinimumContentsLengthWithIcon)` + `setMinimumWidth`
- **样式**：`style_sheet.py` 新增 `QComboBox QAbstractItemView` / `QAbstractItemView::item` 样式

### 2. 画布交互最终方案：纯键盘+按钮缩放
经历多轮迭代（手动 translate / wheelEvent phase 过滤 / NativeGesture 拦截）均因 macOS 触控板惯性滚动造成回弹、或与 ScrollHandDrag 冲突导致拉拽感，**最终方案**：
- **平移**：`ScrollHandDrag`（Qt 原生鼠标拖拽），不拦截任何触控板/鼠标滚轮事件
- **缩放按钮**：画布左下角悬浮 `+` / `−`，半透明深色风格
- **键盘缩放**：`]` / `+` / `=` 放大，`[` / `-` 缩小，`Ctrl+0` 重置
- **缩放约束**：0.05x – 8.0x，`_apply_zoom_factor` 统一夹紧，带浮点误差同步
- 已删除：`event()` (NativeGesture)、`wheelEvent()` 自定义逻辑、手动 mousePressEvent/mouseMoveEvent/mouseReleaseEvent

### 3. 检测进度条
- `_do_detect` 开始显示不确定进度条（marquee），检测期间禁用按钮
- `finally` 块确保关闭进度条并恢复按钮

### 4. 图标安全加固（`NegativeCutter.spec`）
- 移除跨 worktree icon fallback，仅接受 canonical `APP/NegativeCutter.icns`
- 缺失时 `raise FileNotFoundError`
- `build_app.sh` 在 PyInstaller 前强制运行 `generate_icns.py` + 存在性检查

### 5. Code Review 硬化（4 bugs fixed）
| # | 级别 | 文件 | 修复 |
|---|------|------|------|
| 1 | Critical | `detector.py:1683` | `_auto_detect_frames` 新增 `best_result is None` guard，fallback 到 `ef=6` 的 `_analyze_single_config` |
| 2 | Medium | `image_view.py:65` | `__init__` 显式声明 `_last_pinch_value = 0.0`（最终方案中已随手势代码移除） |
| 3 | Medium | `image_view.py:313` | `_apply_zoom_factor`：new_zoom 被边界夹住后计算 `effective = new_zoom / self._zoom`，保证 `scale()` 和 `_zoom` 同步 |
| 5 | Medium | `frame_item.py` + `main_window.py` | 提取 `MIN_FRAME_SIZE = 20` 到 `frame_item.py`，`main_window.py` import 使用，移除重复定义 |

### 6. 版本号展示 + 报错强化
- `main_window.py` `from filmcrop import __version__`
- 窗口标题 `"NegativeCutter v2.4.5"`
- 状态栏 `"NegativeCutter v2.4.5 — 就绪，请打开扫描图像文件"`
- 4 个错误对话框（检测失败 / API 未安装 / 导出失败 / 图像读取失败）均带版本号
- 调优记录 `"version": __version__` 动态引用
- `build_app.sh` / `package_app.sh` 均支持 `--version` 标志，动态读取 `filmcrop.__version__`
- 完成输出含版本号和 zip 打包命令模板
- 新增测试 `test_build_script_exposes_version_flag` / `test_main_window_displays_version`

### 7. 版本号同步
- `APP/filmcrop/__init__.py`：2.4.4 → 2.4.5
- `NegativeCutter-135.lrplugin/filmcrop/__init__.py`：2.4.4 → 2.4.5
- `NegativeCutter-135.lrplugin/Info.lua`：2.4.3 → 2.4.5

### 8. 验证
- GUI 测试：23/23 通过
- 打包契约：6/6 通过（含新增 2 个版本号测试）
- Fresh rebuild + codesign 通过
- 最新产物：`APP/NegativeCutter.app`（arm64，v2.4.5）

### 9. 构建与分发
```bash
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop/APP
bash scripts/package_app.sh
zip -r -y NegativeCutter-v2.4.5-macOS-arm64.zip NegativeCutter.app
```

### 10. 当前已知边界
- **触控板缩放不可用**：macOS 触控板捏合/惯性滚动与 Qt 手势管道冲突，经历 6 轮迭代未解决，当前回退到纯按钮+键盘缩放。未来可考虑用 QPinchGesture（需额外 setup）或 platform-native 方案。
- **仅 arm64**：Intel Mac 不可用，universal2 构建需提前装好 fat binary 依赖。
- **未公证**：首次启动需 `右键 → 打开` 绕过 Gatekeeper。

## 2026-06-18 macOS 应用图标统一增量

- 修复截图中 Finder/Get Info 仍显示旧胶片框+斜线图标的问题。
- 根因不是新版设计缺失：`logo.py` 与 `generate_icns.py` 已是对称菱形/镜头标记，但 `APP/NegativeCutter.icns` 不存在，spec 静默从旧 `.claude/worktrees/` 取到了过期 ICNS。
- 当前构建契约：
  - `APP/scripts/build_app.sh` 在 PyInstaller 前强制运行 `generate_icns.py`
  - 生成后检查 `APP/NegativeCutter.icns` 必须存在
  - `APP/NegativeCutter.spec` 只接受本地 canonical ICNS；缺失时直接失败，不再跨 worktree 回退
- 已生成并纳入源码的 canonical `APP/NegativeCutter.icns`：对称双菱形、中心镜头、深色圆角底板，无旧斜线或胶片孔。
- TDD 证据：新增打包契约先失败于“构建未生成图标”和“spec 仍有 worktree 回退”，最小实现后 `4/4` 通过。
- Fresh 验证：
  - GUI 测试 `23/23` 通过
  - package contract `4/4` 通过
  - `APP/scripts/package_app.sh` fresh rebuild 通过
  - 源 ICNS 与 `.app` 内 ICNS SHA-256 均为 `2c3bcb30d409ffad4283ba0ec8b73b34a6b0d9582cdedbfbe5613d09f0ae7ac0`
  - `CFBundleIconFile` 为 `NegativeCutter.icns`
  - `codesign --verify --deep --strict` 通过
  - 最新 `.app` 时间戳：`2026-06-18 22:37:10`
- Finder 可能短暂显示系统缓存的旧缩略图；bundle 实际资源已替换，Quick Look 对 source/bundle ICNS 的渲染均确认是新版图标。

## 2026-06-18 sRGB ICC 与无损裁切导出增量

- DNG 解码现显式使用 `rawpy.ColorSpace.sRGB` 与 `output_bps=16`；对 `raw0014.dng`，显式参数与此前默认参数生成的 16-bit 数组已验证完全一致，因此没有新增像素转换。
- DNG 临时 TIFF 现通过 Pillow/ImageCms 生成并嵌入标准 sRGB ICC；裁切导出沿用 16-bit 数组切片路径，并原样复制 ICC。
- 真实 `raw0014.dng` 源路径核对：导出为 `uint16 RGB`，裁切区域像素逐值一致，临时/导出 TIFF 的 ICC 均为同一份 588-byte profile。
- 普通 TIFF 继续保持像素优先策略：已有 ICC 原样保留；无 ICC 时不假定 sRGB、不添加 profile，GUI 显示 `色彩空间未知`。
- 现有“保存坐标数据”按钮复用为 DNG sidecar 入口：加载 DNG 时文案为“导出原始 DNG 坐标”，只写 `.negativecutter.json`，不复制或修改 DNG；其他格式仍显示原文案。
- TDD 证据：新测试先分别失败于缺少 `output_color`、DNG 临时 TIFF 无 ICC、无标签 TIFF 被误报为 sRGB、DNG 按钮未改名；最小实现后全部转绿。
- Fresh 验证：
  - GUI 测试 `23/23` 通过
  - 打包契约 `2/2` 通过
  - `APP/scripts/package_app.sh` fresh rebuild 通过
  - `codesign --verify --deep --strict --verbose=2 APP/NegativeCutter.app` 通过
  - 最新 `.app` 时间戳：`2026-06-18 22:13:09`
- 未执行真实 `.app` 点击式人工验收；本轮证据覆盖源码真实 DNG 链路、自动化 GUI 套件、fresh 打包和严格验签。

## 2026-06-18 DNG 观感与真实 `.app` 验收刷新

- 本轮不是再修“有没有彩色”，而是修 DNG 预览被 `rawpy` 渲染得过于中性、看起来像“色罩变淡”的问题。
- 当前最小实现改动：
  - [APP/filmcrop/detector.py](APP/filmcrop/detector.py) 的 `load_dng_preview_array()` 不再强行传 `use_camera_wb=True` 与 `no_auto_bright=True`
  - 现仅保留 `raw.postprocess(output_bps=16)`，继续走 `rawpy` 的 16-bit RGB 预览链路，但让观感更接近 DNG 内嵌预览 / LR
- 当前新增回归覆盖：
  - `tests/test_gui_dng_color.py` 由 `2/2` 扩展到 `3/3`
  - 新增真实 `raw0014.dng` warmth 回归：要求 `rawpy` 预览与 DNG 内嵌预览的 RGB 比例偏差不要过大
- 当前最新自动化证据：
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=APP python3 -m unittest discover -s tests -p 'test_gui_dng_color.py' -v` → `3/3`
  - `QT_QPA_PLATFORM=offscreen PYTHONPATH=APP python3 -m unittest discover -s tests -p 'test_gui_*.py' -v` → `20/20`
  - `APP/scripts/package_app.sh` → fresh rebuild + strict signing 通过
- 当前最新源码级 DNG 观感证据：
  - 真实 `test_files/raw0014.dng` 仍走 `rawpy`，位深 `16`
  - `rawpy` 预览与 DNG 内嵌预览的 RGB 比例偏差 `ratio_delta` 已降到 `0.3911`
  - 之前核对到的旧实现对比值是 `0.6871`，说明当前观感已明显从“过度中性”往 LR 靠近
- 当前最新真实 `.app` 点击式验收：
  - 打包产物 `APP/NegativeCutter.app` 时间戳：`2026-06-18 20:40:59`
  - 真实打开 `test_files/raw0014.dng` 成功，状态栏显示：`raw0014.dng  28859×3128  16bit (rawpy)`
  - 真实点击检测成功，状态栏显示：`检测到 6 帧  耗时 1.40s`
  - 真实点击导出成功，状态栏显示：`已导出 6 张图像到 /Users/winter/Documents/临时拷贝/Claude Code/filmcrop/test_files/cropped`
  - 本轮新导出文件前缀：`negativecutter_dng_1mx_rv2y_frame_*.tif`
  - 真实导出 TIFF 源码级核对：
    - 共 `6` 张
    - `frame_01` → `RGB`，`(16,16,16)`，`4680x3041`
    - `frame_06` → `RGB`，`(16,16,16)`，`4587x3041`
    - `tifffile.imread(...)` 读取为 `uint16`，三通道不相等，不是灰度伪装
- 当前已关闭的旧边界：
  - “最终 `.app` 尚未再次通过 macOS GUI 完整点击 DNG 打开 → 检测 → 导出” 这一项，现在对 `raw0014.dng` 已经实际跑通
- 当前仍保留的边界：
  - DNG 导出链路目前仍未写入 ICC profile；新导出的 `negativecutter_dng_1mx_rv2y_frame_*.tif` 核对结果仍是 `icc False`
  - 因此若后续还要继续追“和 LR 一模一样的观感”，下一个优先项应是 ICC / 色彩空间策略，而不是灰度链路
  - 尚未对用户自己那张原始彩负文件做同文件 GUI 复测；当前实机验收夹具仍是 `raw0014.dng`

## 2026-06-15 现态刷新

- 新增确认并修复一个当时未覆盖到的 DNG 彩色链路缺口：
  - `raw0014.dng` 之前虽然能打开并检测，但 DNG 预览临时 TIFF 仍被写成灰度，导致 GUI 画布看起来黑白，导出结果也跟着变成 `8-bit gray`
  - 当前已改为：`rawpy` 可用时用 `postprocess(..., output_bps=16)` 生成 RGB 预览；临时 TIFF 写为 `16-bit RGB`；DNG 导出复用这条彩色临时 TIFF 路径
- 当前最新已确认 DNG 彩色证据：
  - `tests/test_gui_dng_color.py` 新增 `2/2` 回归测试
  - 真实 `test_files/raw0014.dng` 源码级核对：
    - 预览临时 TIFF → `RGB`，`(16,16,16)`，尺寸 `28859x3128`
    - 首帧导出 TIFF → `RGB`，`(16,16,16)`，尺寸 `4680x3041`
- 当前实现状态不再有新的代码待补；本轮核对后，结论仍是“代码与打包已完成，最终剩一个 GUI 点击式终验边界”。
- 当前最新已确认产物仍是 `APP/NegativeCutter.app`，时间戳 `2026-06-15 03:01:14`，arm64，`codesign --verify --deep --strict` 通过。
- 当前最新已确认自动化/源路径证据：
  - `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_gui_*.py' -v` → `19/19`
  - `python3 -m unittest discover -s tests -p 'test_package_app.py' -v` → `2/2`
  - `APP/scripts/package_app.sh` → fresh rebuild + strict signing 通过
  - 真实 TIFF 源路径验证仍保持：
    - `test_files/Untitled (3).tif` → `16bit`，`6` 个 review frames，导出首帧 `5224x2716` 16-bit RGB
    - `test_files/未标题(1).tif` → `16bit`，`6` 个 review frames，导出首帧 `5133x2598` 16-bit RGB
- 当前唯一未验证项保持不变：
  - 修复后的最终 `.app` 尚未再次通过 macOS GUI 完整点击“打开文件 → 检测 → 导出 → 回看导出结果”。
  - 未验证原因仍是外部执行额度门禁拒绝第二次 GUI 启动，不是应用自身崩溃。
- 门禁恢复后的最短复验命令与检查点：

```bash
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop
open -n APP/NegativeCutter.app
magick identify /tmp/<导出目录>/*.tif
```

- 点击验收时只看这 5 个点：
  1. 打开 `test_files/Untitled (3).tif`
  2. 状态栏显示 `16bit`
  3. 检测后出现 `6` 个框，并有低置信度提示
  4. 成功导出 TIFF
  5. 导出结果 `identify` 为 16-bit RGB，且回载后仍为彩色

## 2026-06-15 03:01 可用性修复增量

### 1. 真实 GUI 复现并修复的缺陷
- 用 Computer Use 在旧包中打开 `test_files/Untitled (3).tif`，确认彩色画布可见，但复现了三个遗漏：
  - 16-bit RGB TIFF 状态栏误报为 `8bit`
  - 预期 6 帧时 detector 找到完整间隙，但置信度熔断后 GUI 显示 `0 帧`
  - TIFF 裁切导出把 16-bit RGB 静默降为 8-bit RGB
- 当前修复：
  - `main_window.py` 从 TIFF `BitsPerSample` 读取真实位深
  - `detector.py` 新增默认关闭的 `include_review_frames`；只有 GUI 显式请求时才返回低置信度候选框，Lightroom/API 默认安全行为不变
  - GUI 对低置信度结果显示 6 个可编辑框，并提示“低置信度，请检查并调整”
  - `export.py` 使用 vendored `tifffile 2024.8.30` 保存 16-bit RGB TIFF，保留 ICC，并按 TIFF orientation 1-8 对齐 GUI 坐标

### 2. 新增回归覆盖
- `tests/test_gui_detection_review.py`
- `tests/test_gui_color_export.py`
- `tests/test_gui_frame_editing.py` 新增真实 TIFF 路径位深/颜色与 GUI review 状态测试
- 小型 16-bit RGB TIFF fixtures 覆盖 TopLeft 与 orientation 7
- RED 阶段确认旧实现分别失败于：位深 8、缺少 review 参数、review frames 被丢弃、导出 BitsPerSample 为 `(8, 8, 8)`

### 3. Fresh 验证
- GUI 测试：`17/17` 通过
- 打包脚本契约：`2/2` 通过
- 真实彩负 TIFF：
  - `Untitled (3).tif` → 16-bit，6 个 review frames，导出 `5224x2716` 16-bit RGB
  - `未标题(1).tif` → 16-bit，6 个 review frames，导出 `5133x2598` 16-bit RGB
- PyInstaller archive 已确认包含：
  - `filmcrop._vendor.tifffile`
  - `filmcrop.export`
  - `filmcrop.gui.main_window`
- `APP/scripts/package_app.sh` fresh 成功，最终产物：
  - `APP/NegativeCutter.app` → `2026-06-15 03:01:14`
  - arm64 Mach-O
  - `codesign --verify --deep --strict` 通过

### 4. 当前唯一未完成验收
- 修复后的最终 `.app` 尚未再次通过 Computer Use 点击完成“打开彩负 → 检测 6 帧 → 导出 TIFF”整条流程。
- 原因不是应用报错，而是第二次 macOS GUI 启动被外部执行额度门禁拒绝；不得绕过。
- 门禁解除后的精确终验步骤：
  1. `open -n APP/NegativeCutter.app`
  2. 打开 `test_files/Untitled (3).tif`，确认状态栏 `16bit`
  3. 点击检测，确认 6 帧与低置信度提示，导出按钮可用
  4. 导出 TIFF 到全新临时目录
  5. `magick identify` 确认所有输出为 16-bit RGB，并重新在 GUI 中打开一张确认彩色显示

## 2026-06-15 增量更新

### 1. 一键打包入口改为“只打包，不启动”
- 新增 [package_app.sh](APP/scripts/package_app.sh)，作为 GUI 版本当前唯一推荐入口
- 流程：运行 GUI 测试 → 调用 `build_app.sh` → `codesign --verify --deep --strict`
- 根据最新用户要求，**默认不再自动打开 `.app`**
- 当前推荐命令：

```bash
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop
APP/scripts/package_app.sh
```

### 2. 修复 16-bit 多通道图像两类问题
- 症状 A：部分输入在打开时直接报 `Too many dimensions: 3 > 2`
- 症状 B：彩色负片能打开，但在画布里被错误显示为黑白

**根因拆分**：
- 检测链路需要二维灰度阵列，这一约束是合理的
- 但显示链路不应复用灰度化结果，之前把 16-bit 多通道数组错误压成 `L` 模式，导致颜色丢失

**当前修复**：
- [detector.py](APP/filmcrop/detector.py) 新增 `_grayscale_2d()`，仅供检测路径把 1/3/4 通道统一成二维灰度
- [image_view.py](APP/filmcrop/gui/image_view.py) 的 `_normalize_16bit_array()` 现按输入维度输出：
  - 2D / 单通道 → `L`
  - 3 通道及以上 → `RGB`
- 这样检测仍走灰度，画布显示则保留彩色

### 3. 已验证
- 完整测试：`14` 项通过
- 打包脚本契约测试通过：确认源码中已无 `open "$APP_BUNDLE"`
- 16-bit 三通道显示测试通过：RGB 通道值保留
- 真实加载验证通过：
  - `test_files/raw0014.dng`
  - `test_files/SHD4001.tif`
- 最新产物时间戳：
  - `APP/scripts/package_app.sh` → `2026-06-15 02:17:38`
  - `APP/filmcrop/gui/image_view.py` → `2026-06-15 02:17:39`
  - `APP/NegativeCutter.app` → `2026-06-15 02:18:14`

### 4. 仍未验证
- 没有保留用户那张“彩负”原文件的本地回归夹具，因此**当前未做同一文件的自动化复测**
- 也没有对导出后的彩色裁切结果做逐帧肉眼验收；当前验证重点在“导入显示保持 RGB”与“检测不崩”

## 项目位置

```
/Users/winter/Documents/临时拷贝/Claude Code/filmcrop/APP/
```

## 目录结构

```
APP/
├── NegativeCutter.app               # ★ 最新打包产物（arm64，v2.4.5）
├── NegativeCutter.icns              # canonical 应用图标（生成后纳入源码）
├── NegativeCutter.spec              # PyInstaller 配置（onedir + target_arch + 强制 icon）
├── main.py                          # PyInstaller 入口
├── generate_icns.py                 # .icns 图标生成脚本
├── scripts/
│   ├── build_app.sh                 # 打包脚本（PyInstaller 前生成 icon）
│   ├── sign_app.sh                  # 签名验证与 ad-hoc 重签名脚本
│   └── package_app.sh               # ★ GUI 版本推荐入口：测试 + 打包 + 严格验签
└── filmcrop/
    ├── __init__.py                  # v2.4.5
    ├── detector.py                  # 帧检测引擎
    ├── export.py                    # JSON/XMP/图像裁切导出
    ├── api.py                       # FastAPI 服务器
    └── gui/
        ├── __init__.py
        ├── __main__.py
        ├── main_window.py           # ★ 主窗口：版本号展示 + 检测进度条 + 错误对话框带版本
        ├── image_view.py            # ★ 纯按钮+键盘缩放 + ScrollHandDrag 平移
        ├── frame_item.py            # 可拖拽帧框（定义 MIN_FRAME_SIZE）
        ├── export_dialog.py         # 导出对话框（下拉框排版修复）
        ├── logo.py                  # 对称品牌图标
        ├── theme.py                 # 暗色暖调设计 token
        └── style_sheet.py           # QSS 样式表（含下拉列表样式）
```

## v2.4.4 变更清单

### 1. PyInstaller onedir 迁移（解决 onefile 弃用警告）
- `EXE` 改为 `exclude_binaries=True`，移除废弃参数 `onefile=False`
- 新增 `COLLECT(exe, a.binaries, a.datas)` 收集依赖
- `BUNDLE` 接收 `coll` 替代 `exe`
- PyInstaller v7.0 不再报错

### 2. Universal 二进制支持
- `NegativeCutter.spec` 中 `target_arch` 支持环境变量 `PYI_TARGET_ARCH`
- 新增 `scripts/build_app.sh`，支持 `--target-arch universal2`
- 脚本自动检查依赖库架构兼容性

### 3. Code signing
- PyInstaller 默认 ad-hoc 签名（`codesign -s -`）
- 新增 `scripts/sign_app.sh`（sign / verify / status 三命令）
- 首次启动需右键 > 打开

### 4. DNG 临时文件清理
- `MainWindow` 新增 `_dng_tmp_path` 属性
- 加载新图像前自动 `os.unlink` 旧临时文件
- 窗口 `closeEvent` 中清理残留临时文件

### 5. JPEG 质量默认检测
- `_load_image` 中对 JPEG 源图读取 `img.info.get("quality")`
- `ExportDialog` 新增 `default_jpeg_quality` 参数
- 导出对话框自动使用源图质量作为默认值（无则回退 95）

### 6. 边角拖拽 Bug 修复
- `frame_item.py` 的 `_drag_start_value`（单值）→ `_drag_start_values`（四方向字典）
- 修复拖拽边角时第二方向使用错误基准值的问题

### 7. UI 截断修复
- 右侧面板包裹在 `QScrollArea` 中，窗口缩小时可滚动
- 帧列表 `MinimumHeight(120)` + `MaximumHeight(240)`
- 坐标标签宽度 32 → 40 px，中文完整显示

### 8. 对称 Logo
- 胶片孔：3 个纵向 → 2×2 对称网格（4 个）
- 中心标记：对角切割线 → 居中小菱形 ◆
- 移除左上角不对称高亮
- 同步更新 `logo.py` + `generate_icns.py` + `.icns`

### 9. 全局调整调优数据收集
- 每次全局调整后自动记录到 `~/.negativecutter/tuning.json`
- 记录字段：图像尺寸、方向、帧数、调整方向/像素、平均帧宽高
- 工具菜单新增「导出调优数据」，可导出 JSON 供算法改进

## 构建与运行

```bash
# 开发模式
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop/APP
python main.py

# 重新生成图标
python generate_icns.py

# 打包（默认 arm64）
./scripts/build_app.sh

# 推荐：完整 GUI 打包验证（仓库根目录执行）
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop
APP/scripts/package_app.sh

# 打包 universal2
./scripts/build_app.sh --target-arch universal2

# 签名验证
./scripts/sign_app.sh verify
```

## 关键数据结构

**Frame dict**：
```python
{
    "index": 1,
    "top": 0, "bottom": 100, "left": 0, "right": 200,
    "relativeTop": 0.0, "relativeBottom": 1.0,
    "relativeLeft": 0.0, "relativeRight": 1.0,
    "frameWidth": 200,
    "confidence": 0.87,
}
```

**MainWindow 状态属性**：
- `_image_path` → 当前图像路径
- `_frames` → list[dict]
- `_img_w`, `_img_h` → 图像尺寸
- `_source_fmt`, `_source_bit_depth`, `_source_color_space`, `_source_jpeg_quality` → 源图属性
- `_dng_tmp_path` → DNG 临时文件路径（加载前/关闭时清理）
- `_debug_info` → detector 诊断数据
- `_is_horizontal` → 扫描方向
- `_crop_angle` → 估计旋转角度
- `_undo_stack`, `_redo_stack` → 50 步历史

## 待办事项（已清空）

v2.4.4 handoff 中的 4 个待办全部解决：
1. ✅ onefile 弃用警告 → onedir 迁移
2. ✅ Universal 二进制 → `PYI_TARGET_ARCH` + build 脚本
3. ✅ Code signing → ad-hoc 签名 + sign_app.sh
4. ✅ DNG 临时文件 → 加载前/关闭时清理
5. ✅ JPEG 质量默认 → 源图 quality 检测

## 相关文件

| 文件 | 说明 |
|------|------|
| [MainWindow](APP/filmcrop/gui/main_window.py) | 主窗口：QScrollArea 面板 + 调优数据记录 |
| [Logo](APP/filmcrop/gui/logo.py) | 对称品牌图标（中心菱形 + 2x2 孔洞） |
| [Frame item](APP/filmcrop/gui/frame_item.py) | 边角拖拽 Bug 修复 |
| [Export dialog](APP/filmcrop/gui/export_dialog.py) | JPEG 质量透传 |
| [Packaging spec](APP/NegativeCutter.spec) | onedir 模式 + target_arch 支持 |
| [Build script](APP/scripts/build_app.sh) | 打包脚本（支持 universal2） |
| [Sign script](APP/scripts/sign_app.sh) | 签名验证与重签名 |
| [ICNS generator](APP/generate_icns.py) | 对称 Logo .icns 生成 |
