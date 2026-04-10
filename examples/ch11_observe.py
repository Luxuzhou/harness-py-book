"""
第11章 Token消耗分析
=====================
读取Agent运行产生的session jsonl文件，分析Token消耗分布。
纯文件解析，无需API。

用法: python examples/ch11_observe.py [session.jsonl路径]
      python examples/ch11_observe.py              # 使用内置示例数据
"""

import json
import sys
from collections import Counter
from pathlib import Path


def analyze_session(events: list[dict]) -> dict:
    """分析session事件列表。"""
    messages = [e for e in events if e.get('type') == 'message']
    tool_calls = [e for e in events if e.get('type') == 'tool_call']
    guards = [e for e in events if e.get('type') == 'loop_guard']

    tool_dist = Counter(tc.get('tool', '?') for tc in tool_calls)
    ok_count = sum(1 for tc in tool_calls if tc.get('ok'))
    fail_count = len(tool_calls) - ok_count

    # 估算Token（基于内容长度）
    total_chars = sum(len(str(m.get('content', ''))) for m in messages)
    est_tokens = total_chars // 3

    return {
        'messages': len(messages),
        'tool_calls': len(tool_calls),
        'tool_ok': ok_count,
        'tool_fail': fail_count,
        'tool_distribution': dict(tool_dist.most_common()),
        'guard_interventions': len(guards),
        'est_tokens': est_tokens,
    }


def format_report(stats: dict) -> str:
    """格式化分析报告。"""
    lines = [
        f'消息数: {stats["messages"]}',
        f'工具调用: {stats["tool_calls"]} (成功:{stats["tool_ok"]} 失败:{stats["tool_fail"]})',
        f'估算Token: ~{stats["est_tokens"]:,}',
        f'LoopGuard介入: {stats["guard_interventions"]}',
        '',
        '工具使用分布:',
    ]
    total_tools = max(sum(stats['tool_distribution'].values()), 1)
    for tool, count in stats['tool_distribution'].items():
        pct = count / total_tools * 100
        bar = '#' * int(pct / 2)
        lines.append(f'  {tool:<15} {count:>3} ({pct:4.1f}%) {bar}')
    return '\n'.join(lines)


def load_jsonl(path: Path) -> list[dict]:
    """加载jsonl文件。"""
    events = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def demo_with_sample():
    """用内置样本数据演示。"""
    sample_events = [
        {'type': 'message', 'role': 'system', 'content': 'You are a coding assistant.' * 20},
        {'type': 'message', 'role': 'user', 'content': '请重构这个项目的数据库层'},
        {'type': 'tool_call', 'tool': 'glob_search', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'message', 'role': 'assistant', 'content': '我已经理解了项目结构，开始重构。' * 5},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': False},
        {'type': 'tool_call', 'tool': 'bash', 'ok': True},
        {'type': 'tool_call', 'tool': 'bash', 'ok': False},
        {'type': 'loop_guard', 'message': '连续失败'},
        {'type': 'tool_call', 'tool': 'read_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'edit_file', 'ok': True},
        {'type': 'tool_call', 'tool': 'bash', 'ok': True},
        {'type': 'message', 'role': 'assistant', 'content': '重构完成，所有测试通过。'},
    ]
    return sample_events


def main():
    print('=== 第11章 Token消耗分析 ===\n')

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f'文件不存在: {path}')
            sys.exit(1)
        events = load_jsonl(path)
        print(f'加载: {path} ({len(events)} 事件)')
    else:
        events = demo_with_sample()
        print(f'使用内置样本数据 ({len(events)} 事件)')

    print()
    stats = analyze_session(events)
    print(format_report(stats))


if __name__ == '__main__':
    main()
