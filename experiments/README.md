# experiments/ — 实证代码

本目录存放"为书中数据负责的"实验脚本。区别于 `examples/`（教学脚本）：
`experiments/` 里的每一份代码都用于生成或复现某一个章节中引用的实验数据。

## 组织规范

```
experiments/
├── README.md                  本文件
├── chXX/                      每章一个目录，用章节号作前缀
│   ├── README.md              汇总该章的全部实验
│   └── exp<N>_<slug>/         单个实验，目录名为 expN_短描述
│       ├── README.md          本实验的目标、配置、指标、复现命令
│       ├── run.py             主入口
│       ├── fixtures/          实验依赖的测试夹具
│       ├── results/           原始数据输出（通过 .gitignore 排除）
│       └── plot.py            （可选）图表生成，与 run.py 解耦
└── _legacy/                   已被正式版本取代、但保留用于历史查阅的脚本
    └── README.md              说明每份文件的原始用途和被取代情况
```

## 命名约定

- 目录一律用 `chXX` 开头（`ch04`、`ch10`、`ch12`），跨章实验归入主引用章节
- 每个实验用 `exp<N>_<slug>/`，N 为 1 起始整数，slug 用下划线分词
- 结果文件统一放 `results/` 子目录，通过 `.gitignore` 不入版本库
- 图表输出位置：书配套图置于 `figures/`，实验过程图置于 `results/figures/`

## 当前索引

| 章节 | 目录 | 对应书稿位置 | 状态 |
|------|------|-------------|------|
| Ch3 | `ch03/exp1_three_round_safety/` | 3.3 三轮渐进安全实验 | 完整可跑（自带 mini-Harness） |
| Ch3 | `ch03/exp2_defense_layers_quantitative/` | 3.3 / 3.4 三层防御统计强化 | 骨架 + 攻击集 |
| Ch4 | `ch04/exp1_tool_description_eval/` | 4.6 节 工具描述评测（V1/V2 × V1/V2 prompt × 3 seeds） | **已跑全量**（4 档对照），数据已回填 Ch4 4.6 |
| Ch4 | `ch04/exp2_tool_count_impact/` | 4.4.3 节 工具数量膨胀 | **已跑**（探索性：tc=3 三 seed + tc=6/12/24/48 单 seed），数据已回填 |
| Ch4 | `ch04/exp3_schema_token_cost/` | 4.5.3 节 MCP Schema 隐性消耗 | **已跑**（离线计算，无需 API） |
| Ch4 | `ch04/exp4_description_length_curve/` | 4.6.7 节 description 长度-准确率曲线 | **已跑**（8 档 × 23 任务 × 3 seeds = 552 obs），数据已回填 |
| Ch5 | `ch05/exp1_agents_md_length/` | 5.1.3 节 AGENTS.md 长度效应 | 已跑，数据已回填正文 |
| Ch5 | `ch05/exp2_cache_stability/` | 5.4.3 / 5.5.2 节 Cache 前缀稳定性 | 已跑，数据已回填正文 |
| Ch5 | `ch05/exp3_prohibition_wording/` | 5.1.2 节 禁令遵从率 | 已跑，数据已回填正文 |
| Ch6 | `ch06/exp1_snr_decay/` | 6.1.1 节 长对话信噪比塌陷 | 代码完成，待跑 |
| Ch6 | `ch06/exp2_compression_triggers/` | 6.2 节 四级压缩触发条件 | 代码完成，待跑（results/ 当前为空） |
| Ch6 | `ch06/exp3_compact_instructions/` | 6.6.3 节 Compact Instructions 效果 | 待跑 |
| Ch6 | `ch06/exp4_dream_consolidation/` | 6.4.3 节 离线 Memory 整理 | **已跑**（无 LLM API，纯本地脚本），数据未回填章节 |
| Ch6 | `ch06/exp5_resume_awakening/` | 6.5 节 Session 持久化与断点续传 | 待跑 |
| Ch7 | `ch07/exp1_open_vs_closed_loop/` | 7.2.1 开环 vs 闭环 | 骨架 + 10 任务 |
| Ch7 | `ch07/exp2_loopguard_intervention/` | 7.4.5 LoopGuard 收敛 | 骨架 + 5 死循环场景 |
| Ch7 | `ch07/exp3_planning_turns_effect/` | 7.6.2 planning_turns 效果 | 骨架 + 10 任务 |
| Ch8 | `ch08/exp1_eval_framework_extended/` | 8.3 节 跨层 Eval 基础设施 | 框架骨架，待接入 |
| Ch8 | `ch08/exp2_failure_mining/` | 8.5 节 失败挖掘 | **可直接跑** |
| Ch8 | `ch08/exp3_redteam_goldenset/` | 8.7.5 节 Red Team 对抗集 | 骨架 + 26 条任务 + 两套 prompt |
| Ch9 | `ch09/exp1_refactor_metrics/` | 9.5 节 重构前后量化对照 | 骨架（before/after metrics + compare） |
| Ch10 | `ch10/hooks_defense/` | 10.3 节 Hook 三层防御 | 已完成 |
| Ch11 | `ch11/exp1_solo_vs_multi/` | 11.6 节 何时该用多 Agent | 骨架（solo/dual/quad 三档对照） |
| Ch12 | `ch12/run_all_cases.py` | 12.1.2 节 三案例消耗对比 | 已完成 |

> 章节顺延记录：2026-04 在 Ch7 之后新增 Ch8《反馈调节》，原 Ch8-Ch11 顺延为
> Ch9-Ch12，对应 `experiments/ch09→ch10`、`experiments/ch11→ch12`。
> Ch11 重新作为新 Ch11 实战三的实验目录，独立于原 Ch11 内容。

## 新增实验的流程

1. 在对应的 `experiments/chXX/` 下建 `exp<N>_<slug>/` 目录
2. 写 README：目标、变量、指标、复现命令、预期产出位置
3. 实现 `run.py`，支持 `--smoke` 最小规模
4. 跑 smoke 验证管道
5. 跑全量产数据
6. 如需图表，独立写 `plot.py`，读 `results/` 生成到 `results/figures/`
7. 将数据或图表写入对应章节的正文
