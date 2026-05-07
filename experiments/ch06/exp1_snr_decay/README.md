# 实验一：上下文信噪比塌陷

对应书稿 **6.1.1 长对话后的信噪比塌陷**。

## 研究问题

> 在禁用压缩的情况下，随着对话轮次增加，上下文中"有用信息"（用户指令 + Agent 推理）
> 占比如何变化？Agent 对综合问题的回答质量是否随之下降？启用 Harness-py 的四级
> 压缩后，这条曲线能否被"拉平"？

章节当前的论断（第 17-63 行）是：**信噪比随轮次快速下降，10 轮后降至 2% 以下**。
这是实验必须复现或否证的关键断言。

## 外部对标

- Anthropic, *Effective Harnesses for Long-Running Agents*（2025-11）
  提出 "Context Rot" 概念，但未给出 SNR 的量化曲线。
- Lumer et al., *Don't Break the Cache*（arXiv:2601.06007, 2026-01）
  测量了长程 Agent 的 Cache 命中率，未直接测量 SNR。

本实验的贡献是**用本书 harness-py 栈在 DeepSeek-V3 上测出一条具体的 SNR 曲线**。

## 实验设定

**任务**：让 Agent 依次读取并分析 10 个预置 Python 模块，每个模块在对话中占一轮。

**自变量**：
- `compression`: `{off, on}` — 是否启用 Harness-py 的压缩
- `observation_turn`: `{3, 6, 10, 15, 20}` — 观察点（到第几轮）

**因变量**：
- `snr`: 有用字符 / 总字符（有用 = user + assistant 消息，噪声 = tool 返回）
- `total_tokens`: `compressor.total_tokens(messages)`
- `quality_score`: 在观察点让 Agent 回答一个综合问题（如"列出所有模块中出现的
  公共工具函数"），由 LLM-as-judge 给 1-5 分
- `recall_accuracy`: 综合问题答案中正确引用早期模块的数量（0-10）

**控制变量**：
- 模型：`deepseek-chat`（DeepSeek-V3, 128K 窗口）
- 温度：0
- 10 个模块内容固定（见 `fixtures/modules/`）
- 模块顺序固定
- system prompt 固定（简化版，不含 Memory）

**样本量**：
- `--smoke`：2 seeds × 2 观察点（turn=3, 10），共 8 次运行
- 全量（实测）：**3 seeds × 5 观察点 × 2 压缩配置 = 30 次运行**，数据已回填 6.1.1 节

## 实际产出

- `results/raw.jsonl`：每次运行的原始度量（30 行，3 seeds × 5 观察点 × 2 压缩配置）
- 当前仓库只保留 `raw.jsonl` 落盘，未生成 `summary.csv` 和 PNG 图；读者如需可视化可基于 `raw.jsonl` 自行绘制

## 复现命令

```bash
# 冒烟（约 $0.3，5 分钟）
python experiments/ch06/exp1_snr_decay/run.py --smoke

# 全量（约 $3，30 分钟）
python experiments/ch06/exp1_snr_decay/run.py
```

## 实测结论（已回填书稿 6.1.1 节）

- 关闭压缩：SNR 从第 3 轮的 ~10.7% 缓慢爬到第 20 轮的 ~11.9%，整体在 10-12% 之间震荡。"10 轮降至 2% 以下"是经验观察，本实验的任务规模下未复现到如此剧烈。
- 启用压缩：SNR 在第 10-15 轮出现拐点回升（峰值约 27.2%），说明压缩确实把无效 tool 结果剔除、让有效信号占比上升。
- **压缩的真正价值不在"提高 SNR 到某个数字"，而在"阻断腐烂"**：关闭压缩时 SNR 看似稳定，但那是"噪声吃满+有效信号绝对量下降"的稳态；启用压缩后 SNR 回升说明有效信号被重新挤回窗口。

## 限制

- 只测 DeepSeek-V3 一个模型。跨模型（Claude/GPT）需要额外成本。
- 模块内容是合成样例，与真实项目代码分布有差异。
- LLM-as-judge 本身是有偏的估计，和人工评分可能有 ±0.5 的误差。
