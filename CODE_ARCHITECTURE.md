# Harness-py Book 代码架构

## 设计原则

1. **从第3章起提供可运行脚本**：方法论章不强行配代码；第3章以后按章节提供 examples/chXX_*.py 或 experiments/chXX/ 的最小验证脚本。
2. **渐进式构建**：harness_py/包逐章叠加，每章加一个模块，前面的模块不动
3. **实战层分离**：Ch9-11用生产级框架（harness_py_pro/），不依赖教学层
4. **实验可复现**：experiments/下的脚本可独立验证书中的每个实验数据

---

## 章节 → 代码映射

### Ch1 Agent的困境（入门）
```
第1章不提供独立运行脚本
  - 正文用于提出问题、分析失败链路和建立 Harness Engineering 的判断框架
  - 配套材料为书中案例记录、表格和 figures/ 下的图表
  - 可运行代码从第3章开始进入 examples/ 与 experiments/
```
**依赖**：无


### Ch3 Agent循环与约束层（构建）
```
examples/ch03_safety_demo.py   ← 约束层防御判定演示
  - 路径白名单、命令黑名单、LoopGuard、Sandbox 五段判定
  - 不调用 LLM，无需 API
  - 真实 Agent 对抗数据见 experiments/ch03/

harness_py/config.py             ← 全局配置 + UTF-8初始化
harness_py/http_client.py        ← HTTP客户端（requests + 重试）
harness_py/agent.py              ← 核心循环（此阶段只有循环+约束，无压缩/记忆）
```
**依赖**：无（真实对抗实验需要 DeepSeek API key）
**验证**：`python examples/ch03_safety_demo.py` → 看到五段防御判定输出

### Ch4 工具系统与MCP（构建）
```
examples/ch04_tools.py         ← 6个工具从零实现 + MCP Server示例
  - read_file / write_file / edit_file / grep_search / glob_search / bash
  - 每个工具的独立测试
  - 一个最小MCP Server连接示例
  ~约350行

harness_py/tools.py              ← 工具注册表 + 6工具（线程bash + 编码修复）
```
**依赖**：无外部依赖（bash工具用subprocess）
**验证**：`python examples/ch04_tools.py` → 每个工具跑一个测试用例

### Ch5 上下文工程与Prompt Cache（构建）
```
examples/ch05_context.py       ← CLAUDE.md发现 + prompt组装 + 安全扫描演示
  - 扫描当前目录的CLAUDE.md文件
  - 演示Cache边界标记
  - 演示上下文文件安全扫描（注入10个威胁模式的检测）
  - 演示三层文档架构
  ~约150行

harness_py/prompt.py             ← Prompt组装 + 安全扫描 + Cache边界
```
**依赖**：无（纯文件系统操作）
**验证**：`python examples/ch05_context.py` → 显示发现的文档和安全扫描结果

### Ch6 记忆管理与上下文压缩（构建）
```
examples/ch06_memory.py        ← 四级压缩演示 + Token预算 + Memory系统 + Session持久化
  - Context Rot信噪比模拟
  - 四级压缩的逐级演示
  - Token预算五区分配
  - MEMORY.md + Dream整理
  - jsonl持久化演示
  ~约400行（内容最多的 examples 脚本）

harness_py/compressor.py         ← 四级压缩（迭代摘要 + 工具对修复）
harness_py/memory.py             ← Auto Memory + Dream
harness_py/session.py            ← jsonl持久化
harness_py/token_budget.py       ← Token预算
```
**依赖**：无（examples版用模拟数据，不需要API）
**验证**：`python examples/ch06_memory.py` → 显示压缩前后对比、预算报告

### Ch7 验证与对抗式评估（构建）
```
examples/ch07_verify.py        ← LoopGuard演示 + 闭环验证 + 分阶段规划演示
  - LoopGuard的四种检测场景
  - 自验证循环的代码模式
  - 分阶段工具解锁的演示
  ~约150行

harness_py/loop_guard.py         ← 循环守卫
harness_py/agent.py              ← 更新：加入分阶段规划 + LoopGuard集成
```
**依赖**：无
**验证**：`python examples/ch07_verify.py` → 显示LoopGuard介入的时机

