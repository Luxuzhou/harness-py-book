# Harness-py Book 代码架构

## 设计原则

1. **每章独立可运行**：standalone/chXX.py 单文件，无外部依赖（除requests），python一键运行
2. **渐进式构建**：harness_py/包逐章叠加，每章加一个模块，前面的模块不动
3. **实战层分离**：Ch8-10用生产级框架（harness_py_pro/），不依赖教学层
4. **实验可复现**：experiments/下的脚本可独立验证书中的每个实验数据

---

## 章节 → 代码映射

### Ch1 Agent的困境（入门）
```
standalone/ch01_experiment.py    ← 三个Agent对比实验的数据展示（不需要API）
  - 展示实验结果对比表
  - 故障链分析的代码级演示
  - 无需运行Agent，纯数据展示
```
**依赖**：无

### Ch2 Harness Engineering方法论（入门）
```
standalone/ch02_checklist.py     ← 六层检查清单的交互式工具
  - 输入一个项目目录
  - 自动扫描：有无CLAUDE.md？有无tests/？有无.env安全？
  - 输出六层架构的完成度评分
```
**依赖**：无（纯文件系统扫描）

### Ch3 Agent循环与约束层（构建）
```
standalone/ch03_agent_loop.py    ← 最小Agent循环 + 三轮安全实验
  - 30行最小循环（可接入DeepSeek跑）
  - 三层安全约束的代码
  - 三轮攻防实验的运行脚本
  ~约200行

harness_py/config.py             ← 全局配置 + UTF-8初始化
harness_py/http_client.py        ← HTTP客户端（requests + 重试）
harness_py/agent.py              ← 核心循环（此阶段只有循环+约束，无压缩/记忆）
```
**依赖**：requests, DeepSeek API key（standalone版也可mock运行）
**验证**：`python standalone/ch03_agent_loop.py` → 看到三轮实验结果

### Ch4 工具系统与MCP（构建）
```
standalone/ch04_tools.py         ← 6个工具从零实现 + MCP Server示例
  - read_file / write_file / edit_file / grep_search / glob_search / bash
  - 每个工具的独立测试
  - 一个最小MCP Server连接示例
  ~约350行

harness_py/tools.py              ← 工具注册表 + 6工具（线程bash + 编码修复）
```
**依赖**：无外部依赖（bash工具用subprocess）
**验证**：`python standalone/ch04_tools.py` → 每个工具跑一个测试用例

### Ch5 上下文工程与Prompt Cache（构建）
```
standalone/ch05_context.py       ← CLAUDE.md发现 + prompt组装 + 安全扫描演示
  - 扫描当前目录的CLAUDE.md文件
  - 演示Cache边界标记
  - 演示上下文文件安全扫描（注入10个威胁模式的检测）
  - 演示三层文档架构
  ~约150行

harness_py/prompt.py             ← Prompt组装 + 安全扫描 + Cache边界
```
**依赖**：无（纯文件系统操作）
**验证**：`python standalone/ch05_context.py` → 显示发现的文档和安全扫描结果

### Ch6 记忆管理与上下文压缩（构建）
```
standalone/ch06_memory.py        ← 四级压缩演示 + Token预算 + Memory系统 + Session持久化
  - Context Rot信噪比模拟
  - 四级压缩的逐级演示
  - Token预算五区分配
  - MEMORY.md + Dream整理
  - jsonl持久化演示
  ~约400行（内容最多的standalone）

harness_py/compressor.py         ← 四级压缩（迭代摘要 + 工具对修复）
harness_py/memory.py             ← Auto Memory + Dream
harness_py/session.py            ← jsonl持久化
harness_py/token_budget.py       ← Token预算
```
**依赖**：无（standalone版用模拟数据，不需要API）
**验证**：`python standalone/ch06_memory.py` → 显示压缩前后对比、预算报告

### Ch7 验证与对抗式评估（构建）
```
standalone/ch07_verify.py        ← LoopGuard演示 + 闭环验证 + 分阶段规划演示
  - LoopGuard的四种检测场景
  - 自验证循环的代码模式
  - 分阶段工具解锁的演示
  ~约150行

harness_py/loop_guard.py         ← 循环守卫
harness_py/agent.py              ← 更新：加入分阶段规划 + LoopGuard集成
```
**依赖**：无
**验证**：`python standalone/ch07_verify.py` → 显示LoopGuard介入的时机

