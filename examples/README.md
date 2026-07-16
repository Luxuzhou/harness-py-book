# examples/ — 教学演示脚本

本目录的脚本是**框架行为的最小演示**。读者读到对应章节时一行命令跑通，看到防御层、压缩、Cache 边界等概念在框架里如何具体落地。

## 重要定位

| 维度 | examples/ | experiments/ | cases/ |
|------|-----------|--------------|--------|
| 是否调用 LLM | **基本不调**（除非脚本顶部明确说明） | **会调**，需要 API key | 调，端到端实战 |
| 输出 | 框架判定结果 / 可视化 / 统计 | 实验数据 jsonl + 报告 | 完整任务执行轨迹 |
| 跑一次成本 | 0（纯本地） | ¥0.5 - 5 | ¥1 - 100 |
| 教学意图 | "看防御层 / 压缩器 / Cache 边界怎么工作" | "复现书中数据" | "看完整 Agent 跑通业务" |

**特别注意**：`ch03_safety_demo.py` 演示的是**约束层各层防御的判定行为**（路径检查、命令黑名单、LoopGuard、Sandbox），不是 Agent 端到端跑任务。要看 Agent 真实对抗，请去 `experiments/ch03/exp1_three_round_safety/`（需 DeepSeek API）。

## 当前脚本清单

| 脚本 | 章节 | 是否调 LLM | 一句话作用 |
|------|------|----------|----------|
| `ch03_safety_demo.py` | 3.2-3.5 | 否 | 路径白名单、命令黑名单、LoopGuard、Sandbox 五段防御层判定演示 |
| `ch04_tools.py` | 4.2 | 否 | 六工具实现的最小调用演示（read / write / edit / grep / glob / bash） |
| `ch04_mcp_server.py` | 4.4 | 否 | MCP Server 的最小实现，可被任何 MCP 客户端连接 |
| `ch05_context.py` | 5.2-5.4 | 否 | CLAUDE.md 三层发现 + Cache 边界 + 安全扫描的演示 |
| `ch06_memory.py` | 6.2-6.5 | 否 | 四级压缩 + 五区 Token 预算 + Memory + Session 持久化的演示 |
| `ch07_verify.py` | 7.4-7.6 | 否 | LoopGuard + 自验证 + 分阶段规划的演示 |
| `ch08_feedback.py` | 8.5 | 否（可选 LLM） | 从 session.jsonl 挖失败模式，`--no-synthesis` 完全本地 |
| `ch12_observe.py` | 12.1 | 否 | jsonl session 解析 + Token 消耗按工具/角色聚合 |

## 与 experiments/ 的对应关系

| examples 脚本 | 配套 experiments（如要跑 LLM 真数据）|
|---------------|----------------------------------|
| ch03_safety_demo | `experiments/ch03/exp1_three_round_safety/` |
| ch04_tools | `experiments/ch04/exp1_tool_description_eval/` |
| ch05_context | `experiments/ch05/exp1_agents_md_length/`、`exp2_cache_stability/`、`exp3_prohibition_wording/` |
| ch06_memory | `experiments/ch06/exp1_snr_decay/` 到 `exp5_resume_awakening/` |
| ch07_verify | `experiments/ch07/exp1_self_eval_blindspot/` 到 `exp5_planning_complexity/` |
| ch08_feedback | `experiments/ch08/exp1_eval_framework_extended/` 到 `exp4_pareto/` |
| ch12_observe | `experiments/ch12/run_all_cases.py` |

## 跑前准备

无需 API key 即可跑全部 8 个 examples。仅需：

```bash
pip install -r requirements.txt
```

跑示例：

```bash
python examples/ch03_safety_demo.py
python examples/ch06_memory.py
python examples/ch12_observe.py
```
