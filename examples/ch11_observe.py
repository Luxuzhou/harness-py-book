"""
第 11 章 Token 消耗 + 成本分析
==============================
读取 Agent 运行产生的 session jsonl 文件，分析 Token 消耗分布并按模型定价
换算成美元成本。纯文件解析，无需 API。

用法:
    python examples/ch11_observe.py                    # 使用内置示例数据 + deepseek 定价
    python examples/ch11_observe.py session.jsonl      # 分析指定会话
    python examples/ch11_observe.py session.jsonl --model claude-opus-4-6

定价来源: 与 harness_py_pro/token_budget.py::MODEL_PRICING 同步。
生产场景的权威成本数据请以 harness_py_pro/token_budget.py::CostTracker 为准，
本脚本仅用于本章节的离线教学演示。
"""

import json
import sys
from collections import Counter
from pathlib import Path


# === 与 harness_py_pro/token_budget.py::MODEL_PRICING 同步 ===
# (input_price, output_price) per 1M tokens, in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    'deepseek-chat': (0.27, 1.10),
    'deepseek-reasoner': (0.55, 2.19),
    'gpt-4o': (2.50, 10.00),
    'gpt-4o-mini': (0.15, 0.60),
    'gpt-4.1': (2.00, 8.00),
    'gpt-4.1-mini': (0.40, 1.60),
    'claude-sonnet-4-6': (3.00, 15.00),
    'claude-opus-4-6': (15.00, 75.00),
    'claude-haiku-4-5': (0.80, 4.00),
}


def analyze_session(events: list[dict]) -> dict:
    """分析 session 事件列表。"""
    messages = [e for e in events if e.get('type') == 'message']
    tool_calls = [e for e in events if e.get('type') == 'tool_call']
    guards = [e for e in events if e.get('type') == 'loop_guard']

    tool_dist = Counter(tc.get('tool', '?') for tc in tool_calls)
    ok_count = sum(1 for tc in tool_calls if tc.get('ok'))
    fail_count = len(tool_calls) - ok_count

    # 粗粒度 token 估算：按字符数 / 3 近似（中英文混合）
    # 生产场景应使用模型原生 tokenizer；这里的估算足够得出数量级
    user_chars = sum(
        len(str(m.get('content', '')))
        for m in messages
        if m.get('role') in ('user', 'system')
    )
    asst_chars = sum(
        len(str(m.get('content', '')))
        for m in messages
        if m.get('role') == 'assistant'
    )
    input_tokens = user_chars // 3
    output_tokens = asst_chars // 3

    return {
        'messages': len(messages),
        'tool_calls': len(tool_calls),
        'tool_ok': ok_count,
        'tool_fail': fail_count,
        'tool_distribution': dict(tool_dist.most_common()),
        'guard_interventions': len(guards),
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'est_tokens': input_tokens + output_tokens,
    }


def estimate_cost(stats: dict, model: str) -> dict:
    """按模型定价换算成本。"""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return {
            'model': model,
            'known_pricing': False,
            'note': f'未登记定价：{model}。已知模型：{sorted(MODEL_PRICING)}',
        }
    in_price, out_price = pricing
    input_cost = stats['input_tokens'] * in_price / 1_000_000
    output_cost = stats['output_tokens'] * out_price / 1_000_000
    return {
        'model': model,
        'known_pricing': True,
        'input_price_per_mtok': in_price,
        'output_price_per_mtok': out_price,
        'input_cost_usd': round(input_cost, 6),
        'output_cost_usd': round(output_cost, 6),
        'total_cost_usd': round(input_cost + output_cost, 6),
    }


def project_monthly_budget(single_cost_usd: float,
                           sessions_per_day: int = 5,
                           work_days_per_month: int = 22) -> dict:
    """把单次会话成本外推为月度预算估算（仅参考）。"""
    daily = single_cost_usd * sessions_per_day
    monthly = daily * work_days_per_month
    return {
        'single_session_usd': round(single_cost_usd, 6),
        'assumed_sessions_per_day': sessions_per_day,
        'assumed_work_days_per_month': work_days_per_month,
        'projected_monthly_usd': round(monthly, 4),
        'projected_monthly_usd_with_20pct_buffer': round(monthly * 1.2, 4),
    }


