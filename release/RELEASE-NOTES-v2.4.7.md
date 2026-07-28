# NegativeCutter v2.4.7

v2.4.7 是一次面向日常使用的小更新，重点改善独立版反复导出时的操作连续性。135 和单排 120 的识别与 Lightroom 裁切流程保持不变。

## 本次更新

### 独立版导出设置记忆

- 在导出对话框中勾选“将当前选项设为默认”后，下一次导出会自动带出保存的文件格式、JPEG 质量和色彩空间。
- 支持 TIFF、JPEG、PNG 等常用导出格式；JPEG 质量只在选择 JPEG 时生效。
- 输出目录仍根据当前图像确定，不会因为保存默认选项而改变。

### 兼容性

- App、Lightroom 插件、API 和 macOS Bundle 版本统一为 2.4.7。
- 继续支持 135 与单排 120（645、6×6、6×7、6×8、6×9）；双排或多排扫描仍不在支持范围内。

## 安装

### Lightroom Classic 插件

1. 下载并解压 `NegativeCutter-135-v2.4.7.zip`。
2. 在解压目录运行顶层 `install.sh`。
3. 重启 Lightroom Classic，并在“文件 → 增效工具管理器”确认 NegativeCutter 正在运行。

### macOS 独立版

1. 下载并解压 `NegativeCutter-135-v2.4.7-Standalone.zip`。
2. 将 `NegativeCutter.app` 移入“应用程序”。
3. 首次启动若被 Gatekeeper 拦截，请右键 App 后选择“打开”。

## 验证范围

- 导出默认项的读取、保存和格式切换测试通过。
- 120 真实样图、135 真实样图、AD/CB 方向契约和插件流水线回归通过。
