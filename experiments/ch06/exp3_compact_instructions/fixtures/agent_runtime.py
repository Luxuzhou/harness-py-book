"""Agent 运行时的最小实现（待 Agent 集成 CostTracker）。"""
from __future__ import annotations

import json


class AgentRuntime:
    """极简 Agent 运行时。"""

    def __init__(self, model: str = 'deepseek-chat'):
        self.model = model
        self.history: list[dict] = []
        # TODO: 实例化 CostTracker

    def step(self, user_message: str) -> dict:
        """单步调用：接受用户消息，返回模拟的 LLM 响应。"""
        self.history.append({'role': 'user', 'content': user_message})
        # 模拟 LLM 响应（测试用，不真调 API）
        response = {
            'content': f'[simulated reply to: {user_message[:40]}]',
            'usage': {
                'prompt_tokens': 1500 + 100 * len(self.history),
                'completion_tokens': 120,
            },
        }
        self.history.append({'role': 'assistant', 'content': response['content']})
        # TODO: 调用 tracker.record 记录 input/output tokens
        return response

    def shutdown(self) -> None:
        """关闭运行时，输出统计。"""
        # TODO: 调用 tracker.summary 并 print(json.dumps(..., indent=2))
        pass
