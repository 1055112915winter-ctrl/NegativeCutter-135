# NegativeCutter-135 安装指南

> **当前版本仅适配 135 胶片规格**，其他规格（120、110 等）正在开发中。

## 系统要求

- **macOS**（Intel / Apple Silicon 均可）
- **Lightroom Classic 10.0+**（建议使用最新版）
- **135 胶片扫描长条图**（DNG / TIFF）

## 安装步骤

1. **解压** `NegativeCutter-135-v2.4.3.zip`
2. 打开 **Lightroom Classic**
3. 菜单：`文件 → 增效工具管理器`（File → Plug-in Manager）
4. 点击左下角的 **`添加`**（Add）
5. 选择解压后的 **`NegativeCutter-135.lrplugin`** 文件夹
6. 确保插件状态显示为**「正在运行」**（Running）
7. 关闭增效工具管理器

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
4. 点击「开始批量处理」

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
| "检测引擎不存在" | 确认 `NegativeCutter-135.lrplugin` 文件夹中包含 `NegativeCutter` 可执行文件 |
| "检测失败 / 未检测到帧" | 检查当前是否在 Lightroom 中选中了图片；查看日志 `~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log` |
| 检测帧数不正确 | 调整预期帧数设置；黑白负片效果最好 |
| 其他胶片规格（120/110）检测结果异常 | **当前仅适配 135 规格**，其他格式尚未支持 |

## 卸载

1. Lightroom：`文件 → 增效工具管理器 → NegativeCutter → 移除`
2. 删除 `NegativeCutter-135.lrplugin` 文件夹即可

---

**版本**：v2.4.3（135-only）  
**作者**：李冬天（小红书号：李冬天 SimplyWinter）  
**开源协议**：GPL v3
