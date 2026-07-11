# NegativeCutter-135 — Lightroom 135 胶片扫描自动裁剪插件

> **当前版本支持 135 与单排 120 扫描**。120 格式包括 645、6×6、6×7、6×8、6×9；双排或多排扫描暂不支持，110 等其他规格尚未测试。

自动识别长条扫描胶片中的单帧，并创建带精确裁剪的虚拟副本。

检测角度经过可信度校验；非有限值或超过 3° 的离群角度会被重置为 0，
避免低分辨率/错误间隙产生灾难性旋转。

## 安装

从 Release 页面下载 **release ZIP** 并解压。压缩包顶层包含 **top-level `install.sh`** 与 `NegativeCutter-135.lrplugin`；在终端进入解压目录后执行：

```bash
./install.sh
```

脚本会 **validates the release and stages it before replacing the installed plugin**，并在出错时 **rolls back if installation fails**。完成后请 **Restart Lightroom**。

`NEGATIVECUTTER_MODULES_DIR` 是 **advanced/test override**，仅用于高级用户或测试指定 Modules 目录；普通安装无需设置。

如果无法运行脚本，可保留使用 Lightroom 的 **Plugin Manager** 手动安装：`文件 > 增效工具管理器` → `添加` → 选择 `NegativeCutter-135.lrplugin` 文件夹；确认状态显示为「正在运行」后重启 Lightroom。

## 使用

### 单次检测

1. 在**图库模块**或**修改照片模块**中选中扫描文件
2. 菜单：`文件 > 增效工具额外命令 > NegativeCutter > 检测胶片帧`
3. 选择胶片格式；120 扫描请选择 645、6×6、6×7、6×8 或 6×9
4. 输入预期帧数（默认 6，填 0 自动检测）
5. 点击「开始检测」，自动创建虚拟副本并应用裁剪

### 批量处理

1. 选中多张照片
2. 菜单：`文件 > 增效工具额外命令 > NegativeCutter > 批量处理`
3. 选择胶片格式并输入预期帧数，所有照片使用相同设置
4. 点击「开始批量处理」

### 快捷键（macOS 手动设置）

Lightroom SDK 不支持插件内置全局快捷键。如需快捷操作，请通过 macOS 系统偏好设置手动绑定：

**系统设置 → 键盘 → 键盘快捷键 → App 快捷键**
1. 点 `+`，应用程序选「Adobe Lightroom Classic」
2. 菜单标题填完整路径（精确匹配）：
   - `文件->增效工具额外命令->NegativeCutter->检测胶片帧`
   - `文件->增效工具额外命令->NegativeCutter->批量处理`
3. 按你想要的组合键（建议 `⌘M` 和 `⌘⇧M`）

## 故障排除

| 问题 | 解决方式 |
|------|----------|
| "检测引擎不存在" | 确认 `NegativeCutter-135.lrplugin` 中包含 `NegativeCutter` 可执行文件 |
| "检测失败 / 未检测到帧" | 检查是否选中了图片；查看日志 `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log` |
| 检测帧数不正确 | 调整预期帧数；黑白负片效果最好 |
| 120 双排或多排扫描检测异常 | 当前仅支持单排 120，请先将不同排拆分为独立扫描 |

## 版本历史

### v2.4.4 (2026-06-13)
- **分发包引擎优先级修复**：优先使用内置 `NegativeCutter` 打包引擎，不再误用系统 Python 导致 `No module named 'numpy'`
- **胶片类型选择**：新增负片/反转片/正片选项，独立边界清理模块 `CropCleaner.lua`
- **DNG 解码加固**：SubIFD 解析支持 8/16/32-bit、单条带/多条带、大端字节序
- **检测算法修复**：valley mode baseline、暗边缘检测、边界单调性守卫
- **打包方式调整**：PyInstaller 从 onefile 改为 onedir，提升 macOS 稳定性

### v2.4.3 (2026-06-09)
- **SubIFD DNG 解码**：直接解析 DNG SubIFD 结构读取 RAW 像素，无需 rawpy/LibRaw
- **严格 3:2 比例锁定**：middle frames 自动输出精确 3:2，无需手动锁定
- **边缘白边消除**：收紧-only 约束 + 安全边距，彻底消除扫描脏边
- **Gap 过渡带吸收**：plateau refinement 将过渡带推进 gap，frame 内部更干净
- **比例化阈值**：阈值随分辨率自适应，低分辨率图也能稳定检测

### v2.4.1 (2026-05-22)
- **赞助与反馈**：新增赞助入口和问题反馈菜单
- **UI 优化**：批量处理完成弹窗优化

### v2.4.0 (2026-05-22)
- **版本号统一**：修正各处版本号不一致问题
- **GitHub 发布**：首次在 GitHub 发布正式 Release
- **文档完善**：安装指南和使用说明更新

### v2.3.0 (2026-05-06)
- **独立可执行文件**：内置检测引擎，无需安装 Python 或 pip 依赖
- **开箱即用**：下载解压即可使用

### v2.2.0-beta.1+135 (2026-05-06)
- **图库模块支持**：无需切换到修改照片模块即可运行
- **UI 精简**：菜单缩减为 2 项（检测 + 批量）
- **流程优化**：跳过预览，直接创建虚拟副本
- **边界清理**：0.3% 内收 + 微小旋转角过滤，消除脏边和斜边
- **检测改进**：plateau-walk gap 边界 + 长边对称回退 + confidence-based mirroring

---

**作者**：李冬天  
**小红书号**：李冬天（SimplyWinter）
