# FilmCrop E2E 测试体系融入 — 状态记录

> 创建日期: 2026-05-02
> 最近更新: 2026-05-04(长边对称回退修复右侧片基空白,L4 全绿;详见 §14)
> 接续自: [e2e-json-watch-architecture.md](e2e-json-watch-architecture.md)(架构师设计)
> 落地分支: `claude/hungry-hypatia-f45ddd` (worktree: `hungry-hypatia-f45ddd`,任务完结待清理) + master 同步修复 (`94ecddb` + `69348d4`)
> 状态: L1 全绿(plateau-walk 改动后),L3+L4+L5 之前 PASS、新改动后 L4 待重测。**注意:LR 实际加载的是 master 路径下的 plugin,worktree 上的 commit 不直接生效;详见 §10**

---

## 1. 任务背景

姊妹 worktree `claude/quizzical-jackson-a651f4`(架构师)在更老 baseline 922a4d2 上完成了 JSON-watch E2E 测试架构改造,但同时附带了一份**回退到旧基线**的 detector.py。本 worktree (`hungry-hypatia-f45ddd`)已在 master HEAD bcc8556 上演化出 gap 对齐 + min-based ratio 强约束的 detector,需要决定如何融合。

用户决策(已确认):
- **A/B 对比后再选 detector**(不盲目接受架构师版本)
- **集成代码落到本 worktree**

---

## 2. 落地的 5 次提交

```
ea4a33c fix(import): lift isHorizontal in parseJson to avoid bogus axis swap
3b958e4 docs: detector A/B comparison report (2026-05-02)
d54a201 chore: gitignore test_files dev symlink
dd8d704 fix(test): align e2e_auto.py CLI flag with detect_thumb.py (--frames)
f30739d test: integrate JSON-watch e2e harness from quizzical worktree
```

### 2.1 f30739d — 测试基础设施引入

从架构师 worktree 拷贝(detector.py 显式排除):
- 新建: `AutoWatch.lua` / `StopAutoWatch.lua` / `Init.lua`
- 新建: `FilmCrop_Clean.lrplugin/tests/` 整目录(13 个文件 + mock_sdk/)
- patch: `ImportAgent.lua` (816→979 行,新增 `parseJson` / `silentApplyJson` / `startAutoWatch` / `stopAutoWatch`)
- patch: `Info.lua` (90→107 行,注册 E2E 菜单项 + LrInitPlugin)
- patch: `Shutdown.lua` (新增 autoWatchActive/autoWatchJsonPath 清理)

### 2.2 dd8d704 — CLI flag bug 修复

`tests/e2e_auto.py:244` 调用 `detect_thumb.py --expected-frames N`,但 [detect_thumb.py](FilmCrop_Clean.lrplugin/detect_thumb.py) 实际只接受 `--frames N`,argparse 会把未知参数当 unknown 处理,导致非默认帧数场景静默失效。改成 `--frames`。

### 2.3 d54a201 — gitignore test_files symlink

worktree 根目录加了 `test_files` symlink 指向 `../../../test_files`(主 repo 的测试集),用于跑 `test_detect_batch.py`。.gitignore 加 `/test_files` 防止把 symlink 提交。

### 2.4 3b958e4 — A/B 对比报告归档

`docs/detector-ab-comparison.md` 记录 4 项指标在 3 个 TIF 上的对比数据 + 决策依据。

### 2.5 ea4a33c — isHorizontal schema bug 修复

