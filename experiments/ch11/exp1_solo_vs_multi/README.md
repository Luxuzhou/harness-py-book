# 实验 1：单 Agent vs 双 Agent vs 四 Agent

对应书稿 **11.1 跨 Java+Python 真实代码库的集成挑战** 和 **11.6 什么时候该用多 Agent**。

## 研究问题

11.1.1 节断言"Solo $9 不能用 vs 多 Agent $200 能用"——这个数字来自 Anthropic
的公开实验（Claude Sonnet）。但本书读者用 DeepSeek-V3，能否复刻这个结论？
更重要的是，多 Agent 的代价/收益曲线在不同复杂度任务上长什么样？

> 同一个跨 Java+Python 集成任务，用 Solo / 双 Agent（Dev+QA）/ 四 Agent
> （Architect+JavaDev+PythonDev+QA）三种配置跑，每档的 **成本 / 总轮数 / 任务
> 收敛率 / 上下文溢出次数 / 接口契约一致性** 各是多少？拐点在哪？

## 设计

**任务**：固定使用 `cases/multiagent_enterprise/` 的"临床路径系统智能预警"
完整需求（涉及 Java 后端 + Python 数据分析模块 + 双端契约一致）。

**三档 Agent 配置**：

| 档 | Agent 数 | 角色分配 | 共享上下文 |
|---|---------|---------|-----------|
| Solo | 1 | 一个全能 Agent，6 个工具全开 | — |
| Dual | 2 | Developer（写代码）+ QA（验证） | review.md 文件交换 |
| Quad | 4 | Architect / JavaDev / PythonDev / QA | plan.md / review.md + 角色 cwd 隔离 |

**控制变量**：
- 模型：deepseek-chat（全程同模型，温度 0）
- max_total_turns（所有 Agent 累计）：60
- 同一任务描述（来自 cases/multiagent_enterprise/TASK.md）
- 每档 3 seeds

**因变量**：
- `total_cost_usd`：所有 Agent 累计成本
- `total_turns`：累计轮数
- `task_resolved`：QA 最终验收通过 = 1
- `context_overflow_events`：单 Agent 上下文超限触发的紧急压缩次数
- `contract_consistency`：Java 接口与 Python 接口的字段是否一致（关键失败模式）
- `wall_seconds`：墙钟时间

**样本量**：3 档 × 3 seeds = 9 次完整运行（成本估算约 ¥80-100，需充分预算）

## 预期产出

- `results/raw.jsonl`：每次运行的原始观测
- `results/summary.csv`：(config) → 各指标均值与标准差
- `results/figures/cost_vs_resolved.png`：横轴成本、纵轴是否解决，三档散点
- `results/figures/turn_breakdown.png`：每档下分 Agent 的轮数分布
- `results/report.md`：可贴入 11.6 节的对照表

## 复现命令

```bash
# 冒烟（仅 Solo + Dual，1 seed，约 ¥10，10 分钟）
python run.py --smoke

# 全量（约 ¥80，60 分钟）—— 注意预算
python run.py

# 只跑某一档
python run.py --config quad --seeds 42
```

## 讨论框架（待数据回填）

回填后本节应回答：

1. **能力拐点**：Solo / Dual / Quad 的 task_resolved 率分别是多少？
   如果 Solo 30% / Dual 60% / Quad 90%，每加一倍 Agent 收益递减但仍正向；
   如果 Quad 比 Dual 没明显提升，说明 4 Agent 是过度设计
2. **成本爆炸**：三档成本比是多少？Anthropic 是 1:20+，DeepSeek 上是否
   也这么夸张？还是因为 DeepSeek 本身便宜，多 Agent 的相对成本可控？
3. **典型失败模式**：Solo 失败的原因（上下文溢出？还是能力不足？）；
   Quad 失败的原因（接口契约不一致？还是 QA 偷懒？）—— 关联 11.7.2
4. **决策准则**：什么样的任务该用 Quad？11.6.1 的"上下文溢出 / 技术栈 / 角色冲突"
   三标准在数据上是否成立？

## 限制

- 每档只 3 seeds，统计显著性弱；建议读者扩到 10+ seeds
- 任务固定为一个，不覆盖更小或更大的任务复杂度光谱
- 模型固定 DeepSeek-V3；Claude / GPT 上的对照值得未来补
