"""
第11章：观测与成本——分析jsonl session文件的Token消耗
====================================================
不需要API key。读取一个已有的jsonl session文件，输出消耗分析。
用法: python standalone/ch11_observe.py [session.jsonl路径]
      python standalone/ch11_observe.py  ← 无参数时使用演示数据
"""
import json
import sys
from pathlib import Path
from collections import Counter


def analyze_session(events: list[dict]) -> dict:
    """分析session事件列表。"""
    stats = {
        'total_events': len(events),
        'messages': Counter(),
        'tools': Counter(),
        'total_input_chars': 0,
        'total_output_chars': 0,
        'compression_events': 0,
    }

    for e in events:
        t = e.get('type', '')
        if t in ('user', 'assistant', 'system', 'tool_result'):
            stats['messages'][t] += 1
            content = str(e.get('message', {}).get('content', ''))
            if t in ('user', 'system'):
                stats['total_input_chars'] += len(content)
            elif t == 'assistant':
                stats['total_output_chars'] += len(content)
            elif t == 'tool_result':
                stats['total_input_chars'] += len(content)
                try:
                    td = json.loads(content)
                    stats['tools'][td.get('tool', 'unknown')] += 1
                except:
                    pass
            if 'compacted' in content.lower() or 'snipped' in content.lower():
                stats['compression_events'] += 1

    return stats


def format_report(stats: dict, model: str = 'deepseek-chat') -> str:
    """生成分析报告。"""
    input_tokens = stats['total_input_chars'] // 4
    output_tokens = stats['total_output_chars'] // 4

    # DeepSeek定价（2026年4月）
    pricing = {
        'deepseek-chat': (0.27, 1.10),  # $/MTok (input, output)
        'claude-opus-4-6': (5.00, 25.00),
        'gpt-5.4': (2.50, 15.00),
    }
    in_price, out_price = pricing.get(model, (0.27, 1.10))
    cost = (input_tokens * in_price + output_tokens * out_price) / 1_000_000

    lines = [
        f'Session分析报告',
        f'{"=" * 45}',
        f'总事件数:     {stats["total_events"]}',
        f'消息分布:     user={stats["messages"].get("user",0)} '
        f'assistant={stats["messages"].get("assistant",0)} '
        f'tool={stats["messages"].get("tool_result",0)} '
        f'system={stats["messages"].get("system",0)}',
        f'',
        f'Token估算（粗略）:',
        f'  输入:       ~{input_tokens:,} tokens ({stats["total_input_chars"]:,}字符)',
        f'  输出:       ~{output_tokens:,} tokens ({stats["total_output_chars"]:,}字符)',
        f'  总计:       ~{input_tokens + output_tokens:,} tokens',
        f'',
        f'工具使用分布:',
    ]
    for tool, count in stats['tools'].most_common():
        pct = count / sum(stats['tools'].values()) * 100
        bar = '█' * int(pct / 5)
        lines.append(f'  {tool:15s} {count:3d}次 ({pct:4.1f}%) {bar}')

    lines.extend([
        f'',
        f'压缩事件:     {stats["compression_events"]}次',
        f'',
        f'成本估算（{model}）:',
        f'  输入:       ${input_tokens * in_price / 1_000_000:.4f}',
        f'  输出:       ${output_tokens * out_price / 1_000_000:.4f}',
        f'  总计:       ${cost:.4f}',
        f'',
        f'如果用Claude Opus 4.6:',
        f'  总计:       ${(input_tokens * 5.0 + output_tokens * 25.0) / 1_000_000:.4f}',
        f'  倍数:       {(input_tokens * 5.0 + output_tokens * 25.0) / max(input_tokens * in_price + output_tokens * out_price, 0.001):.1f}x',
    ])
    return '\n'.join(lines)


def demo_data() -> list[dict]:
    """生成演示数据。"""
    events = [
        {'type': 'permission-mode', 'permissionMode': 'auto'},
        {'type': 'system', 'message': {'role': 'system', 'content': 'You are a coding agent.' * 50}},
        {'type': 'user', 'message': {'role': 'user', 'content': '请分析这个项目并重构main模块'}},
    ]
    tools = ['read_file'] * 8 + ['grep_search'] * 4 + ['edit_file'] * 3 + ['bash'] * 2 + ['write_file'] * 1
    for tool in tools:
        events.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': f'让我{tool}...' * 5}})
        events.append({'type': 'tool_result', 'message': {'role': 'tool', 'content': json.dumps({'tool': tool, 'ok': True, 'content': '结果' * 100})}})
    events.append({'type': 'assistant', 'message': {'role': 'assistant', 'content': '任务完成。所有修改已提交。' * 3}})
    return events


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║  第11章：观测与成本分析                               ║
╚══════════════════════════════════════════════════════╝
""")

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f'文件不存在: {path}')
            return
        events = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except:
                    pass
        print(f'读取: {path.name} ({len(events)}条事件)\n')
    else:
        events = demo_data()
        print(f'使用演示数据（{len(events)}条事件）\n')

    stats = analyze_session(events)
    print(format_report(stats))


if __name__ == '__main__':
    main()