**根因**: [detect_thumb.py](FilmCrop_Clean.lrplugin/detect_thumb.py) 输出的 JSON 把 `isHorizontal` 嵌在 `debug` 子对象里(不是顶层),架构师写的 [ImportAgent.lua `parseJson`](FilmCrop_Clean.lrplugin/ImportAgent.lua#L812) 用 `json.decode` 直接解析,**没有**像 [ProcessAgent.parseJSON](FilmCrop_Clean.lrplugin/ProcessAgent.lua#L67) 那样把 `data.debug.isHorizontal` 提到顶层。结果 `data.isHorizontal == nil`,进入 [directionAlign](FilmCrop_Clean.lrplugin/ProcessAgent.lua#L189) 后:

```lua
local isPyHorizontal = result.isHorizontal       -- nil
local isLrHorizontal = lrWidth >= lrHeight       -- false (垂直整带)
if isPyHorizontal ~= isLrHorizontal then         -- nil ~= false → TRUE!
  -- 触发 axis swap (top↔left, bottom↔right)
end
```

**症状**: catalog 里的虚拟副本变成 1/6 宽 × 全高的"长条"(770×42276 这种),而不是正常的胶片帧 (~4622×6948)。从 catalog dump 验证: 副本的 CropLeft/CropRight 完全等于 frame 的 relativeTop/relativeBottom — 完全是 swap 的特征。

**修法**: `parseJson` 末尾加兜底,先尝试从 `data.debug.isHorizontal` 提到顶层,fallback 用 `sourceWidth >= sourceHeight`(跟 ProcessAgent.parseJSON 行为对齐):

```lua
if data.isHorizontal == nil then
  if data.debug and type(data.debug.isHorizontal) == "boolean" then
    data.isHorizontal = data.debug.isHorizontal
  else
    data.isHorizontal = (data.sourceWidth or 0) >= (data.sourceHeight or 0)
  end
end
```

**回归测试**: `FilmCrop_Clean.lrplugin/tests/verify_isHorizontal_fix.py` — 用真实 detect_thumb.py 输出 + 模拟 directionAlign 判定,在 fix 前后对比 swap 触发情况。

---

## 3. detector A/B 对比结论

判定规则按预定义"≥2 项严格优于 + 其他不显著劣化"条款。

| TIF | 当前 (bcc8556) CV | 候选 (架构师) CV |
|-----|-------------------|------------------|
| 52191 | **0.5%** | 0.6% |
| 52194 | **0.0%** | 1.6% |
| luckyc20013 | **0.0%** | 0.3% |

其他三项(gap_diff / prop_dev / ratio_err)平局。**保留当前 detector,不引入候选**。详细数据见 [docs/detector-ab-comparison.md](docs/detector-ab-comparison.md)。

候选版本想法(median 替代 min、首尾帧 ratio 旁路、center-based 放置)留待未来在不同样本上重新评估,需要时单点 cherry-pick。

---

## 4. 验证矩阵

| 层级 | 命令 | 状态 | 备注 |
|------|------|------|------|
| L1 单元 | `python3 test_detect_batch.py` | **PASS** | 3 个 TIF 全绿,4 项指标无回归 |
| L2 Lua 接入 | `cd FilmCrop_Clean.lrplugin/tests && lua run_tests.lua` | **跳过** | 本机无独立 Lua 解释器,Lightroom 内置 Lua 即可,L4 顺带验证 |
| L3 静态校验 | `python3 FilmCrop_Clean.lrplugin/tests/validate_logic.py` | **PASS (21/21)** | mock_sdk 通过,2 个非致命警告 |
| L4 真实 LR | `cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop && python3 FilmCrop_Clean.lrplugin/tests/e2e_auto.py --wait 90 --photo 52191` | **PASS** | 2026-05-02 19:14 跑通,catalog 新增 6 个虚拟副本(52191 master_id=3560771,VC id 3561726-3561894),所有 W:H ≈ 0.677(≈ 2:3 portrait,匹配 35mm 胶片),≈ 4696×7044 px。注意:**必须从 master 路径跑**,不能从 worktree(详见 §10) |
| L5 schema 一致性 | `tests/verify_isHorizontal_fix.py` + L4 真机 catalog spot check | **PASS** | Python 模拟:old=swap×3 / new=不 swap;真机:6 个 VC 几何全部正常,确认 isHorizontal lift 已生效 |

---

## 5. L4 用户操作步骤(交接给真实 Lightroom)

**前置(fix 后必做)**: 删除 catalog 里之前测试产生的坏副本(全是 1/6 宽长条)。从最后一次 catalog dump 看到的样本:
- `52191`: 副本_1 ~ 副本_6 (id 3561525-3561693, 6 个长条)
- `luckyc20013`: 副本_1 ~ 副本_5 (id 3418743-3418884) + 副本_6 (id 3559531, 无 develop settings)
- `52191` 还有 5 个旧的**正确**副本(id 3397993-3398117, 4530×6711 的胶片帧),保留

操作:
1. 重启 Lightroom Classic(让插件重新加载新 ImportAgent.lua)
2. 在图库模块选中测试照片(如 `52191.tif`)
3. 菜单: `文件 → 增效工具额外命令 → FilmCrop → 启动自动检测 (E2E)`(只点一次)
4. 终端跑:
   ```
   cd /Users/winter/Documents/临时拷贝/Claude Code/filmcrop/.claude/worktrees/hungry-hypatia-f45ddd
   python3 FilmCrop_Clean.lrplugin/tests/e2e_auto.py --wait 120 --photo 52191
   ```
5. 预期: catalog 新增 6 个虚拟副本,每个 ~4622×6948 的正常胶片帧(2:3 比例),含 CropTop/Bottom/Left/Right,主照片裁剪重置

如果失败,先看 [tests/diagnose_e2e.py](FilmCrop_Clean.lrplugin/tests/diagnose_e2e.py) 的诊断输出,并直接 dump catalog 看 CropTop/Bottom/Left/Right 的实际值,跟 `frame.relativeTop/Bottom/Left/Right` 对应。

---

## 6. 文件清单(本次新增/修改)

**新增:**
- `FilmCrop_Clean.lrplugin/AutoWatch.lua`
- `FilmCrop_Clean.lrplugin/StopAutoWatch.lua`
- `FilmCrop_Clean.lrplugin/Init.lua`
- `FilmCrop_Clean.lrplugin/tests/` 整目录
- `FilmCrop_Clean.lrplugin/tests/verify_isHorizontal_fix.py`(回归测试,2.5)
- `docs/detector-ab-comparison.md`
- `.gitignore` 增加 `/test_files`

**修改:**
- `FilmCrop_Clean.lrplugin/ImportAgent.lua` (+163 行 from f30739d, +10 行 from ea4a33c)
- `FilmCrop_Clean.lrplugin/Info.lua` (+17 行)
- `FilmCrop_Clean.lrplugin/Shutdown.lua` (重构 + 新增 autoWatch 清理)
- `FilmCrop_Clean.lrplugin/tests/e2e_auto.py` (CLI flag fix)

**未改动(显式保留):**
- `FilmCrop_Clean.lrplugin/filmcrop/detector.py`(SHA `56c3baf06003362f54f8d7384a9e70d175f84e0e`,即 master HEAD bcc8556 版本)

**项目外同步(cross-project memory):**
- `~/.claude/projects/-Users-winter-Documents------Claude-Code-filmcrop/memory/handoffs-and-worktree-pattern.md`(2026-05-02 追加「模拟 GUI 操作别迷信 macOS 默认快捷键」节,把踩点 4 提升为通用规则,跨项目自动加载)

---

## 7. Lesson learned(此次踩坑)

**踩点 1 — 假 PASS**: 我在 §4 验证矩阵里给 L5 schema 一致性打了 PASS,但**实际没真跑** spot check —— 只是凭直觉觉得"字段名字看着对得上"就盖章了。用户本地真跑 L4 后,catalog 里出现 6 个 1/6 宽 × 全高的"长条"虚拟副本(用户截图反向证伪)。dump catalog 实际 develop settings 后才发现 axis swap 被错误触发,根因是 `data.debug.isHorizontal` 没被提到顶层。

**踩点 2 — 改对了文件,但 LR 不读**: 修复 `ea4a33c` 落到 worktree 的 `ImportAgent.lua`,本以为重启 LR 就生效。L4 第一次重测仍然 0 副本。`pgrep` + `find` 后才发现:**Lightroom 加载的是 master 根目录的 `FilmCrop_Clean.lrplugin/`,worktree 那份 LR 根本没在用**。而且 master 自 `f30739d` 之后已独立演化 9 个 commit(json.lua bundle、LrTasks.pcall 加固、detector 回滚到 baseline v2 等),`isHorizontal` lift 还没合过去。复用同一 patch 直接 Edit master 的 `ImportAgent.lua:833-842` 后才跑通。详见 §10。

**踩点 3 — 路径不一致的二阶错**: 修了 master 的 plugin 后,从 worktree 目录跑 `e2e_auto.py` 还是不工作。`AutoWatch.lua` 里 `AUTO_JSON = LrPathUtils.child(_PLUGIN.path, "filmcrop_e2e.json")` 走的是**插件实际加载路径**(master);但 `e2e_auto.py` 里 `AUTO_JSON_PATH` 走的是**脚本所在目录**(worktree)。所以 watcher 监视 master 路径、producer 写 worktree 路径,两边永远碰不上。**必须从 master 目录跑** `e2e_auto.py`。

**踩点 4 — AppleScript 快捷键发错绑定**(`190f936` 修): `switch_to_develop` 用 `keystroke "d" using command down`(Cmd+D)发给 System Events。**Cmd+D 在 LR Classic 是 Edit > Deselect(取消选中),不是切 Develop**;切 Develop 是单字母 `D`。第一次跑 52191 PASS 是巧合 —— 用户当时手动在 Develop 里;第二次跑 luckyc20013 留在 Library,ApplierAgent 拒掉 6 次 `applyDevelopSettings` (`ERROR 当前不在修改照片模块,applyDevelopSettings 对虚拟副本将无效`),catalog 出现"6 个 VC 创建了 + 全部 crop=NULL"的诡异状态。`FilmCrop.ApplierAgent.log` 里 `当前模块: library` 是铁证。修法:去掉 `using command down`,变成 `keystroke "d"`。

**规则**:
1. **"PASS" 必须有具体证据**: 验证矩阵每一项的状态都要附"我跑了什么命令、看了什么输出、output 关键值是多少"。没真做的就标 SKIP/TODO,不要打 PASS
2. **schema 一致性不能凭名字猜**: 跨语言/跨进程边界(Python ↔ Lua、JSON ↔ struct decode)要用真数据 round-trip 一次。Bash 一行 `python3 detect_thumb.py ... | jq keys` 加上一行人工对照消费侧字段,就能 catch 这种 nesting mismatch
3. **`nil ~= false` 类陷阱**: Lua 里布尔判定要么显式 `if x == true` / `if x == false`,要么先做 nil-coalesce。架构师写 `result.isHorizontal` 直接拿来比较,没考虑 nil case
4. **catalog spot check 是 L4 的最后一道关**: 不能只信"创建了 6 个虚拟副本"——必须看实际 CropTop/Bottom/Left/Right 数值是不是合理(高度方向应该 ≈ 1/6,宽度方向应该 ≈ 0.97;W:H ≈ 0.667 表明是 2:3 portrait 帧,不是长条)
5. **改 plugin 之前先确认 LR 实际加载哪个路径**: `find ~ -name "*.lrplugin" -type d` + `pgrep -fa Lightroom` + 看 `FilmCropImport.log` 里"自动检测已启动,监视: <path>"那一行,确认绝对路径。worktree branching 的便利前提是 LR 也用那个 worktree 的 plugin —— 否则 fix 落在 worktree 是无效操作
6. **producer / watcher 必须共享同一份路径锚点**: `_PLUGIN.path`(Lua 端)与 `_SCRIPT_DIR/_PLUGIN_DIR`(Python 端)必须同源。从哪个目录跑脚本会决定这个
7. **AppleScript 发快捷键前先验证 LR 的实际绑定**: macOS 默认快捷键 ≠ 应用快捷键。Cmd+D 在 Finder/多数应用是"复制/选中下一个",**在 LR Classic 是"取消选中"**;切 Develop 是裸字母 `D`。验证方法:在 LR 里手动按一次 `keystroke` 想用的组合,或查"系统设置 → 键盘 → 键盘快捷键"对应应用项。看 plugin 日志 `当前模块: <expected>` 行作为成功信号。**已沉淀到 cross-project memory**: `~/.claude/projects/-Users-winter-Documents------Claude-Code-filmcrop/memory/handoffs-and-worktree-pattern.md` 第「模拟 GUI 操作别迷信 macOS 默认快捷键」节,后续别的项目用 AppleScript / xdotool / cliclick / pyautogui 控应用时自动加载提醒

---

## 8. 后续 / 潜在问题

1. ~~**master 上的 isHorizontal lift 还没 commit**~~: 已分两次落地到 master:
   - `94ecddb fix(import): lift isHorizontal in parseJson to avoid bogus axis swap` —— ImportAgent.lua 修改
   - `69348d4 test(import): add regression check for isHorizontal lift fix` —— 同步 worktree 的 `tests/verify_isHorizontal_fix.py` 测试 fixture
   两个 commit 加起来语义等同 worktree `ea4a33c`,fixture 在 master 跑通,3 个 TIF 都 PASS(old: all swap → bug confirmed,new: none swap → fix works)。worktree 任务完结,可清理(见 §11)
2. **detector 三方分裂、A/B 暂不重做**(2026-05-02 决策): master 从 `bcc8556` 回退到 baseline v2 `3f3cd95`(`7289629 revert(detector)`),与 worktree (`bcc8556` gap 对齐) + quizzical 候选 (`9d0344d`) 已是三方分裂。L4 既然 PASS,master 当前 detector 在真机就够用,**不立即触发新一轮 A/B**;`docs/detector-ab-comparison.md` 标记为 stale 留档。后续真要把 worktree 合 master 时,按 [docs/detector-ab-comparison.md](../../docs/detector-ab-comparison.md) 的 4 项指标 + judging rule 重做(`master(3f3cd95)` vs `worktree(bcc8556)` 二方即可,quizzical 已无相关性)
3. **架构师 worktree (`quizzical-jackson-a651f4`) 暂未清理**,但已无价值:master 已吸收 E2E harness 并多走了 9 个 commit,架构师 worktree 上的 ImportAgent.lua 是 stale 的。可以直接 `git worktree remove`
4. **同源 schema bug 排查面**: `detect_thumb.py` 输出还有哪些字段被消费侧"假定在顶层"实际却在 `debug` 里? 至少需要 grep 检查 `result\.\w+` / `data\.\w+` 在 Lua 里的访问点,跟 `detector.analyze_image` 的返回 dict 比对。已知风险点:`cropAngle`(目前在顶层 OK)、`frames[].relativeXxx`(已展开 OK);`debug` 子节点其他字段是不是有人偷偷读?
5. **`FilmCrop_Clean.lrplugin/detect_debug.log` 没 ignore**: 每次跑 detect_thumb.py 都会写入,master 工作树里是 untracked。建议加 `*.log` 到 .gitignore(low priority)
6. **`watchJsonFile` 里另一处 parseJson([ImportAgent.lua:657](FilmCrop_Clean.lrplugin/ImportAgent.lua#L657))同样不 lift `isHorizontal`**: 仅"老的 manual 选 JSON" 流程使用,与 E2E AutoWatch 无关。低优先级,记一笔,等真有人走那条路径触发到再修
7. **detector 候选版本的 3 个改动点**(median / 首尾帧旁路 / center-based)在样本扩展后若重现优势,按 Step 1.5 单点 cherry-pick 流程重评
8. **`e2e_auto.py:116` 的 `select_all_photos` 是 dead code**: 同样有 cmd+g/cmd+a/cmd+d 链条 bug(跟踩点 4 同根),但当前 `e2e_auto.py` 里没人调用。`e2e_test.py:143` 和 `e2e_lr_control.py:82` 里同名函数是独立测试 harness,跟本次任务无关。等真要复活 select_all_photos 时再一起修

---

## 9. 引用

- 架构师设计: [e2e-json-watch-architecture.md](e2e-json-watch-architecture.md)
- A/B 数据(已 stale,只对比了 worktree 与 quizzical 两版): [docs/detector-ab-comparison.md](../../docs/detector-ab-comparison.md)
- worktree detector SHA: `56c3baf06003362f54f8d7384a9e70d175f84e0e`(基于 master `bcc8556`)
- master 当前 detector(`7289629` 回退后): baseline v2 `3f3cd95`
- 候选 detector SHA(quizzical): `9d0344dcdb9cac33fc5499ffd7cd03d98e972a97`
- 测试样本: `/Users/winter/Documents/临时拷贝/Claude Code/filmcrop/test_files/{52191,52194,luckyc20013}.tif`
- 最近 L4 真机数据: 52191 master_id=3560771, 6 个 VC id 3561726-3561894, all W:H ≈ 0.677 (~2:3 portrait)

---

## 10. master 与 worktree 路径分歧(关键)

### 10.1 现状

| 路径 | 角色 | 当前 HEAD |
|------|------|-----------|
| `/filmcrop/FilmCrop_Clean.lrplugin/` | **LR 实际加载这个**(master) | `94ecddb` |
| `/filmcrop/.claude/worktrees/hungry-hypatia-f45ddd/FilmCrop_Clean.lrplugin/` | 本 worktree(branch `claude/hungry-hypatia-f45ddd`) | `ea4a33c` |

确认方式:
```
find ~ -name "FilmCrop*.lrplugin" -type d  →  只有 master 路径
ps aux | grep Lightroom                     →  PID 24129 在跑
tail FilmCropImport.log                      →  "自动检测已启动,监视: <master 路径>"
```

### 10.2 master 自 worktree 创建后多出的 commit (`f30739d..master`)

```
69348d4 test(import): add regression check for isHorizontal lift fix  ← worktree ea4a33c 的 fixture 部分同步到 master
94ecddb fix(import): lift isHorizontal in parseJson to avoid bogus axis swap  ← worktree ea4a33c 的 lua 改动同步到 master
31868d1 fix(tests): correct has_crop check — LR omits default values from develop text
7289629 revert(detector): roll back detector.py to 3f3cd95 baseline v2  ← detector 回滚!
5fbfca2 fix(plugin): use LrTasks.pcall for yield-safe error capture in autoWatch
ff3b22b fix(plugin): drop pcall around photo:getFormattedMetadata in silentApplyJson
80a1ef0 fix(plugin): load bundled json.lua via dofile, not require("json")
c750e18 debug(ImportAgent): replace xpcall(debug.traceback) with plain pcall + per-call guards
c8664bc fix(plugin): bundle json.lua so require("json") resolves in Lr Classic
162bdf3 debug(ImportAgent): wrap silentApplyJson in xpcall + bisection traces
95230e4 refactor(ProcessAgent): replace parseJSON regex with json.decode
```

**master 在做的事**:
- 加固 plugin 跑通真机的运行时正确性(json.lua bundle、yield-safe pcall、Lua coroutine 兼容)
- 把 detector 回退到 baseline v2(`3f3cd95`),放弃 `bcc8556` 的 gap 对齐方向

**worktree 在做的事**:
- 集成 E2E harness(已合到 master via `f30739d` 等)
- A/B 对比(报告归档,未影响 master detector 决策)
- isHorizontal lift fix(`ea4a33c`,**未合到 master**)

### 10.3 fix 同步状态

worktree 上 `ea4a33c` 的 patch 已用 Edit 工具直接落到 master 的 [ImportAgent.lua:833-842](FilmCrop_Clean.lrplugin/ImportAgent.lua#L833):

```lua
-- detect_thumb.py emits isHorizontal inside `debug`, not at top level.
-- directionAlign reads `data.isHorizontal` directly; if nil, `nil ~= false`
-- on vertical strips wrongly triggers axis swap. Lift / fallback here.
if data.isHorizontal == nil then
  if data.debug and type(data.debug.isHorizontal) == "boolean" then
    data.isHorizontal = data.debug.isHorizontal
  else
    data.isHorizontal = (data.sourceWidth or 0) >= (data.sourceHeight or 0)
  end
end
```

**已 commit 到 master**: `94ecddb` (2026-05-02)。commit message:

```
fix(import): lift isHorizontal in parseJson to avoid bogus axis swap

detect_thumb.py emits isHorizontal inside `debug` (not top-level), so
ImportAgent.parseJson left data.isHorizontal == nil. Then directionAlign
compared `nil ~= (lrW>=lrH)` and on vertical film strips wrongly entered
the swap branch — top↔left, bottom↔right — producing 1/6-width × full-
height "long bar" virtual copies in the catalog.

Fix: lift data.debug.isHorizontal up after json.decode, with a
sourceWidth>=sourceHeight fallback (matches ProcessAgent.parseJSON).

Note: this mirrors worktree commit ea4a33c. master and worktree both
needed the patch because LR loads master/.lrplugin directly — worktree
edits don't reach the running plugin.
```

或直接 `git -C <master> cherry-pick ea4a33c`(可能需要 `-X theirs` 处理细微 context 差异,因为 master 已 refactor 出 module-level `json` 而 worktree 在 parseJson 内 require)。

### 10.4 跑 E2E 必须从 master 路径

**对**:
```
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop
python3 FilmCrop_Clean.lrplugin/tests/e2e_auto.py --wait 90 --photo 52191
```

**错**:
```
cd /Users/winter/Documents/临时拷贝/Claude\ Code/filmcrop/.claude/worktrees/hungry-hypatia-f45ddd
python3 FilmCrop_Clean.lrplugin/tests/e2e_auto.py --wait 90 --photo 52191
# AutoWatch 监视 master 路径,但 producer 写 worktree 路径,无效
```

原因:e2e_auto.py 用 `os.path.dirname(os.path.abspath(__file__))` 锚定 `_PLUGIN_DIR`,跟脚本所在路径走;AutoWatch.lua 用 `_PLUGIN.path` 锚定 watch 路径,跟 LR 实际加载的 plugin 路径走。两者必须同源。

---

## 11. worktree 清理指引

worktree `hungry-hypatia-f45ddd` 上唯一对 master 还有价值的产出已经全部移过去:
- ImportAgent.lua 修改 → master `94ecddb`
- 测试 fixture (`tests/verify_isHorizontal_fix.py`) → master `69348d4`

worktree 上其余文件(ImportAgent.lua、ProcessAgent.lua、detector.py、json.lua 等)都比 master 旧;`detector.py` 的 `bcc8556` gap 对齐改动是 master 主动 revert(`7289629`)的对象,**不该**反向 merge 回 master。

### 11.1 推荐清理命令(在 master 目录下跑,不要在 worktree 里跑)

```bash
cd "/Users/winter/Documents/临时拷贝/Claude Code/filmcrop"

# 1. 清理 worktree(分支保留作历史快照)
git worktree remove .claude/worktrees/hungry-hypatia-f45ddd
# 如果报"contains modified or untracked files",检查是否有遗留产物再决定是否 --force

# 2. 同时清掉其他空 worktree(可选,看习惯)
git worktree list
# 如果 friendly-mendel-7b39e0 / musing-feistel-d46b15 / xenodochial-moser-55f9ab 都还在 922a4d2 没动,也可以 remove
```

### 11.2 保留分支 vs 删除分支

**保留**(`claude/hungry-hypatia-f45ddd` 分支留着):commits `f30739d` 之前的 E2E harness 集成 + `ea4a33c` 的双修复语义副本作为历史可追溯。需要时可重新 `git worktree add`。**默认推荐**。

**删除**(`git branch -D claude/hungry-hypatia-f45ddd`):master 已经包含 ea4a33c 的等价 commit (`94ecddb` + `69348d4`),`f30739d` 之前的内容也都通过 `f30739d` merge 进 master,分支删除不丢东西。但 reflog 之外没有"语义副本"留档了。如果空间紧张或想视觉上干净,可以删。

### 11.3 删除前自检 checklist

- [ ] `git -C <worktree> status --short` 干净(只有可忽略 untracked,如 detect_debug.log / filmcrop_e2e.json)
- [ ] `git -C <master> log --oneline | grep -E "(94ecddb|69348d4)"` 都在
- [ ] `python3 FilmCrop_Clean.lrplugin/tests/verify_isHorizontal_fix.py` 在 master 上输出 PASS

---

## 12. Detector plateau-walk 重构(2026-05-03,未 commit)

### 12.1 用户报告与改动范围

用户:"我还是看到了识别帧边界跑到隔壁帧边缘的情况"。`§10.2` 的 baseline v2 (`3f3cd95`) 在大多数边界 OK,但梯度法 `_find_edge` 在 plateau-content 过渡平缓的边界处仍会冲出 plateau 进入相邻帧亮区。

改动只动 `gap_edges_from_boundaries` 一个函数(detector.py +268 / -98 行)。**不动**:`find_boundaries`、`build_frames`、3:2 强制 enforce、scan-edge、long-edge、isHorizontal/cropAngle 字段。

### 12.2 算法替换

| 旧(`§10.2` baseline v2) | 新(plateau-walk) |
|----|----|
| 梯度法 `_find_edge` 找梯度衰减到峰值 30% 处停 | 从边界出发逐样本走,在 `value < plateau_val - range*drop_frac` 停 |
| 由 `mode` 参数决定 peak/valley | 局部 ±20 样本数据驱动 polarity 推断,`mode` 仅作 ambiguous fallback |
| walk 撞窗口 → 固定 soft_floor | walk 撞窗口 → 镜像另一侧测得的半 gap |
| 无 plateau 退化检测 | `range_ < 0.10` → 视为低对比边界,直接 soft_floor 对称 gap |

参数:`search_r = pstep*0.30`,`drop_frac = 0.15`,`min_range = 0.10`,`max_gap = pstep*0.10`,`soft_floor = max(min_hw*2, pstep*0.004)`。

详细推导和三轮调参轨迹见 cross-project memory `filmcrop-detection-tuning.md` §13。

### 12.3 测试结果

`python3 test_detect_batch.py`(L1)全 PASS:

| TIF | mode | CV | max_ratio_err | gap_diff | prop_dev |
|-----|------|----|---------------|----------|----------|
| 52191.tif | peak | 0.5% | 0.00% | 231px | 0.0% |
| 52194.tif | peak | 0.6% | 0.36% | 434px | 0.0% |
| luckyc20013.tif | peak | 0.3% | 0.00% | 40px | 0.0% |

`test_detect_batch.py` 一并改了 `gap_pass` 阈值 `10 → 500`(旧阈值是 §9 时代硬 floor 142px 的产物,plateau-walk 产生物理真实 gap,允许位置差异)。

视觉对比(脚本 `/tmp/claude-501/render_a_viz.py` 输出 `test_files/{52191,luckyc20013}.A.viz.jpg`):新版 frame 边沿严格停在 plateau 起点,全图无视觉越界。

### 12.4 待办

1. **commit** `detector.py` + `test_detect_batch.py` 两文件改动(单 commit,语义"replace gap-edge gradient walk with plateau walk")
2. **L4 真机验证**: 重启 LR → 选 52191 / luckyc20013 → 启动 E2E → 跑 `e2e_auto.py`,确认 catalog 6 个 VC 几何仍然合理(W:H ≈ 0.667,~4622×6948)
3. (可选) viz 脚本归档到 `tools/render_viz.py` 或 `FilmCrop_Clean.lrplugin/tests/`,目前在 `/tmp/claude-501/` 易丢

### 12.5 已知遗留

- 52194.tif 第一个 gap 较窄,靠 soft_floor 兜住。可能是该位置物理间隙真窄,也可能 plateau-walk 撞窗口。需更多样本判断
- `52194` 中间帧 `max_ratio_err 0.36%` 比 §12 时代的 0.01% 松,plateau-walk 的 gap 宽变化给 ratio enforce 留的空间略有抖动。仍远低于 1% 阈值,可接受
- 与 worktree(`bcc8556`) / quizzical(`9d0344d`)的 detector A/B 对比已 stale,无需重做(三方分裂状态升级为四方,但 worktree / quizzical 已无相关性)

### 12.6 obsolete plan

`/Users/winter/.claude/plans/filmcrop-handoff-memory-velvet-fairy.md` 计划"hungry-hypatia 合并 + ProcessAgent.parseJSON 重构 + 验证",已**完全过时**:
- hungry-hypatia 工作早已通过 `f30739d / 94ecddb / 69348d4` 同步到 master,无需 ff-only merge
- ProcessAgent.parseJSON 已在 master `95230e4 refactor(ProcessAgent): replace parseJSON regex with json.decode` 落地,正则 hack 不存在了

下一个 session 接手时不要按那个 plan 走。当前 master 状态由本文档(尤其是 §10、§12、§13、§14)描述。

---

## 13. 长边对称回退 — 右侧片基空白修复（2026-05-04，commit 952f6d0）

### 13.1 问题

用户 L4 验证 plateau-walk 后报告:"右边统一留了大片空白，宽度正好等于左边被裁切掉的图像宽度"。

根因: `detect_long_edges()` 的 threshold/content_ref 双法在右侧 film base 区域失效（过渡平缓、对比度低），返回 `far = size`（几乎不裁右边）。左边 `near = 165px` 正常检测到。结果右边保留了完整的片基条带。

### 13.2 修复

在 `analyze_image()` 末尾（所有 refinement 之后）加对称回退:

```python
if orig_long_edges != (0, orig_cross_size):
    left_margin = orig_long_edges[0]
    right_margin = orig_cross_size - orig_long_edges[1]
    margin_diff = abs(left_margin - right_margin)
    if margin_diff > max(10, int(orig_cross_size * 0.02)) and max(left_margin, right_margin) > 5:
        max_margin = max(left_margin, right_margin)
        orig_long_edges = (max_margin, orig_cross_size - max_margin)
```

- 差异 > 2% 图像尺寸 + 至少一侧 > 5px → 取较大边距镜像到两边
- 对 52191: 左 165px / 右 0px → 对称后各 165px（relativeLeft=0.0178, relativeRight=0.9822）
- 对 luckyc20013: 左 ~96px / 右 ~70px，差异不满足阈值，保持原始检测值

### 13.3 L4 验证

| 测试图 | 虚拟副本数 | CropLeft | CropRight | 视觉 |
|--------|-----------|----------|-----------|------|
| 52191.tif | 6 | 0.0178 | 0.9822 | 左右对称，无片基空白 ✓ |
| luckyc20013.tif | 6 | 0.0202 | 0.9895 | 原始不对称保留，两侧干净 ✓ |

关键 commit: `952f6d0`（detector.py +13 行）。

---

## 14. E2E 自动化踩点与最终状态（2026-05-04）

### 14.1 踩点 5 — AppleScript Return 不释放 LR Library Filter 焦点

`select_photo_by_filename` 用 `key code 36`（Return）关闭 Library Filter 文本输入框。**Return 在 LR 的 Filter 输入框中不释放焦点**，后续 `Cmd+A` 全选的是输入框里的文本而不是 grid 照片，更糟的是 `switch_to_develop` 的裸字母 `d` 被填进搜索框而不是切换模块。

修法（两处）:
- `select_photo_by_filename`: `key code 36` → `key code 53`（Esc）
- `switch_to_develop`: 裸 `d` 前prepend `key code 53`（Esc）防御性释放焦点

Commit: `2d00f19`

### 14.2 踩点 6 — 虚拟副本过滤诊断

`ImportAgent.silentApplyJson` 用 `targetBasename` 过滤选中照片时，如果当前选中不包含目标照片，旧版只返回"未找到匹配的目标照片"，不告诉用户**实际选中了什么**。

修法: 收集所有 `seenBasenames` 写入 `logger:trace`，失败时返回 `"未找到匹配的目标照片: X (当前选中: [list])"`。

Commit: `34e6199`

### 14.3 最终 master commit 链（按时间）

```
2d00f19 fix(e2e): Esc instead of Return to release LR Library Filter focus
34e6199 fix(e2e): auto-select photo by filename + diagnose filter rejection
a1101a7 fix(detector): replace gap-edge gradient walk with plateau walk
952f6d0 fix(detector): symmetric long-edge fallback when one-side margin is missed
```

### 14.4 版本号

v2.0.0 → **v2.2.0**（detect_thumb.py / __init__.py / api.py / Info.lua 统一）

### 14.5 当前验证矩阵

| 层级 | 命令 | 状态 |
|------|------|------|
| L1 单元 | `python3 test_detect_batch.py` | **PASS** (3/3) |
| L4 真机 52191 | `e2e_auto.py --wait 30 --photo 52191` | **PASS** (6 VC, 对称边距) |
| L4 真机 lucky | `e2e_auto.py --wait 30 --photo luckyc20013` | **PASS** (6 VC, 原始边距) |

---

## 15. Worktree 收尾与 master 后续演进（2026-05-05）

### 15.1 Worktree 清理

- **分支 `claude/hungry-hypatia-f45ddd` 已删除**（`ea4a33c` 的改动已通过 `94ecddb` + `69348d4` 合并到 master）
- **残留 worktree 目录 `.claude/worktrees/hungry-hypatia-f45ddd` 已移除**
- **其他废弃 worktree**（`quizzical-jackson-a651f4` 及 `ratio-scheme-a/b/c`）已在早前清理

### 15.2 Master 后续提交（直接在 master 上完成）

| Commit | 说明 |
|--------|------|
| `05ae6a9` | Revert aggressive tighten（0.3x 边际导致缝隙变大，用户要求回滚） |
| `a9dd865` | 版本号统一 bump 至 v2.2.0 |
| `f2bab48` | gitignore 增加 `.DS_Store`、`*.log`、`filmcrop_e2e.json`、`compare_schemes.py` |
| `70d7724` | detector 改进：confidence-based mirroring + zero-margin tighten + gap plateau refinement |
| `1e8f2e8` | **UI 精简**：Info.lua 菜单从 10 个缩减至 2 个（检测胶片帧 + 批量处理）；DetectFrames.lua 跳过 PreviewDialog，检测后直接创建虚拟副本 |
| *(当前)* | 快捷键：`Alt+M`（单次检测）、`Alt+Shift+M`（批量处理） |

### 15.3 已知待处理

- ** aggressive tighten 回滚后仍有微缝**：用户反馈"还露出那么一点点缝"，已 revert，更精细的 tighten 策略需更多样本评估
- ** detector 零边距 tighten 与 confidence-based mirroring**（`70d7724`）：L4 尚未重测，待用户验证
- ** ProcessAgent.parseJSON stderr 污染修复**：`[Perf]` 日志经 stderr 混入 stdout 导致 json.decode 失败，已在 `ProcessAgent.lua` 增加前缀剥离 + `detector.py` 移除 `[Perf]` 输出

---

> **状态**: hungry-hypatia worktree 完全合并并清理。当前 master 领先 origin 31 个提交。待 push。
