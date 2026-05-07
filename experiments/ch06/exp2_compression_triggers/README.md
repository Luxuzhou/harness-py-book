# 实验二：四级压缩的触发频率与 Token 控制效果

对应书稿 **6.2 四级压缩** 和 **6.3 Token 预算**。

## 研究问题

> 在一个 30 轮的代码分析任务中，Microcompact、Snipping、Compaction、Reactive
> 各自实际被触发多少次？Token 曲线是否被稳定控制在阈值以下？改变
> `preserve_messages` 和 `compress_threshold_pct` 会如何影响这些触发频率和
> 总 API 成本？

**研究问题已由本实验回答**（见下方"实测结果"）：在本书 18 次 30-轮运行中，Microcompact 是触发最多的那一级（主力承担），Snipping / Compaction 在高压配置下被命中，Reactive 在该任务规模下始终未触发。章节 6.2.1 节正文已经按这组数据修订，不再单独声称"某一种特定的触发次数"。

另外一条顺带测量的指标：Compaction 产生的摘要相对于被压缩内容的 token 比例（`summary_ratio`），对应书稿 6.2.3 的"摘要长度应控制在被压缩内容总量的 15%-20%"这条经验值。

## 外部对标

- Anthropic *Effective Harnesses*（2025-11）：给出 Compaction 的设计原则，
  未公开触发频率数据。
- Hermes Context Window Management：提出迭代摘要设计，无触发频率数据。

本实验提供首份在 DeepSeek-V3 上的触发频率曲线。

## 实验设定

**任务**：30 轮代码分析 + 工程任务混合序列（参见 `fixtures/task_script.json`）。
每轮由脚本定义执行哪个 tool（read_file / bash / grep），确保实验的轨迹可复现，
避免因 Agent 自主决策产生的方差。

**自变量**：
- `preserve_messages`: `{2, 4, 6, 8}`
- `threshold_pct`: `{0.70, 0.80, 0.90}`

**因变量**：
- `microcompact_count`: L0 触发次数
- `snip_count`: L1 触发次数
- `compact_count`: L2 触发次数（含 LLM 调用）
- `reactive_count`: L3 触发次数
- `token_curve`: 每轮后的总 token 数（30 个点的时序）
- `api_errors`: prompt too long 错误次数
- `summary_ratio`: Compaction 生成的摘要 token / 被压缩内容 token 的平均比例
- `total_llm_calls`: 总 LLM 调用（主任务 + 压缩摘要）

**控制变量**：
- 模型：`deepseek-chat`
- 温度：0
- 固定任务脚本（30 步骤）
- 上下文窗口：128K

**样本量**：
- `--smoke`：只跑默认配置（preserve=4, threshold=0.80），1 个种子
- 全量（实测跑法）：**3 preserves × 3 thresholds × 2 seeds = 18 次 30-轮运行**（preserve ∈ {2, 4, 8}，threshold ∈ {0.70, 0.80, 0.90}，seeds ∈ {7, 42}）

## 成本估算

单次 30 轮运行约 150K 输入 token + 20K 输出 token，按 DeepSeek-V3 定价
`$0.28 / $1.10 per MTok` 估算约 $0.07。

- `--smoke`：~$0.1
- 全量：~$2.5

## 实际产出

- `results/raw.jsonl`：每次运行的原始记录（18 次 30-轮 run）
- `results/summary.csv`：按配置聚合的均值
- 当前仓库只保留 `raw.jsonl` 与 `summary.csv` 两项数据落盘；`plot.py` 与图文件未生成，读者若要可视化可基于这两份数据自行绘制

## 复现命令

```bash
python experiments/ch06/exp2_compression_triggers/run.py --smoke
python experiments/ch06/exp2_compression_triggers/run.py
```

## 实测结论（已回填书稿）

- **Microcompact 主力承担**：18 次 30-轮运行中，Microcompact 是各级压缩里触发次数最多的，符合"轻级主力、重级兜底"的设计意图
- **Snip / Compact 高压触发**：在较低 threshold（0.70）或较小 preserve（2）的配置下 Snipping / Compaction 开始命中
- **Reactive 未触发**：在本任务规模（30 轮、128K 窗口）下 Reactive 始终未被触发，说明前三级压缩已经足以把 token 曲线压在阈值之下
- **preserve / threshold 的权衡**：preserve 越小压缩越激进、API 调用次数越多；threshold 越低压缩触发越早但更频繁。具体甜点值依赖任务类型，书稿未给出单一推荐值

## 限制

- 固定任务脚本限制了外部有效性。真实 Agent 会因工具选择分歧产生不同轨迹。
- DeepSeek-V3 的 tokenizer 差异未被精确建模，`len(content) // 4` 的估算
  可能偏离真值 ±15%。
- 只测 1 个模型。扩展到 Claude 和 GPT 需额外成本。
