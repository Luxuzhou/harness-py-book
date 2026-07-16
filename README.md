# 《HarnessEngineering实战：构建可靠的生产级AIAgent》配套代码

> **《HarnessEngineering实战：构建可靠的生产级AIAgent》** 配套代码仓库
>
> 用国产大模型从零构建生产级Agent系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-89%20root%20%2B%20137%20case-green.svg)](#运行测试)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## 这本书讲什么

AI模型越来越强，但Agent系统的可靠性没有同步提升。模型能写出正确的代码，却在多轮任务中丢失目标、上下文溢出、陷入死循环。

**Harness Engineering** 解决的就是这个问题：不换模型，通过改进模型外面的"脚手架"（约束、工具、上下文、记忆、验证、编排），让Agent从"能跑"变成"靠谱"。

本书用一个从零构建的Python Harness框架（harness_py），配合DeepSeek等国产模型，完整演示六层架构的设计与实现。三个企业级实战案例（Java系统重构、医疗数据合规、跨语言多Agent协作）展示Harness在真实工程中的落地。

## 仓库概览

```
harness-py-book/
│
├── harness_py/          教学层框架（11模块，~1,400行）
│                        第3-7章逐章构建，六层架构完整实现
│
├── harness_py_pro/      生产层框架（15模块，~3,700行）
│                        第8章以后使用，含反馈调节、沙箱/Hook、多Agent编排和观测
│
├── examples/            第3章以后每章验证脚本
│                        调用harness_py模块，一行命令验证章节概念
│
├── cases/               三个企业级实战项目（每个含 TASK/CLAUDE/run/verify 壳层）
│   ├── refactor_enterprise/  第9章：92个生产源文件、约10,127行Java Spring Boot临床路径系统
│   ├── data_compliance/     第10章：~15,000行Python合规服务 + 10K条合成数据
│   └── multiagent_enterprise/ 第11章：跨第9章+第10章真实代码的四Agent协作
│
├── tests/               根测试套件（89 passed）
├── cases/data_compliance/target_service/tests/  第10章案例自带测试
├── experiments/          实验脚本
├── figures/             书中配图（300dpi PNG）
└── docs/                章节索引、环境准备与常见问题
```

## 阅读与复现指南

- [章节与代码索引](docs/CHAPTER_INDEX.md)：快速定位第 1—12 章对应的模块、示例和验收入口。
- [环境准备与实验命令](docs/ENVIRONMENT.md)：安装 Python/Java 环境，运行示例、测试和实战验收。
- [常见问题与排错](docs/TROUBLESHOOTING.md)：处理依赖、API、编码、测试和实战基线问题。
- [代码架构](CODE_ARCHITECTURE.md)：面向维护者的模块关系和实现说明。

第 9—11 章的 `run.py` 会让 Agent 修改 `cases/` 中的目标代码。复现实战前请先确认 Git 工作区干净，或在单独分支/副本中运行。

## 快速开始

```bash
# 克隆
git clone https://github.com/Luxuzhou/harness-py-book.git
cd harness-py-book

# 环境
python -m venv .venv && .venv\Scripts\activate  # Windows
# source .venv/bin/activate                     # macOS/Linux

# 1) 根依赖（教学层 + examples/，足够跑 tests/ 与 Ch3-8、Ch12 的 examples）
pip install -r requirements.txt

# 2) 第 10 章案例依赖（FastAPI 服务案例测试需要）
pip install -r cases/data_compliance/target_service/requirements.txt

# 配置API（复制后填入你的 DeepSeek API Key）
cp .env.example .env

# 验证
python -m pytest tests/ -v                                          # 根测试
cd cases/data_compliance/target_service && python -m pytest tests/ -v  # 第10章案例测试
```

## 六层架构

本书的核心框架——每一层对应一到两章内容：

| 层 | 章节 | 代码模块 | 职责 |
|----|------|---------|------|
| ① 约束层 | 第3章 | `config.py` `sandbox.py` | 权限控制、沙箱隔离、预算熔断 |
| ② 工具层 | 第4章 | `tools.py` | 6个工具 + MCP协议 + 路径安全 |
| ③ 上下文层 | 第5章 | `prompt.py` | CLAUDE.md发现、Prompt Cache、安全扫描 |
| ④ 记忆层 | 第6章 | `compressor.py` `memory.py` `session.py` | 四级压缩、长期记忆、断点续传 |
| ⑤ 验证层 | 第7章 | `loop_guard.py` | LoopGuard、对抗评估、规划阶段 |
| ⑥ 编排层 | 第11章 | `swarm.py` | 多Agent编排、角色隔离、收敛控制 |

## 章节导航

| 章节 | 验证命令 | 需要API |
|------|---------|--------|
| 第1章 Agent的困境 | 无需运行代码，配套案例记录与图表 | 否 |
| 第2章 方法论 | 无需运行代码，作为六层架构和评估清单导入 | 否 |
| 第3章 约束层 | `python examples/ch03_safety_demo.py` | 否 |
| 第4章 工具层 | `python examples/ch04_tools.py` | 否 |
| 第5章 上下文层 | `python examples/ch05_context.py` | 否 |
| 第6章 记忆层 | `python examples/ch06_memory.py` | 否 |
| 第7章 验证层 | `python examples/ch07_verify.py` | 否 |
| 第8章 反馈调节 | `python examples/ch08_feedback.py` | 否 |
| 第9章 Java重构 | `python cases/refactor_enterprise/run.py` | 是 |
| 第10章 数据合规 | `python cases/data_compliance/run.py` | 是 |
| 第11章 多Agent | `python cases/multiagent_enterprise/run.py` | 是 |
| 第12章 观测部署 | `python examples/ch12_observe.py` | 否 |


## 读者入口说明

读者使用本仓库时以本文档为准。`CODE_ARCHITECTURE.md` 是作者维护章节与代码映射的内部备忘，不作为正式阅读路径；若它与书稿或本 README 不一致，以书稿和本 README 为准。

第1章用于定义问题和分析一次 Harness 故障诊断案例，不提供可运行示例脚本。配套材料是正文中的案例记录、表格和 `figures/` 下的图表；从第3章开始，读者再按章节运行 `examples/` 中的最小验证脚本。
## API配置

支持所有OpenAI兼容协议的模型。在`.env`中配置：

```bash
# DeepSeek（推荐）
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-你的key
OPENAI_MODEL=deepseek-chat
```

也支持通义千问、Kimi、GLM等国产模型，详见`.env.example`。

## 运行测试

```bash
# 根测试套件（不需要API Key；教学层 + harness_py_pro 框架测试）
python -m pytest tests/ -v
# 预期结果：89 passed

# 第 10 章案例测试（合规服务自带，依赖 fastapi / httpx / openpyxl，见 cases/data_compliance/target_service/requirements.txt）
pip install -r cases/data_compliance/target_service/requirements.txt
cd cases/data_compliance/target_service && python -m pytest tests/ -q
# 预期结果：137 passed（从服务目录运行，避免仓库根 .env 干扰案例配置）
```

## 实战项目

### 第9章：企业级Java系统重构

92个生产源文件、约10,127行的Java Spring Boot临床路径管理系统，包含God Service（1,266行）等典型遗留系统坏味道。Agent任务：理解架构→保持对外契约→逐步拆分职责。

### 第10章：医疗数据服务合规加固

按业务域拆分为路由 / 服务 / Repository / 异常规则引擎 / 调度任务 / 数据导出六大层的 FastAPI 临床数据合规服务（约 15,000 行），配套 10,050 条合成数据（patients / lab_results / instruments）。包含 PII 泄露、SQL 拼接、无审计日志等合规漏洞。三层防御（沙箱 + Hook + CLAUDE.md）实战。**服务自带单元测试覆盖 Repository / 服务 / 路由 / 规则引擎 / 调度 / 导出。**

### 第11章：跨语言多Agent系统集成

本案例**不自建业务代码**：`multiagent_enterprise/run.py` 把 JavaDeveloper 的 cwd 指向第9章的 `refactor_enterprise/target_project/`、PythonDeveloper 的 cwd 指向第10章的 `data_compliance/target_service/`，由 Harness 编排四角色（Architect/JavaDev/PythonDev/QA）在真实业务代码上并行开发。接口契约治理、`parallel_groups` 语义、收敛验证一次性展示。

## 技术选型

- **语言**：Python 3.10+（教学层纯标准库+requests）
- **模型协议**：OpenAI兼容API
- **模型选择**：DeepSeek 等提供 OpenAI 兼容接口的模型
- **无重型依赖**：不需要LangChain/LlamaIndex/AutoGen

## 作者

陆徐洲（Lex），LIMS领域AI算法负责人。医疗信息化背景，控制工程研究生。

## 许可证

仓库代码以 [MIT License](LICENSE) 开源。书稿正文及出版内容版权归作者和电子工业出版社所有；仓库中的合成医疗数据仅用于教学与测试，不代表真实患者信息。

欢迎通过 Issue 反馈代码问题；提交修改前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 中的方式报告。
