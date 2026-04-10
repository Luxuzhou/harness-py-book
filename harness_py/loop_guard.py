"""
循环守卫：防止Agent陷入死循环
==============================
Ch7验证层的核心组件。检测重复调用、连续错误、频率异常。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class LoopGuard:
    """嵌入Agent主循环的守卫。每次工具调用后检查是否陷入循环。"""

    max_identical_calls: int = 3
    max_consecutive_errors: int = 5
    max_same_tool_streak: int = 10
    max_total_tool_calls: int = 100

    _recent_calls: list[str] = field(default_factory=list)
    _consecutive_errors: int = 0
    _same_tool_streak: int = 0
    _last_tool_name: str = ''
    _total_calls: int = 0

    def check(self, tool_name: str, tool_args: dict, result_ok: bool, result_preview: str) -> tuple[bool, str]:
        """返回 (should_intervene, message)。"""
        self._total_calls += 1

        if self._total_calls > self.max_total_tool_calls:
            return True, f'工具调用总量已达{self._total_calls}次。请总结进度并停止。'

        if not result_ok:
            self._consecutive_errors += 1
            if self._consecutive_errors >= self.max_consecutive_errors:
                return True, f'已连续{self._consecutive_errors}次失败。请换一种方法或报告无法完成。'
        else:
            self._consecutive_errors = 0

        if tool_name == self._last_tool_name:
            self._same_tool_streak += 1
            if self._same_tool_streak >= self.max_same_tool_streak:
                return True, f'已连续{self._same_tool_streak}次调用{tool_name}。请换一种方法。'
        else:
            self._same_tool_streak = 1
            self._last_tool_name = tool_name

        args_hash = hashlib.md5(json.dumps(tool_args, sort_keys=True, default=str).encode()).hexdigest()[:12]
        sig = f'{tool_name}:{args_hash}:{result_preview[:200]}'
        self._recent_calls.append(sig)
        if len(self._recent_calls) > 10:
            self._recent_calls = self._recent_calls[-10:]

        if len(self._recent_calls) >= self.max_identical_calls:
            tail = self._recent_calls[-self.max_identical_calls:]
            if len(set(tail)) == 1:
                return True, (
                    f'检测到死循环：最近{self.max_identical_calls}次调用完全相同（{tool_name}）。'
                    f'请立即停止重试，换一种完全不同的策略。'
                )

        return False, ''

    def reset(self) -> None:
        self._recent_calls.clear()
        self._consecutive_errors = 0
        self._same_tool_streak = 0
        self._last_tool_name = ''
        self._total_calls = 0
