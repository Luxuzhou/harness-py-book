# 实验三：Compact Instructions 对任务目标保持的效果

对应书稿 **6.6.3 Compact Instructions 防止任务目标丢失**。

## 研究问题

> 在 CLAUDE.md 中写入 Compact Instructions 段落，是否能显著降低 Compaction
> 压缩后 Agent "忘记剩余任务步骤"的概率？

章节当前的论断（第 1049-1060 行）：**加入 Compact Instructions 之后，
任务目标和关键约束更不容易在压缩过程中被丢掉**。这是本实验要验证的关键断言。

## 外部对标

Compact Instructions 是 Claude Code 的私有设计，未见学术论文或开源框架
讨论。本实验是对这一工程做法的首次独立量化测量。

## 实验设定

**任务**：5 步集成任务（把 CostTracker 集成到 Agent 运行时）。每一步都有
明确的 pytest 验证。任务描述详见 `fixtures/task_description.md`。

**关键操作**：在第 3 步完成后强制触发一次 Compaction（通过调低
`compress_threshold_pct` 到 0.3 实现），观察 Agent 能否继续完成第 4、5 步。

**自变量**：
- `variant`: `{without, with, with_structured}` 三变体
  - `without`: CLAUDE.md 无 Compact Instructions 段落
  - `with`: CLAUDE.md 含自然语言版 Compact Instructions
  - `with_structured`: CLAUDE.md 含结构化版（显式列出"保留"字段）Compact Instructions

**因变量**：
- `completion_rate`: 5 步全部通过 pytest 的比例
- `avg_steps_completed`: 平均完成的步数（0-5）
- `forgot_task_count`: 压缩后"明显偏离原任务"的运行数（LLM-as-judge 判定）
- `compact_triggered`: 确认 Compaction 确实被触发（校验实验有效性）
- `post_compaction_turns_to_recover`: 压缩后 Agent 恢复到正确任务轨道所需的轮数

**控制变量**：
- 模型：`deepseek-chat`
- 任务描述完全相同
- 除 Compact Instructions 段落外，CLAUDE.md 内容相同
- 压缩触发点固定（第 3 步完成后）
- `preserve_messages=4`

**样本量**：
- `--smoke`：每组 2 次，共 6 次
- 全量（实测）：**3 variants × 10 seeds = 30 次**

## 成本估算

单次 5 步任务约 15K 输入 + 3K 输出 token ≈ $0.01。全量约 $0.2。

## 实际产出

- `results/raw.jsonl`：每次运行的完整轨迹（30 行，3 variants × 10 seeds）
- 当前仓库只保留 `raw.jsonl` 落盘，未生成 `summary.csv` 和 PNG 图

## 复现命令

```bash
python experiments/ch06/exp3_compact_instructions/run.py --smoke
python experiments/ch06/exp3_compact_instructions/run.py
```

## 实测结论（已回填书稿 6.6.3 节）

- **without（无 Compact Instructions）pytest 全过率 80%**：在简单任务上，不写 Compact Instructions 反而最稳
- **with（朴素"保留所有步骤"）全过率 10%**：措辞模糊让 Agent 看到摘要后进入"重新规划"模式，与 without 的差异 Fisher 精确检验 p ≈ 0.005，高度显著（负面影响）
- **with_structured（结构化 `[x]`/`[ ]` 标记）全过率 60%**：结构化写法把全过率从 10% 拉回到接近 without 基线；摘要字符数从朴素版 814 字符降到 355 字符
- **结论**：Compact Instructions 不是"要不要写"的二元问题，是"怎么写"的措辞工程题。在简单任务上不写最安全，复杂/长会话/多 Agent 协作才是它真正的用武之地

## 限制

- 任务只有一种（集成任务）。对于长篇写作、复杂调试等其他任务类型，效果
  可能不同。
- DeepSeek-V3 在指令遵从度上可能与 Claude 有差异，Claude 的效果可能更好。
- n=10 样本量较小，显著性检验可能不足。如需更强证据，需要 n=30+。
