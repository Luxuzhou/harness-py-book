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

模块清单（26个）：
  Tier 1 — 核心层（16个）：
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

  Tier 2 — 扩展层·第一批（5个）：
  checkpoint.py      — 文件检查点与回滚（对标Claude Code的rewind）
  git_ops.py         — Git操作封装 + Worktree管理
  mcp_client.py      — MCP客户端（stdio传输 + JSON-RPC 2.0）
  skills.py          — Skill注册与发现（Markdown定义 + YAML frontmatter）
  plugins.py         — 插件系统（skills/hooks/MCP/工具打包）

  Tier 2 — 扩展层·第二批（5个）：
  tasks.py           — 后台任务管理器（spawn/track/kill子进程）
  mailbox.py         — Agent间消息队列（基于文件的异步消息传递）
  lsp.py             — 代码智能（基于AST的符号查找/引用搜索/大纲）
  cron.py            — 定时任务调度（间隔调度+持久化）
  hot_reload.py      — 配置热重载（mtime监控+回调）
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
