# Ch7 实验索引

对应书稿第 7 章《验证与对抗式评估》。

本章 5 组实验对应 5 条核心论点，全部在 DeepSeek-V3 上跑出统计数据。设计原则
是"实验是为了说明论点"——不是说明书风格，而是每组实验都把章节中一个反直觉
判断转为可复现的数据。

## 5 组实验

| 编号 | 目录 | 对应章节 | 论点 | 样本量 |
|------|------|---------|------|------|
| exp1 | `exp1_self_eval_blindspot/` | 7.1 | Agent 自评虚假阳性率 60% | 5 任务 × 3 seeds = 15 trials |
| exp2 | `exp2_pytest_closure/` | 7.2 | 框架强制 pytest 把通过率从 40% 拉到 100% | 5 任务 × 3 模式 × 3 seeds = 45 trials |
| exp3 | `exp3_judge_verbosity_bias/` | 7.3 | Naive judge 受 verbosity bias，BP judge 修复 | 9 策略 × 2 fixture × 3 seeds = 54 trials |
| exp4 | `exp4_loopguard_layered/` | 7.4 | 三层防御中 LoopGuard 是兜底；过度引导反效果 | 4 fixture × 4 档 × 3 seeds = 48 trials |
| exp5 | `exp5_planning_complexity/` | 7.5 | 文档式 plan-then-execute ≫ 机械式 | 12 任务 × 3 模式 × 3 seeds = 108 trials |

## 与其他章节的关系

- Ch3 实验测约束层，Ch7 测验证层，两者构成防御纵深
- Ch8（反馈调节）的输入是 session.jsonl，本章的"LoopGuard 介入日志"和
  "P3 灾难轨迹"会成为 Ch8 失败挖掘的素材
- exp3 的 BP judge 是 Ch11 多 Agent 协作中 Evaluator 角色的设计基础

## 跑实验前

仓库根 `.env` 配置 `DEEPSEEK_API_KEY`。每个实验目录下的 README 给出 smoke 与
全量复现命令。

## 数据产出

| 实验 | 数据文件 |
|------|---------|
| exp1 | `exp1_self_eval_blindspot/results/raw.jsonl` |
| exp2 | `exp2_pytest_closure/results/raw.jsonl` |
| exp3 | `exp3_judge_verbosity_bias/results/blindspot_30trials_final.jsonl` 等 |
| exp4 | `exp4_loopguard_layered/results/raw.jsonl` |
| exp5 | `exp5_planning_complexity/results/raw.jsonl` |