def format_report(stats: dict, cost: dict, monthly: dict | None = None) -> str:
    """格式化分析报告。"""
    lines = [
        f'消息数: {stats["messages"]}',
        f'工具调用: {stats["tool_calls"]} '
        f'(成功:{stats["tool_ok"]} 失败:{stats["tool_fail"]})',
        f'估算 Token: ~{stats["est_tokens"]:,} '
        f'(input ~{stats["input_tokens"]:,} / output ~{stats["output_tokens"]:,})',
        f'LoopGuard 介入: {stats["guard_interventions"]}',
        '',
        '工具使用分布:',
    ]
    total_tools = max(sum(stats['tool_distribution'].values()), 1)
    for tool, count in stats['tool_distribution'].items():
        pct = count / total_tools * 100
        bar = '#' * int(pct / 2)
        lines.append(f'  {tool:<15} {count:>3} ({pct:4.1f}%) {bar}')

    lines.append('')
    lines.append(f'成本估算（模型 {cost["model"]}）:')
    if cost.get('known_pricing'):
        lines.append(
            f'  input  ~{stats["input_tokens"]:,} × ${cost["input_price_per_mtok"]}/MTok '
            f'= ${cost["input_cost_usd"]:.6f}'
        )
        lines.append(
            f'  output ~{stats["output_tokens"]:,} × ${cost["output_price_per_mtok"]}/MTok '
            f'= ${cost["output_cost_usd"]:.6f}'
        )
        lines.append(f'  合计: ${cost["total_cost_usd"]:.6f}')
    else:
        lines.append(f'  {cost.get("note")}')

    if monthly and cost.get('known_pricing'):
        lines.append('')
        lines.append('月度预算推演（默认 5 会话/天 × 22 工作日）:')
        lines.append(
            f'  单次 ${monthly["single_session_usd"]:.6f} × '
            f'{monthly["assumed_sessions_per_day"]} × '
            f'{monthly["assumed_work_days_per_month"]} '
            f'= ${monthly["projected_monthly_usd"]:.4f}'
        )
        lines.append(
            f'  含 20% 缓冲: ${monthly["projected_monthly_usd_with_20pct_buffer"]:.4f}'
        )
    return '\n'.join(lines)


def load_jsonl(path: Path) -> list[dict]:
    """加载 jsonl 文件。"""
    events = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def demo_with_sample() -> list[dict]:
    """用内置样本数据演示。"""
    return [
        {'type': 'message', 'role': 'system',
         'content': 'You are a coding assistant.' * 20},
        {'type': 'message', 'role': 'user',
         'content': '请重构这个项目的数据库层'},
        {'type': 'tool_call', 'tool': 'glob_search', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'message', 'role': 'assistant',
         'content': '我已经理解了项目结构，开始重构。' * 5},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': False},
        {'type': 'tool_call', 'tool': 'bash', 'ok': True},
        {'type': 'tool_call', 'tool': 'bash', 'ok': False},
        {'type': 'loop_guard', 'message': '连续失败'},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'bash', 'ok': True},
        {'type': 'message', 'role': 'assistant',
         'content': '重构完成，所有测试通过。'},
    ]


def main():
    print('=== 第 11 章 Token 消耗 + 成本分析 ===\n')

    args = sys.argv[1:]
    model = 'deepseek-chat'
    session_path: Path | None = None
    i = 0
    while i < len(args):
        if args[i] == '--model' and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        else:
            session_path = Path(args[i])
            i += 1

    if session_path:
        if not session_path.exists():
            print(f'文件不存在: {session_path}')
            sys.exit(1)
        events = load_jsonl(session_path)
        print(f'加载: {session_path} ({len(events)} 事件)')
    else:
        events = demo_with_sample()
        print(f'使用内置样本数据 ({len(events)} 事件)')

    print(f'定价模型: {model}\n')

    stats = analyze_session(events)
    cost = estimate_cost(stats, model)
    monthly = (
        project_monthly_budget(cost['total_cost_usd'])
        if cost.get('known_pricing') else None
    )
    print(format_report(stats, cost, monthly))


if __name__ == '__main__':
    main()
