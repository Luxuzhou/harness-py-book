# Harness-py Book

> **《驾驭AI：Harness Engineering实战》** 配套代码仓库
>
> 用国产大模型从零构建生产级Agent系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-39%20passed-green.svg)](#运行测试)
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
│                        第8-10章实战使用，含沙箱/Hook/多Agent编排
│
├── examples/            每章验证脚本（9个）
│                        调用harness_py模块，一行命令验证章节概念
│
├── cases/               三个企业级实战项目
│   ├── refactor_enterprise/  第8章：7,929行Java Spring Boot临床路径系统
│   ├── data_compliance/     第9章：6,759行Python诊疗数据服务 + 10K条数据
│   └── multiagent_enterprise/ 第10章：跨Java+Python的四Agent协作
│
├── tests/               单元测试（39个，全通过）
├── experiments/          实验脚本
└── figures/             书中配图（300dpi PNG）
```

## 快速开始

```bash
# 克隆
git clone https://github.com/lexzhou/harness-py-book.git
cd harness-py-book

# 环境
python -m venv .venv && .venv\Scripts\activate  # Windows
# source .venv/bin/activate                     # macOS/Linux
pip install -r requirements.txt

# 配置API（复制后填入你的DeepSeek API Key）
cp .env.example .env

# 验证
python -m pytest tests/ -v
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
| ⑥ 编排层 | 第10章 | `swarm.py` | 多Agent编排、角色隔离、收敛控制 |

## 章节导航

| 章节 | 验证命令 | 需要API |
|------|---------|--------|
| 第1章 Agent的困境 | `python examples/ch01_experiment.py` | 否 |
| 第2章 方法论 | `python examples/ch02_checklist.py .` | 否 |
| 第3章 约束层 | `python examples/ch03_agent_loop.py` | 部分 |
| 第4章 工具层 | `python examples/ch04_tools.py` | 否 |
| 第5章 上下文层 | `python examples/ch05_context.py` | 否 |
| 第6章 记忆层 | `python examples/ch06_memory.py` | 否 |
| 第7章 验证层 | `python examples/ch07_verify.py` | 否 |
| 第8章 Java重构 | `python cases/refactor_enterprise/run.py` | 是 |
| 第9章 数据合规 | `python cases/data_compliance/run.py` | 是 |
| 第10章 多Agent | `python cases/multiagent_enterprise/run.py` | 是 |
| 第11章 观测部署 | `python examples/ch11_observe.py` | 否 |

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
# 全量测试（不需要API Key）
python -m pytest tests/ -v

# 预期结果：39 passed
```

## 实战项目

### 第8章：企业级Java系统重构

7,929行Java Spring Boot临床路径管理系统，包含God Service（1,266行）、SQL注入、混合注入风格等10个代码坏味道。Agent任务：理解架构→补测试→逐步重构。

### 第9章：医疗数据服务合规加固

6,759行Python FastAPI数据处理服务 + 10,833条合成医疗数据。包含PII泄露、SQL拼接、无审计日志等10个合规漏洞。三层防御（沙箱+Hook+CLAUDE.md）实战。

### 第10章：跨语言多Agent系统集成

给Java临床路径系统 + Python诊疗分析服务新增路径变异智能预警模块。四Agent角色（Architect/Java Dev/Python Dev/QA）并行开发，接口契约治理，收敛验证。

## 技术选型

- **语言**：Python 3.10+（教学层纯标准库+requests）
- **模型协议**：OpenAI兼容API
- **推荐模型**：DeepSeek-V3（128K窗口，成本约$0.27/MTok）
- **无重型依赖**：不需要LangChain/LlamaIndex/AutoGen

## 作者

陆徐洲（Lex），LIMS领域AI算法负责人。医疗信息化背景，控制工程研究生。

## 许可证

代码以MIT许可证开源。书稿内容版权归作者和电子工业出版社所有。
