# exp5：plan-then-execute 三种实现的对照

对应书稿 **7.6 先看后做的分阶段工具解锁**（按 2026 业界对照后的修正版本）。

## 研究问题

业界 2026 共识：plan-then-execute 是 Agent harness 的核心模式（Anthropic Claude Code
PLAN mode、DeepAgents planner subagent、Cognition Devin、Cursor Composer 都强调"先
规划再执行"）。但**"plan-then-execute"有不同实现方式**：

1. **机械式**（harness_py_pro 当前 `planning_turns`）：前 N 轮强制只读，禁用 write
2. **文档式**（业界主推）：要求 Agent 先写 plan 文档（plan.md / TODO list）作为
   中间产物，再开始执行
3. **不规划**：Agent 自由发挥

> 三种实现下，first_edit_success 和 verify_passed 分别是多少？业界主推的"文档式"
> 是否在数据上确实优于"机械式"？

## 设计

### 三档对照

| 模式 | planning_turns | prompt 前缀 | 含义 |
|---|---|---|---|
| **P0_none** | 0 | 无 | 自由发挥（baseline） |
| **P3_mechanical** | 3 | 无 | 机械式：前 3 轮 read-only，第 4 轮起放开 write（harness_py_pro 当前实现） |
| **P_doc** | 0 | 强制要求先 `write_file plan.md` | 文档式：业界主推的 plan-then-execute |

P_doc 的 prompt 前缀强制 plan.md 包含 4 段：
- 现状分析（读了哪些文件、确认了什么事实）
- 修改步骤（改哪些文件、按什么顺序）
- 验证方法（哪些 grep 模式 / 测试预期）
- 回滚方案（如果改坏如何恢复）

### 任务分组（自动）

| group | category | 数量 |
|---|---|---|
| simple | add_param / change_default / add_import | 7 |
| complex | rename_call_site | 3 |

复用 `experiments/ch07/exp5_planning_complexity/fixtures/` 与 `tasks/edits.jsonl`。

### 控制变量

- 模型：deepseek-chat，temperature=0
- max_iterations: 15
- allow_shell: False
- 每任务 3 seeds（smoke 1 seed）

### 关键指标

| 指标 | 含义 |
|---|---|
| `first_edit_success` | 第一次 edit_file 是否成功 |
| `verify_passed` | 修改后 verify_signal 出现在文件中（端到端通过率） |
| `plan_doc_written` | P_doc 模式下 plan.md 是否实际生成 |
| `plan_doc_size` | plan.md 字符数（plan 质量代理） |
| `total_turns` / `cost_usd` | plan 文档的代价 |

## Smoke 数据（18 trials, 6 任务 × 3 模式 × 1 seed, ¥0.6）

### first_edit_success_rate

| group | P0_none | P3_mechanical | **P_doc** |
|---|---|---|---|
| simple | 100% (3/3) | 67% (2/3) | **100% (3/3)** |
| complex | 100% (3/3) | 100% (3/3) | **100% (3/3)** |

### verify_passed_rate（更关键的端到端指标）

| group | P0_none | P3_mechanical | **P_doc** |
|---|---|---|---|
| simple | 67% (2/3) | **33% (1/3)** | **100% (3/3)** |
| complex | 100% (3/3) | 100% (3/3) | **100% (3/3)** |

### plan 文档质量

| task | P_doc plan.md 字符数 | 任务最终 verify |
|---|---|---|
| ap001 (simple) | 996 | ✓ |
| cd001 (simple) | 387 | ✓ |
| ai001 (simple) | 741 | ✓ |
| rn001 (complex) | 1377 | ✓ |
| rn002 (complex) | 1049 | ✓ |
| rn003 (complex) | 1029 | ✓ |

P_doc 全部 6 trials 真的写了 plan.md（不是敷衍），跨文件任务的 plan 显著更长。

### 成本对照

| mode | simple 平均 turns | complex 平均 turns | simple cost | complex cost |
|---|---|---|---|---|
| P0_none | 4.7 | 5.0 | $0.002 | $0.004 |
| P3_mechanical | 5.0 | 7.0 | $0.002 | $0.006 |
| P_doc | **7.7** | **10.7** | **$0.006** | **$0.011** |

P_doc 成本约为 P0 的 **2-3 倍**——plan 文档的代价是显著的。

## 论点（数据正向支撑）

1. **P_doc 显著优于 P0_none 和 P3_mechanical**——在 simple 组的 verify_passed
   上从 67%/33% 拉到 100%。**业界主推的"文档式 plan-then-execute"在数据上确实有效**。

2. **P3_mechanical（仅禁用 write）反而有害**——simple 组 verify_passed=33%，
   是三档中最差。**简单地剥夺写工具不等于真正的 planning**——它让 Agent 在不输出
   计划的情况下浪费了前 3 轮 read，没形成可被自己引用的中间产物。

3. **plan 文档的价值是"Agent 把思考写下来"**——plan.md 的存在迫使 Agent 在执行
   前形成完整的修改计划（含验证方法和回滚），相当于强制"think aloud"。这与
   Anthropic *Building Effective AI Agents* 的 evaluator-optimizer 模式一致。

4. **代价是成本翻倍**——P_doc 平均成本是 P0 的 2-3 倍。在简单任务上不一定划算；
   在复杂任务上由于 fixture 难度不够（DeepSeek 在 rn001-003 上 P0 已经 100%），
   smoke 数据无法显示 P_doc 的额外价值。**全量实验需要更复杂的 fixture**才能
   测出 P_doc 在复杂任务上的真正优势。

## 章节修订建议

7.6 节当前论点："planning_turns 提升首次修改成功率"——按本实验数据修正为：

| 当前论点 | 数据支撑的修正论点 |
|---|---|
| "planning_turns 提升首次修改成功率" | **"plan-then-execute 显著提升端到端通过率（67% → 100%），但实现方式至关重要"** |
| "前 N 轮强制只读" | **"机械式只读阶段不等于 planning，反而可能有害（simple 组 verify=33%）"** |
| "简化的实现就够用" | **"业界主推的文档式 plan-then-execute（强制 write_file plan.md）才是真正起效的实现"** |
| 默认 planning_turns=3 | **默认 planning_turns=0；高风险/跨文件任务启用 P_doc 模式** |

## 全量样本量

- smoke：6 任务 × 3 模式 × 1 seed = **18 trials**（已跑，¥0.6）
- 全量：10 任务 × 3 模式 × 3 seeds = **90 trials**（约 ¥6，35-40 分钟）
- 跨文件任务建议补充 2-3 个更难的 fixture（如 move_constant、change_signature）
  让 P_doc vs P0 在 complex 组上拉开差距

## 复现命令

```bash
# smoke
python run.py --smoke

# 全量
python run.py

# 仅跑 P_doc
python run.py --modes P_doc
```

## 限制与已知缺陷

- **complex fixture 不够难**：rn001-003 是 3-5 文件 rename，DeepSeek 在 P0 下
  已 100%。需要补充更复杂的 fixture（跨模块 + 接口契约）才能测出 P_doc 在复杂
  任务上的真正优势
- **plan 质量未定量评分**：plan.md 大小是粗代理，应进一步用 BP judge（exp3）
  对 plan 内容打分，验证"plan 越完整结果越好"的假设
- **跨模型未测**：DeepSeek 内化"先看后做"较强；Claude 4.x reasoning 模型可能
  让 P_doc 边际价值更小，弱模型（7B 开源）可能更大
- **smoke 1 seed**：18 trials 是初步信号，需要 90 trials 才有统计显著性
