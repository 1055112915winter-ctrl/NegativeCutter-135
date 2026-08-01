# NegativeCutter v2.4.7

v2.4.7 是一次面向日常使用的小更新，重点改善独立版反复导出时的操作连续性。135 和单排 120 的识别与 Lightroom 裁切流程保持不变。

## 本次更新

### 独立版导出设置记忆

- 在导出对话框中勾选“将当前选项设为默认”后，下一次导出会自动带出保存的文件格式、JPEG 质量和色彩空间。
- 支持 TIFF、JPEG、PNG 等常用导出格式；JPEG 质量只在选择 JPEG 时生效。
- 输出目录仍根据当前图像确定，不会因为保存默认选项而改变。

### 兼容性

- App、Lightroom 插件、API 和 macOS Bundle 版本统一为 2.4.7。
- 支持 macOS 14.0 及以上版本；请下载与设备匹配的 Apple Silicon（arm64）或 Intel（x86_64）安装器。
- 继续支持 135 与单排 120（645、6×6、6×7、6×8、6×9）；双排或多排扫描仍不在支持范围内。

## 安装

### Lightroom Classic 插件

1. 下载与设备架构匹配的、已公证的 `.pkg` 安装器。
2. 双击安装器并完成安装。
3. 重启 Lightroom Classic，并在“文件 → 增效工具管理器”确认 NegativeCutter 正在运行。

如果 Release 同时提供手动安装 ZIP，可在解压目录运行顶层 `install.sh`。请勿通过移除 quarantine 或关闭 Gatekeeper 来绕过系统安全检查。

### macOS 独立版

1. 下载与设备架构匹配的、已签名并通过公证的独立版安装包。
2. 按安装包提示完成安装。
3. 从“应用程序”启动 NegativeCutter。
