"""
循环守卫
========
对齐 DeepSeek-TUI 的两阶段守卫模型：

  - check_pre():  执行前检测，返回 Block / Proceed
  - check_post(): 执行后检测，返回 Warn / Halt / Continue

阈值（与 TUI 一致）：
  - IDENTICAL_CALL_BLOCK_THRESHOLD = 3  相同调用第 3 次阻止执行
  - FAILURE_WARN_THRESHOLD       = 3  同一工具连续失败 3 次警告
  - FAILURE_HALT_THRESHOLD       = 8  同一工具连续失败 8 次终止
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field


# 与 TUI 对齐的阈值
IDENTICAL_CALL_BLOCK_THRESHOLD = 3
FAILURE_WARN_THRESHOLD = 3
FAILURE_HALT_THRESHOLD = 8


@dataclass
class LoopGuard:
    """
    两阶段循环守卫。

    检测机制：
    1. 相同调用重复（pre）→ Block
    2. 同一工具连续失败（post）→ Warn @ 3, Halt @ 8
    """

    # --- 内部状态 ---
    _call_counts: dict[tuple[str, str], int] = field(
        default_factory=lambda: defaultdict(int)
    )
    _failure_counts: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    _intervention_count: int = 0

    # ------------------------------------------------------------------
    # Pre-execution: identical-call blocking
    # ------------------------------------------------------------------
    def check_pre(self, tool_name: str, tool_args: dict) -> tuple[str, str]:
        """
        执行前检测。

        返回 (action, message)：
          action='proceed'  → 允许执行
          action='block'    → 阻止此次调用（不执行工具）
        """
        key = (tool_name, _canonical_json(tool_args))
        self._call_counts[key] += 1
        count = self._call_counts[key]

        if count >= IDENTICAL_CALL_BLOCK_THRESHOLD:
            self._intervention_count += 1
            return 'block', (
                f'Blocked: this exact call (`{tool_name}` with these arguments) '
                f'has already run {count} times. Stop retrying it unchanged. '
                f'Either change the arguments or pick a different tool.'
            )

        return 'proceed', ''

    # ------------------------------------------------------------------
    # Post-execution: per-tool failure warn / halt
    # ------------------------------------------------------------------
    def check_post(
        self,
        tool_name: str,
        success: bool,
    ) -> tuple[str, str]:
        """
        执行后检测。

        返回 (action, message)：
          action='continue' → 正常继续
          action='warn'     → 注入警告消息（模型下轮可见）
          action='halt'     → 终止 Agent 循环
        """
        if success:
            self._failure_counts[tool_name] = 0
            return 'continue', ''

        self._failure_counts[tool_name] += 1
        failures = self._failure_counts[tool_name]

        if failures >= FAILURE_HALT_THRESHOLD:
            self._intervention_count += 1
            return 'halt', (
                f'Stop retrying `{tool_name}` - it has failed {failures} '
                f'consecutive times. Choose a different approach.'
            )

        if failures == FAILURE_WARN_THRESHOLD:
            self._intervention_count += 1
            return 'warn', (
                f'Tool `{tool_name}` has failed {failures} consecutive times. '
                f'Consider changing your approach.'
            )

        return 'continue', ''

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    @property
    def stats(self) -> dict:
        return {
            'interventions': self._intervention_count,
            'failure_counts': dict(self._failure_counts),
        }

    def reset(self):
        """重置所有计数器。"""
        self._call_counts.clear()
        self._failure_counts.clear()
        self._intervention_count = 0


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _canonical_json(obj: dict) -> str:
    """
    生成顺序无关的 canonical JSON 字符串。
    对齐 TUI 的 hash_args：键按字母序排列，数组元素保持原序。
    """
    return json.dumps(_sort_keys(obj), separators=(',', ':'), ensure_ascii=False)


def _sort_keys(obj):
    """递归排序 dict 的键。"""
    if isinstance(obj, dict):
        return {k: _sort_keys(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_keys(v) for v in obj]
    return obj
