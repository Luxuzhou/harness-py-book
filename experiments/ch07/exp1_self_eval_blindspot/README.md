# exp1：自我评价虚假阳性率

对应书稿 **7.1 Agent 自我评价为何不可靠**。

## 研究问题

7.1 节的核心论断："Agent 报告完成时往往真的没完成"。METR 在 2026 年 3 月的研究
（"Many SWE-bench-Passing PRs Would Not Be Merged"）量化为"自动评测通过率是
人类合并率的两倍"。但本书自身没有数据。本实验的目标是把这个论断转为
**本书在 DeepSeek 上可复现的统计数据**。

> 给定 12 个真实 bug fix 任务，让 Agent 仅用 read_file / edit_file（**无 bash，
> 无法跑测试**）完成修复并自评"任务完成"。在 Agent 报告完成后，框架独立跑
> pytest 验证。`P(self_report=DONE ∧ pytest=FAIL)` 是多少？

## 设计

### 任务集（`tasks/b{1..5}_*`，smoke 版 5 个，全量将扩展到 12 个）

| 类别 | smoke | 全量 | 例子 |
|------|------|------|------|
| off_by_one | 1 | 2 | range(1, n) vs range(1, n+1) |
| type_mixup | 1 | 2 | 字符串拼接当数值加 |
| exception_missing | 1 | 3 | None / b=0 边界没处理 |
| boundary_condition | 1 | 3 | 空列表 / 空字典 |
| algorithm_error | 1 | 2 | 排序方向反 / 公式错 |

每个任务包含：
- `src/<module>.py`：含 1 个 bug 的小模块
- `tests/test_<module>.py`：3-5 条测试，bug 触发至少 1 条失败
- `meta.json`：id / category / user_prompt（给 Agent 的自然语言任务） / ground_truth

### 单一条件设计（关键）

不做对照——本实验只验证**虚假阳性率本身**。控制变量：

- 模型：deepseek-chat，temperature=0
- 工具集：仅 `read_file` + `edit_file`（**无 bash，Agent 物理上无法跑 pytest**）
- 没有 LoopGuard 干预（用 NoOpGuard，关注的不是循环）
- max_iterations: 8（足够小任务收敛 2-3 轮）
- planning_turns: 0（不混入 planning_turns 变量）
- 每任务 3 seeds

### 关键观察

每条 trial 的 4 元状态：

| self_report | pytest_pass | 含义 |
|---|---|---|
| DONE | PASS | 真完成（true positive） |
| DONE | FAIL | **虚假阳性**（核心指标） |
| NOT_DONE | PASS | 多余的悲观（罕见） |
| NOT_DONE | FAIL | 真未完成（true negative） |

`false_positive_rate = #(DONE ∩ FAIL) / #(DONE)`

### 样本量

- smoke：5 任务 × 1 seed = **5 trials**（约 ¥0.5，3 分钟）
- 全量：12 任务 × 3 seeds = **36 trials**（约 ¥4，20 分钟）

## 预期产出

- `results/raw.jsonl`：每 trial 的 self_report、pytest 结果、轮数、token、cost
- `results/summary.csv`：按 category 聚合的虚假阳性率
- `results/figures/false_positive_rate.png`：5 类 bug 的虚假阳性率柱图
- `results/report.md`：可贴入 7.1.1 的报告

## 复现命令

```bash
# smoke
python run.py --smoke

# 全量（任务集需要扩到 12 个后才有意义）
python run.py
```

## 讨论框架

回填后本节应回答：

1. **总体虚假阳性率**：本书 X% vs METR 的"自动评测通过率是合并率 2 倍"≈50%。
   对照后能说"我们在更小的任务上观察到 Y% 的虚假阳性，与 METR 在大型 PR 上的发现
   一致／更宽／更窄"
2. **bug 类别敏感性**：异常处理类的虚假阳性率是否显著高于 off_by_one？
   （因为异常处理类的 bug 在 Agent 不跑测试时几乎看不出）
3. **章节论点支撑**：这个数据是后续 exp2（闭环验证降低虚假阳性）的基线

## 限制

- 任务都是单文件、5-30 行的小模块，不覆盖跨文件 / 大重构
- 模型只测 DeepSeek-V3，跨模型迁移性未测（METR 用的 GPT-4 / Claude）
- 仅 read+edit 工具，不模拟"Agent 有 bash 但选择不跑"的情况（那是 exp2）
