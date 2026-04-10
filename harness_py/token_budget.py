"""
Token预算管理：显式分配上下文窗口
=================================
Ch6记忆层的基础设施。五区分配 + 留白原则。
"""
from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    """粗略估算token数。中文约1.5tok/字，英文约0.25tok/word。"""
    if not text:
        return 0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return max(1, int(chinese * 1.5 + other * 0.3))


@dataclass(frozen=True)
class TokenBudget:
    context_window: int
    output_reserve: int
    system_prompt: int
    memory: int
    current_task: int
    history: int

    @classmethod
    def allocate(cls, context_window: int) -> TokenBudget:
        output = int(context_window * 0.15)
        system = int(context_window * 0.10)
        memory = int(context_window * 0.05)
        current = int(context_window * 0.20)
        history = context_window - output - system - memory - current
        return cls(context_window, output, system, memory, current, max(0, history))


def should_compress(budget: TokenBudget, total_tokens: int, threshold_pct: float = 0.80) -> tuple[bool, str]:
    """判断是否需要压缩。"""
    threshold = int(budget.context_window * threshold_pct)
    if total_tokens > budget.context_window - budget.output_reserve:
        return True, f'紧急：侵占了输出预留（{total_tokens:,} > {budget.context_window - budget.output_reserve:,}）'
    if total_tokens > threshold:
        pct = total_tokens / budget.context_window * 100
        return True, f'超过阈值（{pct:.0f}% > {threshold_pct*100:.0f}%）'
    return False, ''


def format_budget(budget: TokenBudget, total_used: int) -> str:
    pct = total_used / budget.context_window * 100 if budget.context_window > 0 else 0
    return (
        f'Token: {total_used:,}/{budget.context_window:,} ({pct:.0f}%) | '
        f'History budget: {budget.history:,} | Output reserve: {budget.output_reserve:,}'
    )
