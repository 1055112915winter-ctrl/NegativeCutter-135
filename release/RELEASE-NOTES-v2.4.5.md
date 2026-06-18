## NegativeCutter-135 v2.4.5

本版本同时更新 Lightroom 插件与独立桌面版。

### 主要更新

- 修复 Lightroom 插件路径转义问题，检测引擎默认在插件目录原地运行
- 系统级执行失败时自动复制运行时到临时目录并重试
- 修复部分 135 扫描条自动识别为 8 帧的问题，恢复为 6 帧
- 调试日志改为按需开启，并限制日志大小
- 独立桌面版增加色彩管理 DNG 导出，修复缩放、平移和手势行为
- 统一应用图标，并在窗口标题中显示版本号

### 系统要求

- macOS 11 或更高版本
- Apple Silicon（arm64）
- Lightroom 插件需要 Adobe Lightroom Classic
- 用户端不需要安装 Python 或额外依赖

### 安装

Lightroom 插件：

1. 下载并解压 `NegativeCutter-135-v2.4.5.zip`
2. Lightroom Classic → 增效工具管理器 → 添加
3. 选择解压后的 `NegativeCutter-135.lrplugin`

独立桌面版：

1. 下载并解压 `NegativeCutter-135-v2.4.5-Standalone.zip`
2. 将 `NegativeCutter.app` 拖入“应用程序”目录后运行

### 验证

- 插件和桌面版版本号均为 2.4.5
- 两个 bundle 均为 macOS arm64
- Standalone APP 通过深度代码签名结构校验
- 插件回归测试通过；raw0014 实物回归本次未运行，因为未提供测试 DNG 路径
