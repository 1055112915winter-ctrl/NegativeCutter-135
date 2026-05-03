# FilmCrop E2E 自动化测试架构 — JSON Watch 模式

> 创建日期: 2026-05-02
> 关联: FilmCrop_Clean.lrplugin 精简版插件
> 背景: AppleScript UI 自动化在 Lightroom Classic 上彻底失败后的替代方案

---

## 1. 背景与决策

### 问题
用户要求实现完全自动化的 E2E 测试，无需手动点击 Lightroom 菜单。先后尝试了多种 AppleScript UI 自动化方案，全部失败：

| 方法 | 错误码 | 根因 |
|------|--------|------|
| 链式 `click menu item "X" of menu 1 of menu item "Y"...` | -1728 | 嵌套子菜单无法通过 AppleScript 访问 |
| `first menu item whose name contains "增效工具"` | -1719 | System Events 无法索引该菜单项 |
| `name of every menu item` 后尝试 click | -1728 | 返回的是缓存列表，非实时 Accessibility 元素 |
| Help 搜索 `Cmd+Shift+/` + 输入"检测胶片帧" | 无响应 | 插件菜单不在 macOS Help 搜索索引内 |
| 修改 `LrPluginInMenu` 到 help/window/Library | 无效 | `LrExportMenuItems` 始终固定在「文件→增效工具额外命令」下 |
| `tell application "System Events"` | -600 | 当前环境 System Events 进程异常/无图形会话 |

**决策**: 放弃 AppleScript UI 自动化，改用 **JSON 文件监视模式**（ImportWatch 的变体）。

### 设计原则
- **一次手动，之后全自动**: 用户只需在 Lightroom 中手动点击一次「启动自动检测 (E2E)」，后续测试完全由 Python 脚本驱动
- **零对话框**: AutoWatch 模式跳过所有对话框，后台静默处理
- **与真实 Lightroom 一致**: 实际调用 `createVirtualCopies()`、`applyCrop()` 等 SDK API，catalog 变更真实可验证

---

## 2. 架构图

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  e2e_auto.py    │     │  detect_thumb.py │     │  Lightroom      │
│  (Python 测试)   │────▶│  (帧检测)         │     │  Classic        │
└────────┬────────┘     └──────────────────┘     └────────┬────────┘
         │                                               │
         │ 1. 生成 JSON 到 filmcrop_e2e.json            │
         │    (包含帧坐标 + targetBasename)              │
         │───────────────────────────────────────────────▶│
         │                                               │
         │    ◀───────── 2. AutoWatch 轮询 ─────────────│
         │       LrTasks.sleep(2) 检查 mtime             │
         │                                               │
         │    3. silentApplyJson() ─────▶ ImportAgent    │
         │       无对话框，直接创建虚拟副本               │
         │       + 应用裁剪                              │
         │                                               │
         │ 4. 倒计时结束后 ─────▶ 读取 catalog SQLite    │
         │    验证新虚拟副本 + 裁剪参数                   │
