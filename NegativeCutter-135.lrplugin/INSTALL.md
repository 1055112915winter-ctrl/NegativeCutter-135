# NegativeCutter-135 安装指南

> **当前版本仅适配 135 胶片规格**，其他规格（120、110 等）正在开发中。

## 系统要求

- **macOS**（Intel / Apple Silicon 均可）
- **Lightroom Classic 10.0+**（建议使用最新版）
- **135 胶片扫描长条图**（DNG / TIFF）

## 安装步骤

1. **解压** `NegativeCutter-135-v2.4.4.zip`
2. （重要）如果从浏览器或网盘下载，macOS 会给文件加上「隔离属性」。打开终端，执行以下命令解除隔离（把路径换成你实际解压的位置）：
   ```bash
   xattr -dr com.apple.quarantine ~/Downloads/NegativeCutter-135.lrplugin
   ```
   否则 Lightroom 可能无法加载插件或无法执行内置检测引擎。
3. 打开 **Lightroom Classic**
4. 菜单：`文件 → 增效工具管理器`（File → Plug-in Manager）
5. 点击左下角的 **`添加`**（Add）
6. 选择解压后的 **`NegativeCutter-135.lrplugin`** 文件夹
7. 确保插件状态显示为**「正在运行」**（Running），并在插件信息面板看到「✓ 已找到打包引擎 (NegativeCutter)」
8. 关闭增效工具管理器

## 使用

### 单次检测（单张照片）

1. 在**图库模块**或**修改照片模块**中，选中一张扫描好的胶片长条图
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 检测胶片帧`
3. 输入预期帧数（默认 6，填 0 自动检测）
4. 点击「开始检测」，自动创建虚拟副本并应用裁剪

### 批量处理（多张照片）

1. 选中多张扫描文件
2. 菜单：`文件 → 增效工具额外命令 → NegativeCutter → 批量处理`
3. 输入预期帧数，所有照片使用相同帧数
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
| "检测引擎不存在" | 同上，或重新下载完整 ZIP 包 |
| "导入 filmcrop 失败: No module named 'numpy'" | 说明你当前用的是 `detect_thumb.py` 而不是打包引擎。检查 `.lrplugin` 中是否存在 `NegativeCutter` 可执行文件，或重新执行 build.sh / 下载新版 |
| "检测失败 / 未检测到帧" | 检查当前是否在 Lightroom 中选中了图片；查看日志 `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log` |
| 检测帧数不正确 | 调整预期帧数设置；黑白负片效果最好 |
| 边缘仍有脏边或白边 | 尝试在对话框切换胶片类型，或调整裁剪后手动微调 |
| 其他胶片规格（120/110）检测结果异常 | **当前仅适配 135 规格**，其他格式尚未支持 |

## 卸载

1. Lightroom：`文件 → 增效工具管理器 → NegativeCutter → 移除`
2. 删除 `NegativeCutter-135.lrplugin` 文件夹即可

---

**版本**：v2.4.4（135-only）  
**作者**：李冬天（小红书号：李冬天 SimplyWinter）  
**开源协议**：GPL v3
