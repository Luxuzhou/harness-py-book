# 章节与代码索引

本文档根据书籍附录 B 整理，用于快速定位第 1—12 章的代码、实验和验收入口。正式阅读时以书稿、仓库 `README.md` 和本索引为准。

## 仓库结构

| 目录 | 作用 | 适用章节 |
|---|---|---|
| `harness_py/` | 模块少、逻辑直观的教学层框架 | 第 3—7 章 |
| `harness_py_pro/` | 含 Hook、沙箱、多 Agent、观测和任务编排的生产层框架 | 第 8—12 章 |
| `examples/` | 不依赖或少依赖外部模型的最小示例 | 第 3—8 章、第 12 章 |
| `experiments/` | 章节实验和对照实验，部分需要模型 API | 第 3—12 章 |
| `cases/` | Java 重构、医疗合规和跨语言多 Agent 三个实战 | 第 9—11 章 |
| `tests/` | 教学层与生产层框架测试 | 全仓库 |
| `figures/` | 书中配图 | 第 1—12 章 |

## 章节导航

| 章节 | 主题 | 主要位置 | 最小运行入口 |
|---|---|---|---|
| 第 1 章 | Agent 困境与 Harness 边界 | `harness_py/token_budget.py`、`agent.py`、`figures/` | 阅读案例与图表 |
| 第 2 章 | Harness Engineering 方法论 | `harness_py/`、`harness_py_pro/` | 无需运行 |
| 第 3 章 | Agent 循环与约束层 | `harness_py/agent.py`、`config.py`、`loop_guard.py`、`experiments/ch03/` | `python -B examples/ch03_safety_demo.py` |
| 第 4 章 | 工具系统与 MCP | `harness_py/tools.py`、`experiments/ch04/` | `python -B examples/ch04_tools.py` |
| 第 5 章 | 上下文工程与 Prompt Cache | `harness_py/prompt.py`、`experiments/ch05/` | `python -B examples/ch05_context.py` |
| 第 6 章 | 记忆管理与上下文压缩 | `compressor.py`、`memory.py`、`session.py`、`experiments/ch06/` | `python -B examples/ch06_memory.py` |
| 第 7 章 | 验证与对抗式评估 | `harness_py/loop_guard.py`、`experiments/ch07/` | `python -B examples/ch07_verify.py` |
| 第 8 章 | 反馈调节与自我演化 | `harness_py_pro/skills.py`、`observe.py`、`experiments/ch08/` | `python -B examples/ch08_feedback.py` |
| 第 9 章 | 遗留系统重构 | `cases/refactor_enterprise/`、`experiments/ch09/` | `python -B cases/refactor_enterprise/run.py` |
| 第 10 章 | 医疗数据服务合规 | `cases/data_compliance/`、`experiments/ch10/` | `python -B cases/data_compliance/run.py` |
| 第 11 章 | 多 Agent 跨语言协作 | `cases/multiagent_enterprise/`、`harness_py_pro/swarm.py` | `python -B cases/multiagent_enterprise/run.py` |
| 第 12 章 | 观测、成本与部署 | `harness_py_pro/observe.py`、`token_budget.py`、`experiments/ch12/` | `python -B examples/ch12_observe.py` |

## 三个实战案例

- `cases/refactor_enterprise/`：Java Spring Boot 临床路径项目。`TASK.md` 定义任务，`CLAUDE.md` 定义约束，`run.py` 启动 Harness，`verify.py` 执行验收。
- `cases/data_compliance/`：FastAPI 医疗数据服务。重点覆盖 SQL 参数化、PII 脱敏、审计日志、错误处理和 CORS。
- `cases/multiagent_enterprise/`：由 Architect、JavaDeveloper、PythonDeveloper 和 QA 协作，`spec/api_contract.yaml` 是跨系统中心契约。

第 9—11 章会修改目标代码。运行前请创建 Git 快照、单独分支或案例副本；如果只阅读代码，不需要执行 `run.py`。