```

---

## 3. 文件变更清单

### 新增文件

| 文件 | 作用 |
|------|------|
| `FilmCrop_Clean.lrplugin/AutoWatch.lua` | E2E 测试入口菜单项。启动后监视 `filmcrop_e2e.json`，文件变化时自动调用 `silentApplyJson()` |
| `FilmCrop_Clean.lrplugin/StopAutoWatch.lua` | 停止 AutoWatch 轮询，清理 `prefs.autoWatchActive` |
| `FilmCrop_Clean.lrplugin/Init.lua` | 插件初始化钩子（预留，当前仅用于验证加载时序） |

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `FilmCrop_Clean.lrplugin/ImportAgent.lua` | **核心改动**。新增 `parseJson()`、`silentApplyJson()`、`startAutoWatch()`、`stopAutoWatch()`。`silentApplyJson` 支持 `targetBasename` 过滤，仅处理匹配的照片。`startAutoWatch` 每次轮询时重新获取当前选中的照片，避免选错 |
| `FilmCrop_Clean.lrplugin/Info.lua` | 注册「启动自动检测 (E2E)」和「停止自动检测 (E2E)」两个菜单项到 `LrExportMenuItems` 和 `LrLibraryMenuItems`。添加 `LrInitPlugin = "Init.lua"` |
| `FilmCrop_Clean.lrplugin/Shutdown.lua` | 插件卸载时同时清理 `autoWatchActive` 和 `autoWatchJsonPath` |
| `FilmCrop_Clean.lrplugin/PluginInfoProvider.lua` | 移除调试用的 `LrLogger` 和 `/tmp/filmcrop_plugin_loaded.log` 写入代码（清理） |
| `FilmCrop_Clean.lrplugin/tests/e2e_auto.py` | **完全重写**。从「AppleScript 菜单触发 + 倒计时等待」改为「Python 生成 JSON → AutoWatch 处理 → catalog 验证」模式。支持 AppleScript 不可用时降级为纯 JSON 生成 |

---

## 4. 使用方式

### 第一步：手动启动 AutoWatch（只需一次）

1. 重启 Lightroom 让插件重新加载（`LrForceInitPlugin=true` 会强制重新初始化）
2. 切换到 **修改照片 (Develop)** 模块
3. 选中要测试的照片（如 `52191.tif`）
4. 点击菜单: `文件 → 增效工具额外命令 → FilmCrop → 启动自动检测 (E2E)`
5. 看到「自动检测已启动」对话框即成功

### 第二步：运行全自动测试

```bash
cd FilmCrop_Clean.lrplugin/tests
python3 e2e_auto.py --wait 120 --photo 52191
```

脚本流程:
1. 读取 catalog 基准状态（当前虚拟副本数）
2. 调用 `detect_thumb.py` 生成帧坐标 JSON
3. 写入 `FilmCrop_Clean.lrplugin/filmcrop_e2e.json`
4. 倒计时等待（默认 90s，建议 120s）
5. 读取 catalog 新状态，对比验证:
   - 是否创建了预期数量的虚拟副本
   - 每个虚拟副本是否包含 `CropTop/Bottom/Left/Right`
   - 主照片裁剪是否被重置

### 停止 AutoWatch

测试完成后，点击菜单 `文件 → 增效工具额外命令 → FilmCrop → 停止自动检测 (E2E)`，或重启 Lightroom。

---

## 5. 关键代码逻辑

### AutoWatch 轮询（ImportAgent.lua）

```lua
LrTasks.startAsyncTask(function()
  local lastModified = LrFileUtils.fileAttributes(jsonPath).fileModificationDate or 0
  while prefs.autoWatchActive do
    LrTasks.sleep(2)
    local attrs = LrFileUtils.fileAttributes(jsonPath)
    if attrs.fileModificationDate > lastModified then
      lastModified = attrs.fileModificationDate
      -- 每次重新获取选中的照片，避免选错
      local currentCatalog = LrApplication.activeCatalog()
      local currentPhotos = currentCatalog:getTargetPhotos()
      silentApplyJson(currentCatalog, currentPhotos, jsonPath)
    end
  end
end)
```

### targetBasename 过滤（e2e_auto.py → ImportAgent.lua）

测试脚本在 JSON 中写入 `targetBasename` 字段:
```json
{"frameCount":6, "targetBasename":"52191", "frames":[...]}
```

`silentApplyJson()` 会过滤 `selectedPhotos`，只处理文件名匹配的照片，避免当用户选中多张照片时误处理。

### AppleScript 降级

当前环境（及某些 CI 环境）System Events 不可用。e2e_auto.py 会先检测 `can_use_applescript()`:
- 可用: 自动激活 Lightroom、切换 Develop 模块、确保选中测试照片
- 不可用: 跳过 UI 控制，仅生成 JSON，依赖用户已正确设置 Lightroom 状态

---

## 6. 环境限制与注意事项

1. **System Events 不可用**: 当前 Claude Code 环境中 `osascript` 与 System Events 通信持续返回 `-600` 错误。e2e_auto.py 已适配降级模式，但完整自动化需要本地 macOS 上 System Events 正常
2. **WAL 模式**: Lightroom 的 SQLite 使用 WAL 日志。e2e_auto.py 使用 `copy_catalog_for_reading()` 复制 catalog + `-wal` + `-shm` 到临时目录再读取，避免文件锁定
3. **同名照片**: catalog 中可能存在多个同 `baseName` 的 master（如 luckyc20013 有两个 master）。脚本优先选择虚拟副本数为 0 的 master
4. **Develop 模块限制**: Lightroom SDK 的 `applyDevelopSettings` 仅在 Develop 模块对虚拟副本生效。AutoWatch 启动前会检查当前模块

---

## 7. 关联文件路径

```
FilmCrop_Clean.lrplugin/
  tests/
    e2e_auto.py              # 主测试脚本
    e2e_test.py              # 旧版交互式测试（保留）
    e2e_lr_control.py        # AppleScript 控制器（已废弃）
    diagnose_e2e.py          # catalog 诊断脚本
  Info.lua                   # 菜单注册
  ImportAgent.lua            # 核心: silentApplyJson + startAutoWatch
  AutoWatch.lua              # 菜单入口: 启动自动检测
  StopAutoWatch.lua          # 菜单入口: 停止自动检测
  Init.lua                   # 插件初始化
  Shutdown.lua               # 插件卸载清理
  filmcrop_e2e.json          # 测试脚本生成的 JSON（运行时创建）
```

---

## 8. 后续可改进方向

- **HTTP API 模式**: 当前 `ImportHTTP.lua` 已有 `detectViaHttp()`，可启动 `filmcrop/gui` 的 FastAPI 服务器，通过 POST /analyze 触发。但同样需要先手动在 Lightroom 中启动一次，优势是可以传入更多参数
- **XMP 边车导入**: `ImportXMP.lua` 支持从 `.filmcrop.xmp` 文件导入，适合与外部工作流集成
- **Mock SDK 回归**: `tests/mock_sdk/` 和 `validate_logic.py` 提供无 Lightroom 的快速回归测试，建议在 CI 中保留作为第一层验证