### Ch8 实战一：企业 Java 系统重构（实战）
```
cases/refactor_enterprise/
├── target_project/              ← 真实规模 Spring Boot 项目（72 文件 / 7,929 行）
│   ├── src/main/java/com/example/cp/   ← Controller / Service / DAO / DTO 八层分工
│   └── ...
├── CLAUDE.md                    ← 项目规则（Hook 范围、命名纪律、事务纪律）
├── TASK.md                      ← God Class 拆分与 API 契约不变的十项验收
├── run.py                       ← 单 Agent 编排入口
└── verify.py                    ← 静态验收（服务数、契约、测试、编译）
```
**依赖**：harness_py_pro/（生产级框架）+ DeepSeek API key
**验证**：`python cases/refactor_enterprise/run.py` → Agent 执行重构 → `python cases/refactor_enterprise/verify.py` → 量化对比

### Ch9 实战二：医疗数据合规（实战）
```
cases/data_compliance/
├── target_service/              ← 按业务域拆分的 FastAPI 服务（~15,000 行）
│   ├── app/api/routes/          ← 7 个域路由（patients / lab_results / ...）
│   ├── app/repositories/        ← 6 个 Repository（患者 / 检验 / 仪器 / 异常 / 审计 / Base）
│   ├── app/services/            ← 规则引擎、调度、数据导出
│   ├── tests/                   ← 104 个单元测试
│   ├── sample_data/             ← 合成样本（patients/lab_results/instruments + reference_ranges.json）
│   └── generate_sample_data.py
├── CLAUDE.md                    ← 三层防御规则（SQL / PII / 审计 / 沙箱 / 网络）
├── TASK.md                      ← 六项合规验收
├── run.py                       ← 单 Agent + Hook 执行入口
└── verify.py                    ← 静态合规验收（SQL / PII / 审计 / 沙箱 / 网络 / 测试）
```
**依赖**：harness_py_pro/ + DeepSeek API key
**验证**：`python cases/data_compliance/run.py` → 分析执行 → `python cases/data_compliance/verify.py` → 合规率报告

### Ch10 实战三：跨项目多 Agent 编排（实战）
```
cases/multiagent_enterprise/
├── spec/                        ← requirement.md / api_contract.yaml / architecture.md
├── roles/                       ← architect / java_developer / python_developer / qa_engineer
├── CLAUDE.md                    ← 多 Agent 编排配置 + 契约治理规则
├── TASK.md                      ← 四轮编排定义 + 角色隔离约束
├── run.py                       ← 四角色编排入口（cwd 指向 Ch8/Ch9 真实代码）
└── verify.py                    ← 跨项目一致性验证（anchors / 骨架 / 契约 / 产物）
```
**本案例不自建业务代码**：JavaDeveloper 与 PythonDeveloper 的 `cwd` 由 Harness 分别锁定到 Ch8 的 `refactor_enterprise/target_project/` 与 Ch9 的 `data_compliance/target_service/`。

**依赖**：harness_py_pro/ + DeepSeek API key（还要求 Ch8/Ch9 两个锚点目录存在）
**验证**：`python cases/multiagent_enterprise/run.py` → 四 Agent 编排 → `python cases/multiagent_enterprise/verify.py`

### Ch11 观测、成本与生产部署（进阶）
```
standalone/ch11_observe.py       ← Token消耗追踪 + 成本建模 + 预算报告
  - 读取jsonl session文件，分析token消耗
  - 按工具类型的消耗分布图
  - 月度成本预测
  ~约100行
```
**依赖**：一个已有的jsonl session文件
**验证**：`python standalone/ch11_observe.py .harness_sessions/xxx.jsonl`

### Ch12 Harness的未来（进阶）
```
无代码。纯文字章节。
引用Hermes Agent的自改进Skills作为未来方向。
```

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

