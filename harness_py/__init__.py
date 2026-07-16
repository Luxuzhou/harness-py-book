"""
Harness-py: 用Python从零构建生产级Agent Harness
================================================
《HarnessEngineering实战：构建可靠的生产级AIAgent》配套框架

六层架构：约束 → 工具 → 上下文 → 记忆 → 验证 → 编排
技术路线：OpenAI兼容协议 + 国产大模型（DeepSeek/Qwen）

参考实现：Claude Code架构 + Hermes Agent最佳实践
"""

__version__ = '0.1.0'

from .agent import run, resume, RunResult
from .config import ModelConfig, AgentConfig

__all__ = [
    'run',
    'resume',
    'RunResult',
    'ModelConfig',
    'AgentConfig',
]
