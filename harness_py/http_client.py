"""
HTTP客户端：requests + 自动重试 + 去相关jitter
==============================================
对齐Claude Code的重试策略，融入Hermes的去相关jitter。
Ch3代码线的基础设施层。
"""
from __future__ import annotations

import time
import threading
from typing import Any

import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ModelConfig

RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

# Hermes风格去相关jitter
_jitter_lock = threading.Lock()
_jitter_counter = 0


def jittered_backoff(attempt: int, base: float = 0.5, max_delay: float = 10.0, jitter_ratio: float = 0.5) -> float:
    """指数退避 + 去相关jitter。防止并发重试的雷群效应。"""
    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        tick = _jitter_counter
    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    delay = min(base * (2 ** (attempt - 1)), max_delay)
    jitter = rng.uniform(0, jitter_ratio * delay)
    return delay + jitter


class LLMClient:
    """OpenAI兼容API客户端。内置连接池、自动重试、编码容错。"""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._session = self._create_session()

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """非流式调用。返回assistant消息dict。"""
        payload: dict[str, Any] = {
            'model': self.config.model,
            'messages': messages,
            'temperature': self.config.temperature,
        }
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'

        url = f'{self.config.base_url.rstrip("/")}/chat/completions'

        # 带session重建的重试（解决Windows长连接socket问题）
        for attempt in range(3):
            try:
                resp = self._session.post(url, json=payload, timeout=self.config.timeout_seconds)
                break
            except (OSError, requests.ConnectionError) as exc:
                if attempt < 2:
                    print(f'  [HTTP] 连接错误，重建Session后重试（{attempt + 1}/3）')
                    self._rebuild_session()
                    time.sleep(jittered_backoff(attempt + 1))
                    continue
                raise RuntimeError(f'API连接失败: {exc}') from exc

        if resp.status_code != 200:
            raise RuntimeError(f'API错误 HTTP {resp.status_code}: {resp.text[:300]}')

        data = resp.json()
        choices = data.get('choices', [])
        if not choices:
            raise RuntimeError('API返回空choices')

        message = choices[0].get('message', {})
        usage = data.get('usage', {})
        # 在usage中添加模型信息，便于成本跟踪
        usage['model'] = self.config.model
        message['usage'] = usage
        message['stop_reason'] = choices[0].get('finish_reason', '')
        return message

    def _create_session(self) -> requests.Session:
        """创建带重试配置的HTTP Session。唯一的Session工厂方法。"""
        retry = Retry(
            total=5,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=list(RETRYABLE_STATUS),
            allowed_methods=['POST'],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
        session = requests.Session()
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        session.headers.update({
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
        })
        return session

    def _rebuild_session(self) -> None:
        """重建HTTP Session。解决Windows socket损坏问题。"""
        try:
            self._session.close()
        except Exception:
            pass
        self._session = self._create_session()
