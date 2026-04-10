"""
HTTP客户端
==========
多Provider支持（OpenAI兼容格式）。
对标OpenHarness的api/openai_client + Hermes的auxiliary_client。
增加：去相关抖动重试、会话重建。
"""

from __future__ import annotations
import random
import time
from typing import Any

import requests

from .config import ModelConfig


class LLMClient:
    """LLM HTTP客户端，支持OpenAI兼容格式。"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self._session = self._build_session()
        self._retry_count = 0

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
        })
        return s

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        发送完成请求。

        返回格式统一为：
        {
            'content': str,
            'tool_calls': [{'id': str, 'function': {'name': str, 'arguments': str}}],
            'usage': {'prompt_tokens': int, 'completion_tokens': int},
            'finish_reason': str,
        }
        """
        url = f'{self.config.base_url.rstrip("/")}/chat/completions'

        payload: dict[str, Any] = {
            'model': self.config.model,
            'messages': self._clean_messages(messages),
            'temperature': temperature if temperature is not None else self.config.temperature,
            'max_tokens': max_tokens or self.config.max_output_tokens,
        }

        if tools:
            payload['tools'] = [{'type': 'function', 'function': t} for t in tools]

        return self._request_with_retry(url, payload)

    def _request_with_retry(self, url: str, payload: dict, max_retries: int = 3) -> dict:
        """带去相关抖动的重试。"""
        for attempt in range(max_retries + 1):
            try:
                resp = self._session.post(url, json=payload, timeout=300)

                if resp.status_code == 429:
                    wait = self._jittered_backoff(attempt)
                    print(f'  [CLIENT] 429 rate limit, 等待 {wait:.1f}s...')
                    time.sleep(wait)
                    continue

                if resp.status_code >= 500:
                    wait = self._jittered_backoff(attempt)
                    print(f'  [CLIENT] {resp.status_code} server error, 重试 {attempt+1}/{max_retries}...')
                    time.sleep(wait)
                    self._session = self._build_session()
                    continue

                if resp.status_code != 200:
                    raise RuntimeError(f'API {resp.status_code}: {resp.text[:500]}')

                return self._parse_response(resp.json())

            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    wait = self._jittered_backoff(attempt)
                    print(f'  [CLIENT] 连接错误, 重建会话, 重试 {attempt+1}/{max_retries}...')
                    time.sleep(wait)
                    self._session = self._build_session()
                    continue
                raise RuntimeError('连接失败，已用尽重试次数')

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    print(f'  [CLIENT] 请求超时, 重试 {attempt+1}/{max_retries}...')
                    continue
                raise RuntimeError('请求超时，已用尽重试次数')

        raise RuntimeError('重试次数用尽')

    def _jittered_backoff(self, attempt: int) -> float:
        """去相关抖动退避。对标Hermes的jittered_backoff。"""
        base = min(2 ** attempt, 30)
        return random.uniform(0, base)

    def _parse_response(self, data: dict) -> dict:
        """解析API响应为统一格式。"""
        choice = data.get('choices', [{}])[0]
        message = choice.get('message', {})

        tool_calls = []
        for tc in message.get('tool_calls', []):
            tool_calls.append({
                'id': tc.get('id', ''),
                'function': {
                    'name': tc['function']['name'],
                    'arguments': tc['function'].get('arguments', '{}'),
                },
            })

        return {
            'content': message.get('content', '') or '',
            'tool_calls': tool_calls,
            'usage': data.get('usage', {}),
            'finish_reason': choice.get('finish_reason', ''),
        }

    def _clean_messages(self, messages: list[dict]) -> list[dict]:
        """清理消息格式，确保API兼容性。"""
        cleaned = []
        for msg in messages:
            m = {'role': msg['role'], 'content': msg.get('content', '') or ''}

            if msg.get('tool_calls'):
                m['tool_calls'] = [{
                    'id': tc.get('id', f'tc_{i}'),
                    'type': 'function',
                    'function': tc['function'],
                } for i, tc in enumerate(msg['tool_calls'])]
                if not m['content']:
                    m['content'] = None

            if msg.get('tool_call_id'):
                m['tool_call_id'] = msg['tool_call_id']

            if msg.get('name'):
                m['name'] = msg['name']

            cleaned.append(m)
        return cleaned
