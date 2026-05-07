# Ch12 实验索引

## `run_all_cases.py`

对应书稿 12.1.2 节"三个案例的消耗模式对比"。

顺序执行 `cases/` 下的三个实战案例（refactor_enterprise / data_compliance /
multiagent_enterprise），为每个案例记录：

- 总轮数、工具调用次数
- 分 token 类型的消耗（input / output / cache hit / cache miss）
- 按工具类型分桶的消耗结构
- 成本估算
- wall-clock 耗时

用于 12.1 节"一次运行到底是什么构成了账单"的量化论据。

## Harness 内核必须被实验捕获

第 12 章的全量实验不再手写一套简化配置，而是直接调用三个 case 自己的
`run.py`。这样捕获到的是同一套 Harness 生产控制面：

- Ch9：规划门禁、路径权限、Hook、CLAUDE.md 注入、verify gates。
- Ch10：fail-closed post-hook、只读样本数据、网络隔离、PII 脱敏、pytest gates。
- Ch11：分阶段 round_plan、并行开发组、角色 cwd 隔离、共享产物、QA 收敛。
- Ch12：同一 `CostTracker` 定价表、未知模型显式暴露、session/metrics/cost_summary 一起归档。

上线前的离线门禁：

```bash
python experiments/check_ch09_ch12_kernel.py
python examples/ch12_observe.py
```

### 复现命令

```bash
cd experiments/ch12
python run_all_cases.py
```

需要 `OPENAI_API_KEY`（或 `HARNESS_API_KEY`）设置在 `.env`。完整复现约 40 分钟，
单案例成本约 1-3 美元，三案例合计 5-8 美元。

## 历史命名

本目录由原 `experiments/ch11/` 顺延而来。书稿 2026-04 在 Ch7 之后增设
Ch8《反馈调节》，后半篇章节号集体 +1，本章对应新 Ch12"观测、成本与生产部署"。
