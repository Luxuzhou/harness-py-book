# 实验二：工具集规模对选择准确率的影响

对应书稿 **4.4.3 为何少量工具优于大而全的工具集**。

## 研究问题

> 给 Agent 暴露 3 / 6 / 12 / 24 / 48 个工具时，First-call Accuracy 和每任务工具调用次数如何变化？是否存在一个拐点——超过它之后再加工具反而降低选择准确率？

章节当前的论断（第 790-814 行）是："工具数量并非越多越好，重点不是系统总工具数，而是每次对话中活跃工具集是否足够小"。目前这一论断**仅靠 Stripe 口头经验**，无本书栈上的量化证据。

## 外部对标

- Stripe, *How we built the Stripe Agent Toolkit*（2025-04）：500+ 工具规模下的工具选择准确率下降，但未公布具体曲线。
- Anthropic, *Building effective agents*（2024-12）：建议"从最小工具集开始"，但未量化"最小"是多少。
- Xu et al., *ToolLLM: Facilitating LLMs to Master 16000+ Real-world APIs*（arXiv:2407.16696, 2024-07）：大规模工具集需要 retriever 预筛选，暗示直接暴露过多工具不可行。

**本实验的贡献**：在 DeepSeek-V3 + harness-py-pro 栈上给出一条具体的"工具数 vs 准确率"曲线，并定位工程可用的工具数拐点。

## 实验设定

**核心方法**：复用 `exp1_tool_description_eval/` 的 Golden Set 和 capture-only framework，但给 Agent 暴露的工具集逐步扩大。除了 6 个真实工具外，用"noop 工具"（结构类似但功能无效）填充至目标数量。

**自变量**：
- `tool_count`: `{3, 6, 12, 24, 48}`
    - 3: 仅 read_file / edit_file / bash（最小可用子集）
    - 6: 完整的 V2 描述 6 工具（基线）
    - 12: 6 真实 + 6 noop（`noop_1` 到 `noop_6`）
    - 24: 6 真实 + 18 noop
    - 48: 6 真实 + 42 noop

**因变量**：
- `first_call_accuracy`: 首次工具选择命中预期
- `any_call_accuracy`: 多轮内命中
- `avg_calls_per_task`: 平均工具调用次数
- `total_tokens_per_task`: 平均每任务 Token 消耗（含 schema 开销）
- `p95_duration_sec`: 单任务 P95 响应时间

**控制变量**：
- 工具描述：V2（来自 `exp1_tool_description_eval/descriptions.py`）
- System Prompt：V1（最小版，排除 prompt 层影响）
- 任务集：`exp1_tool_description_eval/golden_set.jsonl` 的 100 条
- 模型：`deepseek-chat`，temperature=0
- 种子：`[42, 43, 44]`

**实际规模**：tc=3 档 3 seeds（228 observations），tc=6/12/24/48 档各 1 seed（每档 100 observations），合计 628 次调用。这是一次**探索性对照实验**，书稿 4.4.3 已据此把结论限定为"单 seed 观察"。读者若想得到统计显著性，可以按 5 档 × 100 任务 × 3 seeds = 1500 次调用的完整规模跑，预计约 2 小时。

## 运行

```bash
# 前置：.env 已有 DEEPSEEK_API_KEY
cd experiments/ch04/exp2_tool_count_impact/

# 冒烟（1 档 × 5 任务 × 1 种子）
python run.py --smoke

# 单档位（调试某个 tool_count）
python run.py --tool-count 12 --seeds 1

# 全量
python run.py

# 仅重绘（数据已在，画图时用）
python run.py --replot-only
```

结果写入 `results/results.json`，支持中断续跑（已完成的配置不重跑）。

## 指标

每次任务记录：
- `first_call_right` / `any_call_right`
- `n_calls`：工具调用总次数
- `input_tokens` / `output_tokens` / `total_tokens`
- `duration_sec`
- `tool_count`：该次实验的工具总数
- `all_calls`：完整调用序列

## 实测结果（2026-04，DeepSeek-V3）

实验前的预测基于 Stripe 经验，认为 12 工具起退化、48 工具严重下降。**实测结果与该预测不一致**（见书稿 4.4.3 表格）：

| 工具数 | FC% | AC% | AvgTokens |
|--------|------|------|-----------|
| 3  | 31.6% | 46.9% | 3,481 |
| 6  | 68.0% | 93.0% | 8,275 |
| 12 | 67.0% | 88.0% | 8,899 |
| 24 | 67.0% | 90.0% | 10,627 |
| 48 | 69.0% | 89.0% | 14,039 |

核心观察：
- tc=3 档严重退化（能力覆盖不足）
- 在 tc=6-48 区间内，FC% 在单 seed 噪声范围内没有观察到退化
- 主要代价随工具数线性增长的是 **schema 成本**（每 10 个 noop 工具约多 1,500 tokens）

这和 Stripe 经验不矛盾：Stripe 测的是 500+ 规模、有命名歧义的真实业务工具；本实验用的是一眼可识别的 noop 填充，不构成命名歧义，测的是不同的失败模式。

## 后续

数据已写入书稿 4.4.3 节。结论限定为"**探索性单 seed 观察**"，读者要把结论外推到自己的场景，应补跑完整 5 × 100 × 3 多 seed 对照。

### 诚实的局限

- 此实验的 noop 工具是"纯干扰"，真实 MCP 场景的冗余工具可能有部分重叠功能（会更坏），也可能有精准的名称引导（会更好）。本实验给出的是**纯注意力稀释下界**。
- 若读者将本实验换到 Claude 等强模型上，预期拐点会后移到 24-48。这正是 Ch4 4.6.7 "跨模型可迁移性"要展开的话题。
