"""简易成本追踪器。记录API调用的token消耗。"""
from __future__ import annotations

from collections import defaultdict


class CostTracker:
    """按键累加记录的计数器。"""

    def __init__(self) -> None:
        self._records: dict[str, int] = defaultdict(int)

    def record(self, key: str, amount: int) -> None:
        """累加某个键的数值。"""
        if amount < 0:
            raise ValueError(f'amount must be non-negative, got {amount}')
        self._records[key] += amount

    # TODO: 需要补充 summary() 方法。
    # 该方法应返回所有记录的字典副本（不泄露内部状态）。
    # 空记录时应返回空字典 {}。
