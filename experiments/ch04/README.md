# Ch4 实验索引

第4章《工具系统与 MCP》的全部实证代码。四个实验覆盖第4章的四条关键论断，各自在 DeepSeek-V3 + harness-py-pro 栈上做一手验证。

## 实验清单

| 目录 | 对应章节 | 要验证的断言 | 状态 |
|------|----------|--------------|------|
| `exp1_tool_description_eval/` | 4.5.1 / 4.6 | 工具描述 V2（NEVER 前置、英文化、明确替代）优于极简 V1 | **已跑完**，4 档 3-seed 数据齐全 |
| `exp2_tool_count_impact/` | 4.4.3 | 在本次单 seed 探索中，6-48 工具区间未观察到 FC% 随工具数明显退化；主要代价是 schema 成本随工具数线性增长 | **已跑**（tc=3 三 seed，tc=6/12/24/48 单 seed；书稿定性为"探索性单 seed 观察"） |
| `exp3_schema_token_cost/` | 4.3.2 / 4.5.3 | schema token 成本离线测量；`cache_stability` 仅保留 append-only 参考（Cache 失效由 Ch5 exp2 支撑） | **已跑**（离线） |
| `exp4_description_length_curve/` | 4.6.7 | DeepSeek-V3 描述长度 FC 在 303-521 tokens 附近并列峰值（97.1%），两侧回落 | **已跑**（8 档 × 23 任务 × 3 seeds = 552 observations） |

## 快速开始

```bash
# 前置：根目录 .env 已配置
#   DEEPSEEK_API_KEY=sk-...
#   (exp3 不需要 API key)

cd experiments/ch04/

# 1. exp1_tool_description_eval 已有数据：直接看 comparison.md
cd exp1_tool_description_eval && cat comparison.md && cd ..

# 2. 跑 exp3（最快，纯离线，5 分钟内）
cd exp3_schema_token_cost && python run.py && cd ..

# 3. 跑 exp4（约 50 分钟，¥2）
cd exp4_description_length_curve && python run.py --smoke  # 先 smoke 验证
cd exp4_description_length_curve && python run.py          # 全量
cd ..

# 4. 跑 exp2（约 2 小时，¥6，最重）
cd exp2_tool_count_impact && python run.py --smoke
cd exp2_tool_count_impact && python run.py
```

## 产出映射（实验结果 → 书稿章节）

```
exp1_tool_description_eval/comparison.md           -> 4.6.5 / 4.6.6 的核心表格
exp2_tool_count_impact/results    -> 4.4.3 节的"工具数 vs 准确率"曲线
exp3_schema_token_cost/results    -> 4.5.3 节表格替换为实测数字
exp4_description_length_curve     -> 4.6.7 节的"303-521 tokens 峰值区"曲线
```

## 数据归档与回归测试

建议做法（参见 Ch5/Ch6 的习惯）：
1. 每次完整跑完的 `results*.json` 提交到仓库（作为 baseline）
2. 修改 descriptions.py / prompt_v2_template.py 前先跑 exp1_tool_description_eval 作为 pre-change 基线
3. 修改后重新跑，对比 before / after 两份 results，看有无回归
4. 对大改动，建议加一档 smoke 先跑 `--smoke` 验证框架不崩

## 与 Ch5/Ch6 的呼应

- Ch5 exp2_cache_stability 与本章 exp3 都关注 Prompt Cache，共同构成 Prompt Cache 的完整论据
- Ch5 exp3_prohibition_wording 与本章 exp1_tool_description_eval 都涉及负向约束措辞，可交叉引用
- Ch6 exp2_compression_triggers 与本章 exp2 都涉及"活跃工具集管理"，前者是上下文压缩，后者是工具数暴露

## 外部对标与引用

本章四个实验的外部对标论文/博客统一管理：

| 断言 | 外部源 | 本实验关系 |
|------|--------|-----------|
| 描述需要 NEVER 负向约束 | OpenAI Function Calling Guide | exp1_tool_description_eval 验证 |
| 工具数增加反而降低准确率 | Stripe Agent Toolkit (2025) | exp2 量化 |
| MCP schema 开销显著 | MCP Spec, Anthropic MCP docs | exp3 精确测量 |
| 描述长度存在注意力拐点 | Fabien Roger *Contextual Positional Encoding* | exp4 对模型定位 |
| 工具描述走 Prompt Cache | Anthropic Prompt Caching docs | Cache 命中与失效由 Ch5 exp2 实测；本章 exp3 只保留 append-only 场景参考 |