### Ch8 反馈调节：让 Harness 自我演化（构建）
```
examples/ch08_feedback.py       ← 反馈闭环、规则沉淀、成本观测演示
```
**依赖**：无
**验证**：`python examples/ch08_feedback.py`

### Ch9 实战一：企业 Java 系统重构（实战）
```
cases/refactor_enterprise/
├── target_project/              ← 真实规模 Spring Boot 项目（92 个生产源文件 / 约 10,127 行）
│   ├── src/main/java/com/example/cp/   ← Controller / Service / DAO / DTO 八层分工
│   └── ...
├── CLAUDE.md                    ← 项目规则（Hook 范围、命名纪律、事务纪律）
├── TASK.md                      ← God Class 拆分与 API 契约不变的十项验收
├── run.py                       ← 单 Agent 编排入口
└── verify.py                    ← 静态验收（服务数、契约、测试、编译）
```
**依赖**：harness_py_pro/（生产级框架）+ DeepSeek API key
**验证**：`python cases/refactor_enterprise/run.py` → Agent 执行重构 → `python cases/refactor_enterprise/verify.py` → 量化对比

### Ch10 实战二：医疗数据合规（实战）
```
cases/data_compliance/
├── target_service/              ← 按业务域拆分的 FastAPI 服务（~15,000 行）
│   ├── app/api/routes/          ← 7 个域路由（patients / lab_results / ...）
│   ├── app/repositories/        ← 6 个 Repository（患者 / 检验 / 仪器 / 异常 / 审计 / Base）
│   ├── app/services/            ← 规则引擎、调度、数据导出
│   ├── tests/                   ← 单元测试与契约测试
│   ├── sample_data/             ← 合成样本（patients/lab_results/instruments + reference_ranges.json）
│   └── generate_sample_data.py
├── CLAUDE.md                    ← 三层防御规则（SQL / PII / 审计 / 沙箱 / 网络）
├── TASK.md                      ← 六项合规验收
├── run.py                       ← 单 Agent + Hook 执行入口
└── verify.py                    ← 静态合规验收（SQL / PII / 审计 / 沙箱 / 网络 / 测试）
```
**依赖**：harness_py_pro/ + DeepSeek API key
**验证**：`python cases/data_compliance/run.py` → 分析执行 → `python cases/data_compliance/verify.py` → 合规率报告

### Ch11 实战三：跨项目多 Agent 编排（实战）
```
cases/multiagent_enterprise/
├── spec/                        ← requirement.md / api_contract.yaml / architecture.md
├── roles/                       ← architect / java_developer / python_developer / qa_engineer
├── CLAUDE.md                    ← 多 Agent 编排配置 + 契约治理规则
├── TASK.md                      ← 四轮编排定义 + 角色隔离约束
├── run.py                       ← 四角色编排入口（cwd 指向第9章/第10章真实代码）
└── verify.py                    ← 跨项目一致性验证（anchors / 骨架 / 契约 / 产物）
```
**本案例不自建业务代码**：JavaDeveloper 与 PythonDeveloper 的 `cwd` 由 Harness 分别锁定到第9章的 `refactor_enterprise/target_project/` 与第10章的 `data_compliance/target_service/`。

**依赖**：harness_py_pro/ + DeepSeek API key（还要求第9章/第10章两个锚点目录存在）
**验证**：`python cases/multiagent_enterprise/run.py` → 四 Agent 编排 → `python cases/multiagent_enterprise/verify.py`

### Ch12 观测、成本与生产部署（进阶）
```
examples/ch12_observe.py       ← Token消耗追踪 + 成本建模 + 预算报告
  - 读取jsonl session文件，分析token消耗
  - 按工具类型的消耗分布图
  - 月度成本预测
  ~约100行
```
**依赖**：一个已有的jsonl session文件
**验证**：`python examples/ch12_observe.py`

