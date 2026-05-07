# exp2：闭环验证 vs 开环 vs Agent 自决

对应书稿 **7.2 pytest 驱动的闭环自验证**。

## 研究问题

7.2.1 节论断："闭环验证比开环显著提升可靠性"。当前章节只有定性叙述，
没有数据。本实验把"开环 vs 闭环"细化为三档对照，量化各档的最终通过率。

> 给定 5 个含双 bug 的修复任务（复用 exp1 任务集），三种 Harness 配置下
> 最终 pytest 通过率分别是多少？让 Agent 自决跑测试与框架强制跑测试的差距有多大？

## 设计

### 三档对照（关键变量：验证机制是谁的责任）

| 档 | 工具集 | 验证 | 含义 |
|---|---|---|---|
| **O1_no_bash** | read_file + edit_file | 无 | Agent 物理上无法跑测试，最纯粹的开环 |
| **O2_bash_optional** | read_file + edit_file + bash | Agent 自决 | Agent 想跑就跑，prompt 不强制——回答"自决跑测试是否可靠" |
| **O3_harness_forced** | read_file + edit_file | 框架强制 | Agent 报告完成后，框架独立跑 pytest，失败把 stderr 注入回灌一次重试 |

### 任务集

复用 `exp1_self_eval_blindspot/tasks/`（5 个任务，每个含 prompt 报告的
bug A + prompt 不提的隐藏 bug B）。

### 控制变量

- 模型：deepseek-chat，temperature=0
- max_iterations：第一次 8 轮，O3 retry 4 轮
- planning_turns: 0
- 每任务 3 seeds（smoke 用 1 seed）

### 关键指标

| 指标 | 含义 |
|---|---|
| `pytest_pass` | 框架最终独立验证（4 个测试全部通过 = 1） |
| `bash_calls` | O2 中 Agent 实际调用 bash 的次数 |
| `retry_triggered` | O3 是否触发了一次重试 |
| `tool_calls / cost_usd / wall_seconds` | 闭环代价 |

## Smoke 数据（5 任务 × 3 档 × 1 seed = 15 trials，约 ¥0.5）

```
O1_no_bash          pass_rate = 2/5 = 40.0%
O2_bash_optional    pass_rate = 2/5 = 40.0%
O3_harness_forced   pass_rate = 4/5 = 80.0%
```

**关键观察**：

1. **O2 vs O1 完全相同**——给 Agent bash 工具但不强制，DeepSeek 不会主动跑全量验证。
   即使有一个任务（b4_boundary）Agent 调用了 bash 6 次，仍然 FAIL——说明 Agent
   倾向于用 bash 做局部确认，而不是端到端的全量 pytest 闭环。

2. **O3 vs O1 翻倍**——框架强制验证 + 一次回灌重试，把 pass rate 从 40% 提到 80%。
   这是 7.2 节"闭环验证不可缺"论点的直接证据。

3. **O3 多花的成本**：retry 触发时多花 1 次 LLM 调用（约 +$0.003），但换来 +40pp
   通过率。性价比极高。

## 全量样本量

- smoke：15 trials，约 ¥0.5，3-5 分钟
- 全量：5 任务 × 3 档 × 3 seeds = **45 trials**，约 ¥2，10-15 分钟
- 任务集扩到 12 个后：12 × 3 × 3 = **108 trials**，约 ¥5，30 分钟

## 复现命令

```bash
# smoke
python run.py --smoke

# 全量
python run.py

# 仅跑某档（用于调试）
python run.py --conditions O3_harness_forced
```

## 讨论框架

回填后本节应回答：

1. **核心论点**：O3 vs O1 的 pass_rate 差距 = 强制闭环的边际价值
2. **反直觉发现**：O2 ≈ O1 说明"给 Agent bash 不等于闭环"——这是章节中
   "Bash 工具是闭环的物理基础但不是充分条件"的关键支撑
3. **代价分析**：O3 的 retry 开销 vs 通过率提升的性价比
4. **bash_calls 分布**：O2 中 Agent 平均跑了几次 bash？跑了之后是真在 verify 还是
   只在做局部探查？

## 限制

- 5 任务过少；需要扩到 12 个才有统计显著性
- 一次 retry 已经从 40% → 80%，但更多 retry 是否有边际收益未测
- pytest 输出有时含中文 docstring → Windows GBK 解码报错（仅日志噪音，不影响
  pass/fail 判定，已在 run_pytest 中用 bytes + utf-8 errors=replace 修复）
- DeepSeek 的"不主动验证"行为是否在 Claude/GPT 上不同未测——这是跨模型敏感性
  问题，留给后续实验
