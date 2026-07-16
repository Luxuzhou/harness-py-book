# 跨项目多 Agent 案例 — 项目 Harness 配置

## 案例概述

跨 Java + Python 的真实业务系统集成开发：为已有的临床路径与数据合规系统新增"路径变异智能预警"模块。
本案例演示四 Agent 角色隔离编排：Architect、Java Developer、Python Developer、QA Engineer。

**关键区别**：本案例不自建业务代码。两个 Developer 角色的工作目录分别指向：

- Java 端 → `cases/refactor_enterprise/target_project/`（第 9 章案例的 Spring Boot 项目）
- Python 端 → `cases/data_compliance/target_service/`（第 10 章案例的 FastAPI 服务）

这是"单 Agent 上下文装不下整套业务"时必须引入多 Agent 编排的真实动因。

## Agent 角色隔离规则

### 1. Architect Agent
- **工具权限：** 只读（read_file, grep_search, glob_search, write_file 仅用于产出 plan）
- **工作目录：** 本案例目录（`cases/multiagent_enterprise/`），可读整个仓库，写仅限 `implementation_plan.md`
- **禁止：** 不可创建或修改第9章/第10章目录下的任何业务代码

### 2. Java Developer Agent
- **工具权限：** read_file, write_file, edit_file, bash(`mvn compile`, `mvn test`)
- **工作目录：** 固定在 `cases/refactor_enterprise/target_project/`
- **禁止：** 不可修改 `cases/data_compliance/target_service/` 下的任何文件

### 3. Python Developer Agent
- **工具权限：** read_file, write_file, edit_file, bash(`pytest`, `python`)
- **工作目录：** 固定在 `cases/data_compliance/target_service/`
- **禁止：** 不可修改 `cases/refactor_enterprise/target_project/` 下的任何文件

### 4. QA Engineer Agent
- **工具权限：** read_file, write_file, edit_file, grep_search, bash(`mvn test`, `pytest`)
- **工作目录：** 本案例目录；可读取第9章/第10章的测试目录，但只能写到编排目录下的 `test_report.md`
- **禁止：** 不可修改第9章与第10章的业务代码

## 接口契约管控

**核心规则：`spec/api_contract.yaml` 不可由单方修改。**

- 只有 Architect Agent 有权审批契约变更
- Java Developer 或 Python Developer 如需修改契约，须：
  1. 在其输出中标记 `[BLOCKED: 需要 Architect 审批契约变更]`
  2. 描述需要变更的内容和原因
  3. 等待 Architect 在下一轮审批

## 代码变更规则

- 每次代码变更后必须运行对应的验证命令：
  - Java 端：`mvn compile`（编译检查）
  - Python 端：`python -m py_compile <file>`（语法检查）
- Round 3（QA 阶段）必须运行完整测试：
  - Java 端：`mvn test`
  - Python 端：`python -m pytest -q`（在第10章 target_service 目录下）

## 文件结构

```
multiagent_enterprise/
├── CLAUDE.md                 # 本文件 — Harness 配置
├── TASK.md                   # 任务定义与编排流程
├── run.py                    # 四 Agent 编排执行脚本
├── verify.py                 # 验证脚本
├── spec/
│   ├── requirement.md        # 需求规格说明书
│   ├── api_contract.yaml     # OpenAPI 接口契约
│   └── architecture.md       # 现有架构说明
└── roles/
    ├── architect.md
    ├── java_developer.md
    ├── python_developer.md
    └── qa_engineer.md

（Java 与 Python 两端的业务代码不在本目录下，
 分别位于 cases/refactor_enterprise 与 cases/data_compliance。）
```

## 编排顺序

1. **Round 1** — Architect 分析需求与两端业务代码，输出 `implementation_plan.md`
2. **Round 2** — Java Dev + Python Dev **并行**开发（由 `parallel_groups={2: [...]}` 声明）
3. **Round 3** — QA Engineer 编写并执行跨项目测试，产出 `test_report.md`
4. **Round 4** — 按测试失败项分派修复（按需触发）

## 补偿面标注

多 Agent 隔离 + 工作目录锁定，补偿了模型当前的以下不足：

- 面对跨语言跨项目代码，单 Agent 上下文容易失焦 → 隔离视图
- Agent 在一侧修复时容易越界改动另一侧 → 工作目录 cwd 强约束
- 契约一致性往往被忽略 → Architect 单独审批 + QA 统一校验

当模型在长上下文理解与自我边界意识达到更高水平时，多 Agent 编排可以被单 Agent 替代；
但在"真实企业级代码量 + 强契约约束"的场景下，多 Agent 在较长时间内仍是首选。