| 章节 | standalone可运行 | 需要API | 需要前置章节 | 验证命令 |
|------|----------------|---------|------------|---------|
| Ch1 | ✅ | ❌ | ❌ | `python standalone/ch01_experiment.py` |
| Ch2 | ✅ | ❌ | ❌ | `python standalone/ch02_checklist.py` |
| Ch3 | ✅ | ✅可选 | ❌ | `python standalone/ch03_agent_loop.py` |
| Ch4 | ✅ | ❌ | ❌ | `python standalone/ch04_tools.py` |
| Ch5 | ✅ | ❌ | ❌ | `python standalone/ch05_context.py` |
| Ch6 | ✅ | ❌ | ❌ | `python standalone/ch06_memory.py` |
| Ch7 | ✅ | ❌ | ❌ | `python standalone/ch07_verify.py` |
| Ch8 | ❌ | ✅ | harness_py_pro | `python cases/refactor_enterprise/run.py` |
| Ch9 | ❌ | ✅ | harness_py_pro | `python cases/data_compliance/run.py` |
| Ch10 | ❌ | ✅ | harness_py_pro | `python cases/multiagent_enterprise/run.py` |
| Ch11 | ✅ | ❌ | 一个jsonl文件 | `python standalone/ch11_observe.py` |
| Ch12 | N/A | N/A | N/A | 无代码 |

---

## 目录总览

```
harness-py-book/
├── README.md
├── .env.example                     ← API key配置模板
│
├── examples/                        ← 每章薄脚本（调harness_py模块，非自包含重复）
│   ├── ch01_experiment.py           ← 三Agent实验数据展示（纯数据，无依赖）
│   ├── ch02_checklist.py            ← 六层检查清单（纯文件扫描）
│   ├── ch03_agent_loop.py           ← 安全实验 → harness_py.tools._check_path_escape
│   ├── ch04_tools.py                ← 6工具验证 → harness_py.tools.*
│   ├── ch04_mcp_server.py           ← MCP Server（独立协议，自包含）
│   ├── ch05_context.py              ← 上下文发现 → harness_py.prompt.*
│   ├── ch06_memory.py               ← 压缩+Memory → harness_py.compressor/memory/session
│   ├── ch07_verify.py               ← LoopGuard → harness_py.loop_guard.*
│   └── ch11_observe.py              ← Token分析（纯jsonl解析）
│
├── standalone/                      ← [保留] 原始自包含版本（历史参考）
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
├── harness_py_pro/                  ← 生产级框架（~3,500行，15模块，Ch8-10用）
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
├── cases/                           ← 三个实战项目（26文件）
│   ├── refactor/                    ← Ch8: 遗留系统重构
│   │   ├── TASK.md                  ← 四阶段重构任务
│   │   ├── CLAUDE.md                ← 重构约束规则
│   │   ├── run.py / verify.py       ← 运行+验证脚本
│   │   └── target_project/          ← ~900行待重构代码（God Class+SQL注入+硬编码）
│   ├── medical/                     ← Ch9: 医疗数据分析
│   │   ├── TASK.md                  ← 数据分析任务+合规要求
│   │   ├── CLAUDE.md                ← 医疗合规配置
│   │   ├── compliance_hooks.py      ← 合规Hook（PII过滤+审计+网络隔离）
│   │   ├── run.py / verify.py       ← 运行+合规验证
│   │   └── sample_data/             ← 150条脱敏血常规数据
│   └── fullstack/                   ← Ch10: 多Agent全栈开发
│       ├── TASK.md                  ← 三角色协作任务
│       ├── CLAUDE.md                ← 编排规则
│       ├── spec.md                  ← 一句话需求
│       ├── roles/                   ← Planner/Generator/Evaluator角色定义
│       ├── run.py / verify.py       ← 运行+功能验证
│       └── output/                  ← Agent生成的代码（运行后产生）
│
├── experiments/                     ← 实验脚本
│   ├── compression_demo.py          ← Ch6: DeepSeek 128K压缩实验
│   ├── cost_tracker_task.py         ← Ch7: CostTracker集成任务
│   └── planning_vs_no_planning.py   ← Ch7: 有无规划阶段的对比实验
│
└── tests/                           ← 框架自身的测试
    ├── test_tools.py
    ├── test_compressor.py
    ├── test_loop_guard.py
    └── test_e2e.py
```
