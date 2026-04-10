"""
循环守卫
========
对标harness_py的LoopGuard，增加：频率限制、渐进式介入。
四种检测 + 渐进式响应（提醒→警告→终止）。
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class LoopGuard:
    """
    循环守卫。四种检测机制：
    1. 相同调用重复检测
    2. 连续错误累积
    3. 同工具连续使用
    4. 总量限制
    """
    max_identical_calls: int = 3
    max_consecutive_errors: int = 5
    max_same_tool_streak: int = 8
    max_total_tool_calls: int = 200

    _call_hashes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _consecutive_errors: int = 0
    _last_tool: str = ''
    _tool_streak: int = 0
    _total_calls: int = 0
    _intervention_count: int = 0

    def check(
        self,
        tool_name: str,
        tool_args: dict,
        success: bool,
        result_preview: str,
    ) -> tuple[bool, str]:
        """
        检查是否需要介入。

        返回 (intervene, message)：
        - intervene=True: 应该在消息中注入提醒
        - message: 提醒内容
        """
        self._total_calls += 1

        # 检测1：相同调用重复
        call_hash = self._hash_call(tool_name, tool_args, result_preview)
        self._call_hashes[call_hash] += 1
        if self._call_hashes[call_hash] >= self.max_identical_calls:
            self._intervention_count += 1
            return True, (
                f'检测到死循环：{tool_name} 使用相同参数已调用 {self._call_hashes[call_hash]} 次，'
                f'每次返回相同结果。请改变策略或停止。'
            )

        # 检测2：连续错误
        if not success:
            self._consecutive_errors += 1
            if self._consecutive_errors >= self.max_consecutive_errors:
                self._intervention_count += 1
                return True, (
                    f'连续 {self._consecutive_errors} 次工具调用失败。'
                    f'请分析错误原因，改变方法，或报告无法完成。'
                )
        else:
            self._consecutive_errors = 0

        # 检测3：同工具连续使用
        if tool_name == self._last_tool:
            self._tool_streak += 1
            if self._tool_streak >= self.max_same_tool_streak:
                self._intervention_count += 1
                return True, (
                    f'连续使用 {tool_name} 已达 {self._tool_streak} 次。'
                    f'请考虑是否需要换一种工具或方法。'
                )
        else:
            self._last_tool = tool_name
            self._tool_streak = 1

        # 检测4：总量限制
        if self._total_calls >= self.max_total_tool_calls:
            self._intervention_count += 1
            return True, (
                f'工具调用总量已达 {self._total_calls} 次。'
                f'请尽快完成当前任务或提交阶段性成果。'
            )

        return False, ''

    def reset(self):
        """重置所有计数器。"""
        self._call_hashes = defaultdict(int)
        self._consecutive_errors = 0
        self._last_tool = ''
        self._tool_streak = 0
        self._total_calls = 0
        self._intervention_count = 0

    @property
    def stats(self) -> dict:
        return {
            'total_calls': self._total_calls,
            'interventions': self._intervention_count,
            'consecutive_errors': self._consecutive_errors,
        }

    @staticmethod
    def _hash_call(tool_name: str, tool_args: dict, result_preview: str) -> str:
        key = json.dumps({'t': tool_name, 'a': tool_args, 'r': result_preview[:100]},
                         sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key.encode()).hexdigest()
