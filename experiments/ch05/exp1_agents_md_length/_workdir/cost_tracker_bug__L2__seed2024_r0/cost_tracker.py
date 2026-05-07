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

    def summary(self) -> dict[str, int]:
        """返回所有记录的字典副本（不泄露内部状态）。"""
        # 返回字典的副本，确保外部修改不会影响内部状态
        return dict(self._records)
