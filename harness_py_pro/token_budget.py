"""
Token预算与成本追踪
====================
对标OpenHarness的token_estimation + Hermes的usage_pricing。
harness_py教学层只做了len/3粗估，生产层需要精确到模型级别。

两个组件：
1. TokenEstimator — 精确估算消息token数
2. CostTracker — 实时成本追踪与预算控制
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ============ Token估算 ============

# 各模型的token/字符比率（经验值，基于tokenizer分析）
MODEL_CHAR_RATIOS = {
    # OpenAI系列：cl100k_base tokenizer
    'gpt-4': 3.2,
    'gpt-4o': 3.5,
    'gpt-4.1': 3.5,
    'gpt-5': 3.5,
    # Anthropic系列
    'claude': 3.3,
    'claude-3': 3.3,
    'claude-4': 3.3,
    # DeepSeek
    'deepseek': 2.5,  # 中文tokenizer效率更高
    # 默认
    'default': 3.0,
}

# 工具调用的固定overhead（token数）
TOOL_CALL_OVERHEAD = 50  # 每个tool_call的schema约50 tokens
MESSAGE_OVERHEAD = 4  # 每条消息的role/formatting overhead


def _get_char_ratio(model: str) -> float:
    """根据模型名获取字符/token比率。"""
    model_lower = model.lower()
    for prefix, ratio in MODEL_CHAR_RATIOS.items():
        if prefix in model_lower:
            return ratio
    return MODEL_CHAR_RATIOS['default']


def estimate_message_tokens(message: dict, model: str = 'default') -> int:
    """
    精确估算单条消息的token数。

    考虑因素：
    - 文本内容的字符/token比率（按模型区分）
    - tool_calls的JSON结构开销
    - 中文字符的特殊处理
    """
    ratio = _get_char_ratio(model)
    tokens = MESSAGE_OVERHEAD

    content = str(message.get('content', '') or '')
    if content:
        # 中文字符通常1-2个token，英文3-4个字符1个token
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        en_chars = len(content) - cn_chars
        tokens += int(cn_chars * 1.5 + en_chars / ratio)

    # tool_calls
    for tc in message.get('tool_calls', []):
        tokens += TOOL_CALL_OVERHEAD
        args_str = tc.get('function', {}).get('arguments', '{}')
        tokens += len(args_str) // 4

    return max(tokens, 1)


def estimate_tokens(messages: list[dict], model: str = 'default') -> int:
    """估算整个消息列表的token数。"""
    return sum(estimate_message_tokens(m, model) for m in messages)


def estimate_tools_tokens(tool_schemas: list[dict], model: str = 'default') -> int:
    """估算工具schema占用的token数。"""
    total = 0
    for schema in tool_schemas:
        total += 150
        # 参数描述的额外token
        params = schema.get('parameters', {})
        props = params.get('properties', {})
        for prop_name, prop_def in props.items():
            desc = prop_def.get('description', '')
            total += len(desc) // 4
    return total


# ============ 五区预算分配 ============

@dataclass
class TokenBudget:
    """
    Token预算五区分配。对标Claude Code的预算模型。

    ┌─────────────────────────────┐
    │ Zone 1: System Prompt (10%) │
    │ Zone 2: Tools Schema  (5%) │
    │ Zone 3: Context      (55%) │
    │ Zone 4: Output       (15%) │
    │ Zone 5: Safety Buffer(15%) │
    └─────────────────────────────┘
    """
    total: int
    system: int
    tools: int
    context: int
    output: int
    safety: int

    @classmethod
    def allocate(cls, context_window: int) -> TokenBudget:
        return cls(
            total=context_window,
            system=int(context_window * 0.10),
            tools=int(context_window * 0.05),
            context=int(context_window * 0.55),
            output=int(context_window * 0.15),
            safety=int(context_window * 0.15),
        )

    @property
    def available_for_messages(self) -> int:
        """消息可用空间 = total - system - tools - output - safety。"""
        return self.total - self.system - self.tools - self.output - self.safety

    def should_compress(self, current_tokens: int, threshold_pct: float = 0.7) -> tuple[bool, str]:
        """判断是否需要压缩。"""
        limit = self.available_for_messages
        if current_tokens > int(limit * threshold_pct):
            return True, f'tokens={current_tokens:,} > {int(limit * threshold_pct):,} ({threshold_pct:.0%})'
        return False, ''


def format_budget(budget: TokenBudget, current_tokens: int) -> str:
    """格式化预算报告。"""
    used_pct = current_tokens / budget.available_for_messages * 100 if budget.available_for_messages else 0
    return (
        f'total={budget.total:,} '
        f'available={budget.available_for_messages:,} '
        f'used={current_tokens:,} ({used_pct:.1f}%)'
    )


# ============ 成本追踪 ============

# 主流模型定价 (USD per 1M tokens, 2026-04数据)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_price, output_price) per 1M tokens
    'deepseek-chat': (0.27, 1.10),
    'deepseek-reasoner': (0.55, 2.19),
    'gpt-4o': (2.50, 10.00),
    'gpt-4o-mini': (0.15, 0.60),
    'gpt-4.1': (2.00, 8.00),
    'gpt-4.1-mini': (0.40, 1.60),
    'gpt-4.1-nano': (0.10, 0.40),
    'gpt-5': (5.00, 15.00),
    'claude-sonnet-4-6': (3.00, 15.00),
    'claude-opus-4-6': (15.00, 75.00),
    'claude-haiku-4-5': (0.80, 4.00),
}


@dataclass
class CostTracker:
    """
    实时成本追踪器。

    功能：
    1. 按API调用记录input/output tokens
    2. 按模型计算累计成本
    3. 预算告警（可选）
    """
    budget_usd: float = 0.0  # 0表示无上限
    _records: list[dict] = field(default_factory=list)
    _total_input: int = 0
    _total_output: int = 0

    def record(self, model: str, input_tokens: int, output_tokens: int):
        """记录一次API调用。"""
        self._total_input += input_tokens
        self._total_output += output_tokens

        cost = self._calculate_cost(model, input_tokens, output_tokens)
        self._records.append({
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': cost,
        })

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算单次调用成本。"""
        pricing = self._find_pricing(model)
        if not pricing:
            return 0.0
        input_price, output_price = pricing
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    def _find_pricing(self, model: str) -> tuple[float, float] | None:
        """查找模型定价。"""
        model_lower = model.lower()
        for key, pricing in MODEL_PRICING.items():
            if key in model_lower:
                return pricing
        return None

    @property
    def total_cost(self) -> float:
        return sum(r['cost_usd'] for r in self._records)

    @property
    def over_budget(self) -> bool:
        if self.budget_usd <= 0:
            return False
        return self.total_cost >= self.budget_usd

    def summary(self) -> dict:
        """生成成本摘要。"""
        by_model: dict[str, dict] = {}
        for r in self._records:
            m = r['model']
            if m not in by_model:
                by_model[m] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0}
            by_model[m]['calls'] += 1
            by_model[m]['input_tokens'] += r['input_tokens']
            by_model[m]['output_tokens'] += r['output_tokens']
            by_model[m]['cost_usd'] += r['cost_usd']

        return {
            'total_calls': len(self._records),
            'total_input_tokens': self._total_input,
            'total_output_tokens': self._total_output,
            'total_cost_usd': round(self.total_cost, 6),
            'budget_usd': self.budget_usd,
            'budget_remaining': round(self.budget_usd - self.total_cost, 6) if self.budget_usd > 0 else None,
            'by_model': by_model,
        }

    def format_report(self) -> str:
        """格式化成本报告。"""
        s = self.summary()
        lines = [
            f'成本报告:',
            f'  API调用: {s["total_calls"]} 次',
            f'  Input tokens: {s["total_input_tokens"]:,}',
            f'  Output tokens: {s["total_output_tokens"]:,}',
            f'  总成本: ${s["total_cost_usd"]:.4f}',
        ]
        if s['budget_usd']:
            lines.append(f'  预算: ${s["budget_usd"]:.2f} (剩余: ${s["budget_remaining"]:.4f})')

        for model, data in s['by_model'].items():
            lines.append(f'  [{model}] {data["calls"]}次 '
                         f'in={data["input_tokens"]:,} out={data["output_tokens"]:,} '
                         f'${data["cost_usd"]:.4f}')
        return '\n'.join(lines)
