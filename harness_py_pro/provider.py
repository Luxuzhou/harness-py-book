"""
Provider路由与降级
==================
对标Hermes的auxiliary_client + OpenHarness的api/registry。
生产环境中，单一Provider不可靠，需要降级链。

设计：
  PrimaryProvider → FallbackProvider1 → FallbackProvider2
  每个Provider有独立的api_key/base_url/model配置。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import ModelConfig
from .client import LLMClient


@dataclass
class ProviderProfile:
    """
    Provider配置档案。

    一个Provider对应一个LLM API端点（可以是同一公司的不同模型）。
    """
    name: str
    model: str
    api_key: str
    base_url: str
    context_window: int = 128_000
    max_output_tokens: int = 16_384
    temperature: float = 0.0
    priority: int = 0  # 越小优先级越高

    # 运行时状态
    _consecutive_failures: int = 0
    _last_failure_time: float = 0.0
    _circuit_open: bool = False

    def to_model_config(self) -> ModelConfig:
        return ModelConfig(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            context_window=self.context_window,
            max_output_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )


@dataclass
class ProviderRouter:
    """
    Provider路由器。

    功能：
    1. 按优先级排序Provider
    2. 失败时自动降级到下一个
    3. 断路器：连续失败3次后暂时跳过该Provider（60秒冷却）
    4. 自动恢复：冷却期后尝试恢复
    """
    providers: list[ProviderProfile] = field(default_factory=list)
    _clients: dict[str, LLMClient] = field(default_factory=dict)

    # 断路器配置
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: float = 60.0

    def add_provider(self, profile: ProviderProfile):
        """添加Provider。"""
        self.providers.append(profile)
        self.providers.sort(key=lambda p: p.priority)

    def add_from_env(self):
        """从环境变量自动发现Provider。"""
        import os

        # DeepSeek
        ds_key = os.getenv('DEEPSEEK_API_KEY', os.getenv('OPENAI_API_KEY', ''))
        ds_base = os.getenv('DEEPSEEK_BASE_URL', os.getenv('OPENAI_BASE_URL', ''))
        if ds_key and 'deepseek' in ds_base.lower():
            self.add_provider(ProviderProfile(
                name='deepseek',
                model=os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
                api_key=ds_key,
                base_url=ds_base,
                priority=0,
            ))

        # OpenAI
        oai_key = os.getenv('OPENAI_API_KEY', '')
        oai_base = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        if oai_key and 'openai' in oai_base.lower():
            self.add_provider(ProviderProfile(
                name='openai',
                model=os.getenv('OPENAI_MODEL', 'gpt-4o'),
                api_key=oai_key,
                base_url=oai_base,
                priority=10,
            ))

        # Anthropic (via OpenAI兼容端点)
        ant_key = os.getenv('ANTHROPIC_API_KEY', '')
        ant_base = os.getenv('ANTHROPIC_BASE_URL', '')
        if ant_key and ant_base:
            self.add_provider(ProviderProfile(
                name='anthropic',
                model=os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-6'),
                api_key=ant_key,
                base_url=ant_base,
                priority=20,
            ))

        # 通用HARNESS_配置（最高优先级）
        h_key = os.getenv('HARNESS_API_KEY', '')
        h_base = os.getenv('HARNESS_BASE_URL', '')
        if h_key and h_base:
            self.add_provider(ProviderProfile(
                name='harness-primary',
                model=os.getenv('HARNESS_MODEL', 'deepseek-chat'),
                api_key=h_key,
                base_url=h_base,
                priority=-10,  # 最高优先级
            ))

    def get_client(self, provider: ProviderProfile) -> LLMClient:
        """获取或创建Provider对应的Client。"""
        if provider.name not in self._clients:
            self._clients[provider.name] = LLMClient(provider.to_model_config())
        return self._clients[provider.name]

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> tuple[dict, str]:
        """
        带降级的完成请求。

        返回 (response, provider_name)。
        如果所有Provider都失败，抛出RuntimeError。
        """
        errors = []

        for provider in self._available_providers():
            client = self.get_client(provider)

            try:
                response = client.complete(messages, tools, **kwargs)
                # 成功，重置断路器
                provider._consecutive_failures = 0
                provider._circuit_open = False
                return response, provider.name

            except RuntimeError as e:
                error_msg = str(e)
                errors.append(f'{provider.name}: {error_msg[:100]}')
                provider._consecutive_failures += 1
                provider._last_failure_time = time.time()

                # 断路器逻辑
                if provider._consecutive_failures >= self.circuit_failure_threshold:
                    provider._circuit_open = True
                    print(f'  [ROUTER] {provider.name} 断路器打开（连续失败 {provider._consecutive_failures} 次）')

                print(f'  [ROUTER] {provider.name} 失败，降级到下一个Provider...')
                continue

        raise RuntimeError(
            f'所有Provider均失败 ({len(errors)}):\n' +
            '\n'.join(f'  - {e}' for e in errors)
        )

    def _available_providers(self) -> list[ProviderProfile]:
        """获取可用的Provider列表（排除断路器打开的）。"""
        now = time.time()
        available = []

        for p in self.providers:
            if p._circuit_open:
                # 检查冷却期是否已过
                if now - p._last_failure_time > self.circuit_cooldown_seconds:
                    p._circuit_open = False
                    p._consecutive_failures = 0
                    print(f'  [ROUTER] {p.name} 断路器恢复（冷却期已过）')
                    available.append(p)
                # 冷却期内跳过
            else:
                available.append(p)

        # 如果全部断路，强制使用第一个（总得试试）
        if not available and self.providers:
            available = [self.providers[0]]

        return available

    @property
    def active_provider(self) -> str | None:
        """当前活跃的Provider名称。"""
        available = self._available_providers()
        return available[0].name if available else None

    def status(self) -> list[dict]:
        """所有Provider的状态。"""
        return [{
            'name': p.name,
            'model': p.model,
            'priority': p.priority,
            'circuit_open': p._circuit_open,
            'consecutive_failures': p._consecutive_failures,
        } for p in self.providers]
