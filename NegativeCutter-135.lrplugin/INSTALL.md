# NegativeCutter-135 安装指南

> **当前版本支持 135 与单排 120 扫描**。120 格式包括 645、6×6、6×7、6×8、6×9；双排或多排扫描暂不支持，110 等其他规格尚未测试。

## 系统要求

- **macOS**（Intel / Apple Silicon 均可）
- **Lightroom Classic 10.0+**（建议使用最新版）
- **135 或单排 120 胶片扫描长条图**（DNG / TIFF）

## 安装步骤

推荐使用 Release 页面下载的 **release ZIP**：解压后，顶层会有 **top-level `install.sh`** 和 `NegativeCutter-135.lrplugin`。

1. 在终端进入解压后的目录并运行：
   ```bash
   ./install.sh
   ```
   安装脚本会 **validates the release and stages it before replacing the installed plugin**；若安装过程中失败，**rolls back if installation fails**，保留原有插件。安装完成后请 **Restart Lightroom**，让它重新载入插件。
2. （重要）如果从浏览器或网盘下载，macOS 会给文件加上「隔离属性」。打开终端，执行以下命令解除隔离（把路径换成你实际解压的位置）后，再运行安装脚本：
   ```bash
   xattr -dr com.apple.quarantine /path/to/extracted-release
   ```
   否则 Lightroom 可能无法加载插件或无法执行内置检测引擎。

### 高级选项与手动安装

- `NEGATIVECUTTER_MODULES_DIR` 是 **advanced/test override**，仅供高级用户或测试指定非默认 Modules 目录；普通安装请不要设置它。
- 如果不能运行脚本，仍可使用 Lightroom 的 **Plugin Manager**：打开 `文件 → 增效工具管理器`，点击 `添加`，选择解压后的 `NegativeCutter-135.lrplugin` 文件夹，确认状态显示为「正在运行」，然后重启 Lightroom。

## 使用

「检测胶片帧」和「批量处理」都可选择 **逐张预览**、**整批统一** 或 **不预览**。逐张预览逐张确认；整批统一只复用第一张成功识别照片的四个数值偏移，不复用帧坐标；不预览直接按每张照片自己的检测结果创建副本。

预览中的四个数字控制上、下、左、右边界向外扩展。停止输入约 **120 毫秒** 后图片刷新；预览尚未完成或渲染失败时不能「**确认**」，「**重置**」会恢复四个 0。运行时可在 Lightroom 左上角查看**进度**并**取消**，取消不会删除已经成功创建的虚拟副本。

### 单次检测（单张照片）

1. 在**图库模块**或**修改照片模块**中，选中一张扫描好的胶片长条图
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 检测胶片帧`
3. 选择胶片格式；120 扫描请选择 645、6×6、6×7、6×8 或 6×9
4. 自动检测画幅时，预期帧数默认为 0（自动）；选择具体画幅后会带出常用值：135 为 6，645 为 4，6×6 为 3，6×7 为 3，6×8 和 6×9 为 2
5. 点击「开始检测」，自动创建虚拟副本并应用裁剪

### 批量处理（多张照片）

1. 选中多张扫描文件
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 批量处理`
3. 保持自动检测可自动判断帧数，也可手动指定整批使用的帧数
4. 选择胶片格式（135/120 6×6 等）和胶片类型（负片/反转片/正片）
5. 点击「开始批量处理」

> **胶片类型说明**：
> - **负片（Negative）**：默认 0.3% 边界内收，适合大多数黑白/彩色负片
> - **反转片（Reversal）**：与负片相同参数，可独立调优
> - **正片（Positive）**：0.5% 边界内收，适合对比度较低的场景
>
> 首次使用建议从「负片」开始，如果边缘仍有脏边再尝试其他类型。

### 快捷键（可选）

Lightroom SDK 不支持插件内置快捷键，需要通过 macOS 系统设置手动绑定：

**系统设置 → 键盘 → 键盘快捷键 → App 快捷键**
1. 点 `+`，应用程序选「Adobe Lightroom Classic」
2. 菜单标题填完整路径：
   - `文件->增效工具额外命令->NegativeCutter->检测胶片帧`
   - `文件->增效工具额外命令->NegativeCutter->批量处理`
3. 按你想要的组合键（建议 `⌘M` 和 `⌘⇧M`）

## 故障排除

| 问题 | 解决方式 |
|------|----------|
| 插件管理器显示「✗ 未找到检测引擎」 | 确认 `.lrplugin` 文件夹中包含 `NegativeCutter` 可执行文件；如从网络下载，执行 `xattr -dr com.apple.quarantine /path/to/NegativeCutter-135.lrplugin` |
| "检测引擎不存在" | 同上，或重新下载并重新运行 Release 的 `install.sh` |
| "导入 filmcrop 失败: No module named 'numpy'" | 说明你当前用的是 `detect_thumb.py` 而不是打包引擎。检查 `.lrplugin` 中是否存在 `NegativeCutter` 可执行文件，然后重新运行 Release 的 `install.sh` |
| "检测失败 / 未检测到帧" | 检查当前是否在 Lightroom 中选中了图片；查看日志 `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log` |
| 检测帧数不正确 | 调整预期帧数设置；黑白负片效果最好 |
| 边缘仍有脏边或白边 | 尝试在对话框切换胶片类型，或调整裁剪后手动微调 |
| 120 双排或多排扫描检测异常 | 当前仅支持单排 120，请先将不同排拆分为独立扫描 |
| 其他胶片规格（110 等）检测结果异常 | 当前尚未支持 |

## 卸载

1. Lightroom：`文件 → 增效工具管理器 → NegativeCutter → 移除`
2. 删除 `NegativeCutter-135.lrplugin` 文件夹即可

---

**版本范围**：v2.4.7（135 + 单排 120）
**作者**：李冬天（小红书号：李冬天 SimplyWinter）  
**开源协议**：GPL v3
