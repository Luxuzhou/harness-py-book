# 实验四：工具描述长度的效果拐点

对应书稿 **4.6.7 跨模型可迁移性与三层优化边界**。

## 研究问题

> 单个工具的描述长度从 15 tokens 增加到 1172 tokens 时，DeepSeek-V3 在相关任务上的 First-call Accuracy 如何变化？是否存在一个峰值区间，超过它之后更长的描述不再带来改善、甚至反而下降？

**实测结果（2026-04）**：8 档 × 23 任务 × 3 seeds = 552 observations。FC% 曲线为倒 U 形：15 → 65.2%、45 → 85.5%、80 → 78.3%、146 → 79.7%、**303 → 97.1%（峰值）**、**521 → 97.1%（并列峰值）**、761 → 88.4%、1172 → 84.1%。峰值区为 303-521 tokens，远长于早期凭经验断言的"512 字符（≈ 128 tokens）拐点"。

## 外部对标

- Fabien Roger, *Contextual Positional Encoding*（arXiv:2402.05896, 2024-02）：发现长上下文内位置编码对注意力稀释的影响。
- OpenAI, *Function Calling Best Practices*（developers.openai.com）：强调清晰的函数名、参数描述、边界示例、控制初始工具数量；未给出明确的描述长度区间。
- Anthropic 的 Claude tool use docs：强调 detailed descriptions，建议至少 3-4 句，复杂工具可更长，未给出确切长度上限。本实验在 DeepSeek-V3 上实测的峰值为 303-521 tokens，761 tokens 开始出现稀释。

**本实验的贡献**：给 DeepSeek-V3 画一条"描述长度 vs First-call Accuracy"的实测曲线，定位对该模型的效果峰值区间。

## 实验设定

**核心方法**：在 `exp1_tool_description_eval/` 的 V2 描述基础上，**只改 `bash` 工具描述**的长度（从极简到极长 8 档，按 log 间距覆盖两个数量级），其他 5 个工具保持 V2 不变。测 `bash` 相关任务的表现。

**自变量**：
- `bash_desc_length`: `{15, 45, 80, 146, 303, 521, 761, 1172}` tokens（实测，以 `_variants.py` 为准）
    - 15：极简一句话
    - 45：+ 简短 NEVER
    - 80：+ 替代工具提示
    - 146：当前 V2 完整版
    - 303 / 521：完整 NEVER 列表 + translate 规则 + 示例（**峰值区**）
    - 761 / 1172：V2 + 大量冗余解释和重复强调（开始过约束反噬）

**因变量**：
- `first_call_accuracy`: bash 相关任务的首次命中
- `forbidden_hit_rate`: bash_confuse 类任务的误用率
- `bash_positive_accuracy`: 真正该用 bash 的任务（ba001-ba008）
- `glob_confuse_bash_hit`: 用户说 `ls *.py` 等 bash 命令的翻译命中率
- `grep_confuse_bash_hit`: 用户说 `grep X` 等翻译命中率

**控制变量**：
- 其他 5 个工具：V2 描述（不变）
- 任务子集：
    - bash_positive（8）：期望 bash
    - glob_confuse_bash（5）：期望 glob_search，诱导 bash
    - grep_confuse_bash（5）：期望 grep_search，诱导 bash
    - read_confuse_bash（5）：期望 read_file，诱导 bash
    - 合计 23 条任务 × 3 seed = 69 次/档 × 8 档 = 552 observations
- 模型：DeepSeek-V3，temperature=0
- System Prompt：V1（最小版）

**规模**：8 档 × 23 任务 × 3 种子 = 552 observations，约 60 分钟。

## 运行

```bash
cd experiments/ch04/exp4_description_length_curve/

# 冒烟（1档 × 5任务 × 1种子）
python run.py --smoke

# 某个长度档位调试
python run.py --length 400 --seeds 1

# 全量
python run.py
```

结果写入 `results/results.json`，支持续跑。

## 指标

每次任务记录：
- `bash_desc_length`：实验的 bash 描述长度
- `first_call_right` / `forbidden_hit`
- `category`：来自 golden_set
- `first_call`：实际选择的工具

聚合层输出：
- 每档位上的 4 个细分准确率曲线

## 实测结果（2026-04，DeepSeek-V3）

| tokens | FC% | Forbidden Hit% | bash_positive% |
|--------|-----|----------------|----------------|
| 15 | 65.2% | 30.4% | 87.5% |
| 45 | 85.5% | 13.0% | 95.8% |
| 80 | 78.3% | 18.8% | 91.7% |
| 146 | 79.7% | 10.1% | 70.8% |
| **303** | **97.1%** | **0.0%** | 91.7% |
| **521** | **97.1%** | 1.4% | 95.8% |
| 761 | 88.4% | 5.8% | 83.3% |
| 1172 | 84.1% | 7.2% | 75.0% |

实测曲线比早期"512 字符（≈128 tokens）拐点"假设的峰值位置**明显靠后**。书稿 4.6.7 节已更新为 303-521 tokens 峰值区。

### 诚实的局限

- 本实验只变 **bash** 一个工具的描述长度，其他工具保持不变。真实世界里"描述长度"是多工具的系统属性，单工具实验是简化版。
- "填充冗余内容"时我们用的是人为的重复和扩展，真实生产里长描述可能是**必要信息的累积**，不完全等价。
- 本实验结论限定在 DeepSeek-V3，其他模型（特别是 Claude）拐点位置可能大不相同——这正是 4.6.7 节强调"跨模型必须自测"的理由。
