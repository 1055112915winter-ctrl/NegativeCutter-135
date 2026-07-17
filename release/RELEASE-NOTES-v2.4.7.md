# NegativeCutter v2.4.7

v2.4.7 是 Lightroom Classic 插件的 120 预览方向修复版本。它修复了带 EXIF orientation 5/7（Lightroom 中常见为 `AD/CB`）的 120 TIFF 在裁切预览中方向不匹配的问题。

## 本次修复

- 将检测缩略图坐标与 Lightroom 最终裁切坐标分离
- 预览始终在缩略图自身方向上绘制画格，不再把上下排列的 120 画格显示成左右窄列
- 用户确认预览后才转换为 Lightroom 裁切坐标，保留 v2.4.6 已验证的最终虚拟副本方向
- 逐张预览与整批统一模式采用同一坐标转换契约
- 整批像素偏移先在预览坐标中应用，再转换到每张照片自己的 Lightroom 方向

## 影响范围

- 主要影响 Lightroom Classic 插件中的单排 120 预览
- 135 检测算法未修改
- macOS 独立版检测行为未修改，仅同步补丁版本号
- 继续仅支持单排 120；多排或网格扫描不在本版本范围内

## 安装

### Lightroom Classic 插件

1. 下载并解压 `NegativeCutter-135-v2.4.7.zip`
2. 在解压目录运行顶层 `install.sh`
3. 完全退出并重新打开 Lightroom Classic

### macOS 独立版

1. 下载并解压 `NegativeCutter-135-v2.4.7-Standalone.zip`
2. 将 `NegativeCutter.app` 移入“应用程序”
3. 首次启动若被 Gatekeeper 拦截，请右键 App 后选择“打开”

## 验证

- 用户已在真实 `Untitled (3).tif` 预览中确认方向恢复正常
- 65 项核心 Python 测试通过
- 真实 135 TIFF、DNG 与两条真实 120 TIFF 回归通过
- AD/CB 方向、逐张确认、整批统一偏移、预览运行时和识别工作流回归通过
- 发布包清单、签名、打包前后识别 smoke 与预览渲染 smoke 通过

## 发布附件

- `NegativeCutter-135-v2.4.7.zip`
- `NegativeCutter-135-v2.4.7-Standalone.zip`
