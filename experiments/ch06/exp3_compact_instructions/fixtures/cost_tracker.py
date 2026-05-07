"""CostTracker 起始实现（待 Agent 添加 summary 方法）。"""
from __future__ import annotations


class CostTracker:
    """追踪 LLM 调用的 token 消耗和成本。"""

    INPUT_PRICE_PER_MTOK = 0.28  # USD
    OUTPUT_PRICE_PER_MTOK = 1.10  # USD

    def __init__(self):
        self._records: dict[str, int] = {'input': 0, 'output': 0}

    def record(self, key: str, value: int) -> None:
        """记录一次 token 用量。key 为 'input' 或 'output'。"""
        if key not in self._records:
            self._records[key] = 0
        self._records[key] += value

    # TODO: 实现 summary 方法
    # 返回 {'total_input_tokens', 'total_output_tokens', 'total_cost_usd'}