---

## harness_py 模块的逐章叠加顺序

```
Ch3后的状态：
  harness_py/
  ├── __init__.py
  ├── config.py          ← 全局配置 + UTF-8
  ├── http_client.py     ← HTTP + 重试
  └── agent.py           ← 最小循环 + 约束（不含压缩/记忆/验证）

Ch4后新增：
  ├── tools.py           ← 6工具 + 工具注册表

Ch5后新增：
  ├── prompt.py          ← Prompt组装 + 安全扫描 + Cache

Ch6后新增：
  ├── compressor.py      ← 四级压缩
  ├── memory.py          ← Memory + Dream
  ├── session.py         ← jsonl持久化
  └── token_budget.py    ← Token预算

Ch7后新增/更新：
  ├── loop_guard.py      ← 循环守卫
  └── agent.py           ← 更新：加入压缩+记忆+验证+分阶段规划
                          （这是agent.py的最终版本）
```

---

## 验证矩阵

| 章节 | examples可运行 | 需要API | 需要前置章节 | 验证命令 |
|------|----------------|---------|------------|---------|
| Ch1 | ❌ | ❌ | ❌ | 无独立脚本，见正文案例与 figures/ |
| Ch3 | ✅ | ❌ | ❌ | `python examples/ch03_safety_demo.py` |
| Ch4 | ✅ | ❌ | ❌ | `python examples/ch04_tools.py` |
| Ch5 | ✅ | ❌ | ❌ | `python examples/ch05_context.py` |
| Ch6 | ✅ | ❌ | ❌ | `python examples/ch06_memory.py` |
| Ch7 | ✅ | ❌ | ❌ | `python examples/ch07_verify.py` |
| Ch8 | ✅ | ❌ | harness_py_pro | `python examples/ch08_feedback.py` |
| Ch9 | ❌ | ✅ | harness_py_pro | `python cases/refactor_enterprise/run.py` |
| Ch10 | ❌ | ✅ | harness_py_pro | `python cases/data_compliance/run.py` |
| Ch11 | ❌ | ✅ | harness_py_pro | `python cases/multiagent_enterprise/run.py` |
| Ch12 | ✅ | ❌ | harness_py_pro | `python examples/ch12_observe.py` |

---

## 目录总览

