# NegativeCutter Plugin Hardening Handoff

Date: 2026-06-14 (initial) · 2026-06-18 (v2.4.5 执行路径重构)

## Branch and scope

- Branch: `codex/plugin-hardening-v2.4.5`
- Worktree: `.claude/worktrees/codex-plugin-hardening-v2.4.5`
- Base: `e2dd3a6`
- 已合并 master 最新改动，v2.4.5 发布 ZIP 已产出。

## Implemented

- raw0014 auto-frame mode now rejects the narrow-gap 8-frame over-segmentation and returns 6 frames.
- CLI file logging is opt-in through `NEGATIVECUTTER_DEBUG_LOG` and capped at 512 KiB.
- `filmcrop.api` imports cleanly when FastAPI/Pydantic are absent.
- Release staging excludes tests, WORK, local instructions, debug files, and validates every `Info.lua` file reference.
- The diagnostic menu entry that referenced an excluded test script was removed.
- Obsolete NumPy hidden imports were removed from the PyInstaller spec.

## 2026-06-18 v2.4.5 增量：移除临时目录复制，原地执行引擎

### 根因

用户反馈插件报「无法复制到临时目录」。原 `ProcessAgent.lua:analyzeWithPython` 的 `ensureRuntimeBundle` 机制通过逐文件 `LrFileUtils.copy` 将 138 个 PyInstaller onedir 文件（含 Mach-O 二进制、大型 .dylib）复制到 `temp/NegativeCutter_Runtime/`。该复制在真实 Lightroom 中不可靠，LrFileUtils.copy 对特殊文件类型会失败。

**该复制机制的历史成因**：旧版 `shellEscape` 有一个 Lua 模式匹配 bug —— `:gsub('$', '\\$')` 中的 `$` 在 Lua 模式中匹配字符串末尾锚点而非字面美元符，导致**所有路径末尾都被追加了字面 `$`**，shell 执行时报 "No such file or directory"（退出码 127 / 32512）。当时误判为「中文路径不兼容」，引入了复制到英文临时目录的 workaround。实际上 shellEscape 的 bug 才是根因。

### 修复

1. **移除临时目录复制机制**（~70 行删除）：`ensureRuntimeBundle`、`copyFileWithDirs`、`runtimeBundleIsComplete` 全部移除。`manifest.txt` 不再被 Lua 层读取。

2. **`shellEscape` 修复**：`:gsub('$', '\\$')` → `:gsub('%$', '\\$')`。`%$` 在 Lua 模式中正确匹配字面美元符。

3. **原地执行**：直接在插件目录内执行 `NegativeCutter/NegativeCutter`，不复制到临时目录。这是正常路径。

4. **宽容 fallback**：原地执行失败时，不再仅匹配退出码 32512，而是检测任意系统级失败信号：
   - 退出码范围 1-31（SIGKILL=9、SIGBUS=10、SIGSEGV=11 等，常见于 Gatekeeper/SIP 干预）
   - 或 stderr 包含 11 个已知系统错误关键词（`dyld`、`Library not loaded`、`Operation not permitted`、`Killed`、`code signing`、`permission denied` 等）
   - 检测到系统级失败后，用单条 `cp -RL` shell 命令复制整个 onedir 到 `temp/` 后重试
   - 这对一台新 Mac 上可能遇到的 Gatekeeper/SIP/dyld/架构不匹配等不同阻止形态提供统一回退

5. **`build.sh` sandbox 兼容**：`mktemp -d` → `$TMPDIR/filmcrop-build-$$`，修复沙箱下 `/var/folders/...` 不可写的问题。

### 实现对比：GUI vs 插件

| | GUI（独立 .app） | 插件（Lightroom） |
|---|---|---|
| 执行方式 | 进程内 Python 函数调用 | 子进程 `LrTasks.execute` |
| 文件复制 | 无（直接读取） | 已移除（原 138 次 LrFileUtils.copy） |
| fallback | 无（不需要） | cp -R → 重试（系统级失败时） |

### 版本号

- `filmcrop/__init__.py` (plugin + APP)：2.4.4 → 2.4.5
- `Info.lua`：2.4.3 → 2.4.5（之前漏更新）

### 修改文件

| 文件 | 改动性质 |
|------|----------|
| `ProcessAgent.lua` | 核心重构：删除临时目录复制，改为原地执行 + 宽容 fallback |
| `filmcrop/__init__.py` × 2 | 版本号 |
| `Info.lua` | 版本号（补之前漏更新） |
| `build.sh` | mktemp sandbox 兼容 |

### 验证

- Python 测试：27/27 通过
- `bash -n build.sh` 通过
- `ast.parse` Python 语法检查通过
- PyInstaller onedir 构建成功
- ZIP 打包：`NegativeCutter-135-v2.4.5.zip`（29MB）
- ZIP 内容验证：版本号 2.4.5 已写入 Info.lua + filmcrop/__init__.py

### 未验证（需要真实 Lightroom 验收）

1. 在真实 Lightroom 中安装 v2.4.5 ZIP，打开一张 135 扫描片，点击「检测胶片帧」
2. 确认检测成功（不再报「无法复制到临时目录」）
3. 如果原地执行因系统级原因失败，确认 cp -R fallback 接管并成功重试
4. 在另一台 Mac（不同 macOS 版本/安全策略）上复测
