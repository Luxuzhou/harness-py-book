# Ch11 实验索引

对应书稿第 11 章《实战三：跨语言系统集成的多 Agent 协作》。

## 当前实验

| 编号 | 目录 | 对应章节 | 状态 | 一句话目标 |
|------|------|---------|------|-----------|
| exp1 | `exp1_solo_vs_multi/` | 11.1 / 11.6 何时该用多 Agent | 骨架 + 编排门禁 | 同一跨 Java+Python 集成任务，分别用 1 / 2 / 4 Agent 配置跑，对比成本、轮数、收敛、上下文溢出 |

## 与 cases/multiagent_enterprise 的关系

`cases/multiagent_enterprise/` 是 4-Agent（Architect/JavaDev/PythonDev/QA）的完整实战。
本实验把同一任务用三档 Agent 配置都跑一遍，回答章节 11.1.1 节的核心断言：
"Solo 模式 $9 不能用 vs 多 Agent $200 能用"。

这是对 Anthropic 公开实验（同 prompt 同模型，Solo $9 失败 vs Multi $200 成功）的
**本书复刻**，用 DeepSeek-V3 + harness_py_pro 验证：

> 即使在便宜模型上，多 Agent 编排是否仍然能实现 Solo 做不到的任务？
> 成本上升 N 倍，能力提升能否 cover？

## Harness 内核必须被实验捕获

多 Agent 实验不能只统计"几个人更快"。必须证明编排层提供了单 Agent 没有的工程能力：

- **阶段性**：`round_plan` 固定 Architect → Java/Python Developers → QA → 修复 → QA，不允许每轮所有角色无差别运行。
- **角色边界**：JavaDeveloper 只在 Ch9 Java 项目 cwd 工作；PythonDeveloper 只在 Ch10 Python 项目 cwd 工作；QA 使用跨项目只读/命令验证边界。
- **共享产物**：`implementation_plan.md` 和 `test_report.md` 是唯一跨角色长期状态，Developer 通过编排器注入的共享产物读取计划，而不是越权读写编排目录。
- **Generator/Evaluator 分离**：Developer 负责生成改动，QA 负责契约与测试报告；收敛条件只看 QA 报告和 `verify.py`，不看 Developer 自述。
- **成本归因**：报告要按角色拆分 turns、tool_calls、tokens、cost，说明多 Agent 贵在哪里、值在哪里。

离线检查：

```bash
python experiments/check_ch09_ch12_kernel.py
python cases/multiagent_enterprise/verify.py
```
