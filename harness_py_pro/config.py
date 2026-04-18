"""
配置系统
========
三层配置：ModelConfig（LLM连接）、AgentConfig（Agent行为）、HookConfig（钩子配置）。
对标OpenHarness的Settings + 我们的AgentConfig融合。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


def ensure_utf8_console():
    """确保Windows控制台使用UTF-8编码。对标Claude Code的from_utf8_lossy。"""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


@dataclass
class ModelConfig:
    """LLM模型配置。"""
    model: str = ''
    api_key: str = ''
    base_url: str = ''
    context_window: int = 128_000
    max_output_tokens: int = 8_192
    temperature: float = 0.0

    # 复现性：seed 不为 None 时把它通过 `seed` 字段传给支持的模型
    # （DeepSeek、OpenAI gpt-4o 等都支持），同样的 prompt+seed 会得到
    # 接近一致的输出。temperature=0 仍然有浮点精度的随机性，加 seed
    # 能让"教学示例的输出可复现"这件事更靠谱。
    seed: Optional[int] = None

    # HTTP 连接池大小：默认 1（串行 Agent 工作流）；如果上层做并行
    # 工具调用或多 Agent 并发，需要把 pool_size 调大避免连接复用瓶颈。
    pool_size: int = 1

    @classmethod
    def from_env(cls) -> ModelConfig:
        seed_env = os.getenv('HARNESS_SEED', '')
        return cls(
            model=os.getenv('HARNESS_MODEL', os.getenv('MODEL', 'deepseek-chat')),
            api_key=os.getenv('HARNESS_API_KEY', os.getenv('OPENAI_API_KEY', '')),
            base_url=os.getenv('HARNESS_BASE_URL', os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')),
            context_window=int(os.getenv('HARNESS_CONTEXT_WINDOW', '128000')),
            max_output_tokens=int(os.getenv('HARNESS_MAX_OUTPUT', '8192')),
            seed=int(seed_env) if seed_env.strip() else None,
            pool_size=int(os.getenv('HARNESS_POOL_SIZE', '1')),
        )


@dataclass
class HookConfig:
    """
    钩子配置。
    pre_tool: 工具执行前调用，返回 (allow, reason)
    post_tool: 工具执行后调用，返回 (filtered_result, warnings)
    """
    pre_tool: Callable | None = None
    post_tool: Callable | None = None


@dataclass
class AgentConfig:
    """Agent行为配置。"""
    cwd: Path = field(default_factory=Path.cwd)
    max_iterations: int = 40
    planning_turns: int = 3
    max_cost_usd: float = 0.0
    allow_write: bool = True
    allow_shell: bool = True

    # 生产定制扩展点：用户可传入自定义 CostTracker 实例（比如对接
    # Prometheus / Grafana / 自家计费系统），传入则替换 engine 内部的默认
    # CostTracker。Optional[Any] 是为了避免 config.py 与 token_budget.py
    # 的循环依赖——engine 接收任意 duck-typed 对象，只要支持
    # record(model, input_tokens, output_tokens) / total_cost /
    # over_budget / summary() 四个方法即可。
    cost_tracker: Optional[Any] = None

    # 压缩配置
    compress_threshold_pct: float = 0.7
    compact_preserve_messages: int = 4

    # 权限配置
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)

    # 钩子
    hooks: HookConfig = field(default_factory=HookConfig)

    # 沙箱配置
    sandbox_mode: str = 'ask'  # ask / accept / bypass / plan
    network_isolated: bool = False
    filesystem_roots: list[str] = field(default_factory=list)
    command_runner: Callable[[str, int], tuple[bool, str]] | None = None

    # Agent角色（用于多Agent场景）
    role: str = ''
    role_prompt: str = ''
    tool_filter: list[str] = field(default_factory=list)