```
harness-py-book/
├── README.md
├── .env.example                     ← API key配置模板
│
├── examples/                        ← 第3章起的教学脚本（多数调 harness_py 模块）
│   ├── ch03_safety_demo.py          ← 约束层防御判定演示
│   ├── ch04_tools.py                ← 6工具验证 → harness_py/tools.py
│   ├── ch04_mcp_server.py           ← MCP Server（独立协议，自包含）
│   ├── ch05_context.py              ← 上下文发现 → harness_py/prompt.py
│   ├── ch06_memory.py               ← 压缩+Memory → harness_py/compressor.py、memory.py、session.py
│   ├── ch07_verify.py               ← LoopGuard → harness_py/loop_guard.py
│   ├── ch08_feedback.py             ← 反馈闭环与规则沉淀演示
│   └── ch12_observe.py              ← Token分析（纯jsonl解析）
│
├── harness_py/                      ← 教学层框架（~1500行，Ch3-7逐章叠加）
│   ├── __init__.py
│   ├── config.py                    ← Ch3: 配置
│   ├── http_client.py               ← Ch3: HTTP
│   ├── agent.py                     ← Ch3→Ch7: 核心循环（逐章更新）
│   ├── tools.py                     ← Ch4: 工具系统
│   ├── prompt.py                    ← Ch5: 上下文
│   ├── compressor.py                ← Ch6: 压缩
│   ├── memory.py                    ← Ch6: 记忆
│   ├── session.py                   ← Ch6: 持久化
│   ├── token_budget.py              ← Ch6: 预算
│   └── loop_guard.py                ← Ch7: 循环守卫
│
├── harness_py_pro/                  ← 生产级框架（~3,500行，15模块，Ch8-12用）
│   ├── __init__.py                  ← 包入口
│   ├── config.py                    ← 三层配置（Model/Agent/Hook）+ 沙箱配置
│   ├── client.py                    ← HTTP客户端 + 抖动重试
│   ├── provider.py                  ← 多Provider路由 + 断路器降级
│   ├── engine.py                    ← 核心循环（沙箱+Hook+权限+并行+压缩+成本+指标）
│   ├── tools.py                     ← BaseTool抽象 + ToolRegistry + 6工具
│   ├── sandbox.py                   ← 沙箱隔离（权限模式+网络+文件系统+危险命令）
│   ├── hooks.py                     ← Pre/Post Hook框架（合规支撑）
│   ├── permissions.py               ← 路径+工具权限检查器
│   ├── compact.py                   ← 四级压缩 + 迭代摘要 + 孤儿修复
│   ├── prompt.py                    ← CLAUDE.md发现 + 安全扫描 + 角色注入
│   ├── loop_guard.py                ← 循环守卫（4种检测）
│   ├── token_budget.py              ← Token精确估算 + 五区预算 + CostTracker
│   ├── observe.py                   ← 结构化Logger + Metrics + SessionAnalyzer
│   ├── memory.py                    ← Memory CRUD + Dream整理
│   ├── session.py                   ← jsonl会话持久化
│   └── swarm.py                     ← 多Agent编排（orchestrate + pipeline）
│
├── cases/                           ← 三个实战项目（Ch9-11，见下）
│   ├── refactor_enterprise/         ← Ch9: Java 企业项目重构（92 个生产源文件 / 约 10,127 行）
│   │   ├── TASK.md                  ← God Class 拆分 + 契约不变的十项验收
│   │   ├── CLAUDE.md                ← 重构约束规则
│   │   ├── run.py / verify.py       ← 运行 + 静态验收脚本
│   │   └── target_project/          ← 完整 Spring Boot 项目（Controller/Service/DAO/DTO 八层）
│   ├── data_compliance/             ← Ch10: 医疗数据合规（约 15,000 行 Python）
│   │   ├── TASK.md                  ← 六项合规验收
│   │   ├── CLAUDE.md                ← 三层防御规则（SQL/PII/审计/沙箱/网络）
│   │   ├── run.py / verify.py       ← 运行 + 合规验证
│   │   └── target_service/          ← FastAPI 服务（api/repositories/services/tests 六层）
│   └── multiagent_enterprise/       ← Ch11: 跨项目多 Agent 编排（编排骨架 + cwd 指向第9章/第10章）
│       ├── TASK.md                  ← 四轮编排定义 + 角色隔离约束
│       ├── CLAUDE.md                ← 契约治理规则
│       ├── spec/                    ← requirement.md / api_contract.yaml / architecture.md
│       ├── roles/                   ← architect/java_developer/python_developer/qa_engineer
│       └── run.py / verify.py       ← 运行 + 跨项目一致性验证
│
├── experiments/                     ← 书中数据对应的实验脚本
│   ├── ch03/                        ← 约束层真实对抗与量化防御
│   ├── ch04/                        ← 工具描述、工具数量、Schema 成本
│   ├── ch05/                        ← AGENTS.md、Prompt Cache、禁令措辞
│   ├── ch06/                        ← 压缩、Dream、断点续传
│   ├── ch07/                        ← 验证闭环、Judge、LoopGuard、Planning
│   ├── ch08/                        ← 反馈闭环、失败挖掘、Red Team、Pareto
│   ├── ch09/                        ← Java 重构前后指标
│   ├── ch10/                        ← Hook 防御实验
│   ├── ch11/                        ← Solo vs Multi-Agent 对照
│   └── ch12/                        ← 三案例成本观测
│
└── tests/                           ← 框架自身的测试
    ├── test_tools.py
    ├── test_compressor.py
    ├── test_loop_guard.py
    └── test_e2e.py
```
