# Detector A/B 对比报告 (2026-05-02)

## 背景

引入 [JSON-watch e2e 测试体系](.claude/handoffs/e2e-json-watch-architecture.md) 时,姊妹 worktree `claude/quizzical-jackson-a651f4` 同步带来了一份基于更老 baseline (922a4d2) 的 detector 改写。需要决定是否吸收。

两个版本的核心差异:

| 算法点 | 当前 master (bcc8556) | 候选 (架构师改写) |
|--------|----------------------|-------------------|
| scan 维度统计 | `np.min(middle_scan_dims)` | `np.median(middle_scan_dims)` |
| 首/尾帧 ratio | 强制(同中间帧) | 不强制 (`is_middle = (0 < i < n)` 旁路) |
| 帧放置 | gap-aligned (`prev_bottom + min_gap` 累积) | center-based (`(left_b + right_b) // 2`) |
| `min_gaps` / `prev_bottom` | 保留 | 删除 |

## 测试方法

`test_detect_batch.py` 在 `test_files/{52191,52194,luckyc20013}.tif` 上跑两轮,期间 swap `FilmCrop_Clean.lrplugin/filmcrop/detector.py`,记录四项指标。判定阈值:gap_diff ≤10px、CV ≤5%、prop_dev ≤5%、ratio_err ≤1%。

## 结果

两组都全 PASS,但中间帧高度变异系数 (CV) 有显著差异:

| TIF | 当前 CV | 候选 CV | 当前 heights | 候选 heights |
|-----|---------|---------|--------------|--------------|
| 52191 | **0.5%** | 0.6% | [6935, 7024×5] | [6935, 7044×4, 7176] |
| 52194 | **0.0%** | 1.6% | [6986×5, 6143] | [**7275**, 6986×4, 6143] |
| luckyc20013 | **0.0%** | 0.3% | [6853×6] | [**7017**, 6968×4, **7366**] |

其他三项 (gap_diff / prop_dev / ratio_err) 两组均为 0 或 0.01%,平局。

候选版本的首尾帧 "自然"扩张/缩减(52194 首帧 7275 vs 中段 6986; luckyc20013 尾帧 7366 vs 中段 6968),会拉散整带尺寸一致性。

## 决策

按预定义判定规则中"当前 detector 在 ≥2 项指标上严格优于,其他项不显著劣化"条款:**保留当前 detector,不引入候选版本**。

## 后续考虑

候选版本的几个想法在不同假设下仍有价值,留待未来评估:

- **median 替代 min**: 当扫描带某帧异常窄时(光学失真、抖动),median 比 min 更鲁棒。当前 3 张样本都没触发这个场景
- **首尾帧 ratio 旁路**: 如果胶片帧物理边界本身存在差异(打孔变形、张力不均),这个旁路会保留更真实的边界。当前样本看不出这个需求
- **center-based 放置**: 与 gap 对齐相互排斥。仅当未来出现 gap 累积漂移问题时考虑

需要时按 `Step 1.5` 单点 cherry-pick (median 改动最小、风险最低) 而非整体替换。

## 数据出处

- A 组(当前): commit bcc8556 detector.py, sha `56c3baf06003362f54f8d7384a9e70d175f84e0e`
- B 组(候选): quizzical-jackson-a651f4 worktree 的 detector.py, sha `9d0344dcdb9cac33fc5499ffd7cd03d98e972a97`
- 测试集: `/Users/winter/Documents/临时拷贝/Claude Code/filmcrop/test_files/{52191,52194,luckyc20013}.tif`
