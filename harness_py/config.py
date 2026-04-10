"""全局配置。纯数据声明，无副作用。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelConfig:
    """模型配置。"""
    model: str = 'deepseek-chat'
    base_url: str = 'https://api.deepseek.com/v1'
    api_key: str = ''
    temperature: float = 0.0
    timeout_seconds: float = 120.0
    context_window: int = 128_000

    @classmethod
    def from_env(cls) -> ModelConfig:
        return cls(
            model=os.environ.get('HARNESS_MODEL', os.environ.get('OPENAI_MODEL', 'deepseek-chat')),
            base_url=os.environ.get('HARNESS_BASE_URL', os.environ.get('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')),
            api_key=os.environ.get('HARNESS_API_KEY', os.environ.get('OPENAI_API_KEY', '')),
        )


@dataclass
class AgentConfig:
    """Agent运行配置。"""
    cwd: Path = field(default_factory=lambda: Path.cwd())
    max_iterations: int = 200
    max_cost_usd: float = 2.0
    max_output_chars: int = 30_000
    command_timeout: float = 30.0
    compact_preserve_messages: int = 4
    compress_threshold_pct: float = 0.80

    # 权限
    allow_write: bool = True
    allow_shell: bool = True
    allow_destructive: bool = False

    # 分阶段执行
    planning_turns: int = 3
    planning_tools: tuple = ('read_file', 'grep_search', 'glob_search')
