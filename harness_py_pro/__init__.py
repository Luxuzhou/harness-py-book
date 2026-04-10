"""
harness_py_pro — 生产级Harness框架
===================================
基于OpenHarness架构 + Hermes Agent模式 + harness_py的实战改进。
用于书中Ch8-10三个实战项目。

架构层次：
  config → client/provider → tools → hooks → permissions → engine
                                                             ↓
                              compact ← prompt ← loop_guard ← token_budget
                                                             ↓
                                  observe ← memory ←       swarm (多Agent)

模块清单（14个）：
  config.py          — 三层配置（Model/Agent/Hook）
  client.py          — HTTP客户端 + 抖动重试
  provider.py        — 多Provider路由 + 断路器降级
  tools.py           — BaseTool抽象 + ToolRegistry + 6工具
  hooks.py           — Pre/Post Hook框架
  permissions.py     — 路径+工具权限检查器
  engine.py          — 核心循环（并行工具+Hook+权限+压缩+成本+指标）
  compact.py         — 四级压缩 + 迭代摘要 + 孤儿修复
  prompt.py          — CLAUDE.md发现 + 安全扫描 + 角色注入
  loop_guard.py      — 循环守卫（4种检测）
  token_budget.py    — Token精确估算 + 五区预算 + CostTracker
  observe.py         — 结构化Logger + Metrics + SessionAnalyzer
  memory.py          — Memory CRUD + Dream整理
  sandbox.py         — 沙箱隔离（权限模式+网络+文件系统+危险命令）
  session.py         — jsonl会话持久化
  swarm.py           — 多Agent编排（orchestrate + pipeline）
"""

__version__ = '0.2.0'

from .config import ModelConfig, AgentConfig, HookConfig
from .engine import run, resume, RunResult
from .provider import ProviderProfile, ProviderRouter
from .swarm import orchestrate, run_pipeline, SwarmResult

__all__ = [
    'run',
    'resume',
    'RunResult',
    'ModelConfig',
    'AgentConfig',
    'HookConfig',
    'ProviderProfile',
    'ProviderRouter',
    'orchestrate',
    'run_pipeline',
    'SwarmResult',
]
