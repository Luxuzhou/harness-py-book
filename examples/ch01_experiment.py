"""
第1章 实验结果展示
==================
从experiments/results/ch01_*.json读取真实实验数据并展示对比。
不硬编码任何数据——所有数字来自实际运行。

用法: python examples/ch01_experiment.py
"""

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / 'experiments' / 'results'


def load_results() -> list[dict]:
    """从结果文件加载实验数据。"""
    results = []
    for pattern in ['ch01_claude*.json', 'ch01_codex*.json', 'ch01_harness*.json', 'ch01_deepseek*.json']:
        for f in sorted(RESULTS_DIR.glob(pattern)):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                results.append(data)
            except (json.JSONDecodeError, OSError) as e:
                print(f'警告: 无法加载 {f.name}: {e}')
    return results


def main():
    results = load_results()

    if not results:
        print('未找到实验结果文件。')
        print(f'请先运行实验：')
        print(f'  1. Claude Code: claude "任务描述..." → python experiments/ch01_capture.py claude')
        print(f'  2. Codex:       codex "任务描述..."  → python experiments/ch01_capture.py codex')
        print(f'  3. DeepSeek:    python experiments/ch01_run_deepseek.py')
        print(f'\n实验任务定义: experiments/ch01_task.md')
        sys.exit(1)

    print('='*70)
    print('  第1章实验：同一任务，三种Harness，三组真实数据')
    print('='*70)

    for r in results:
        agent = r.get('agent', '?')
        model = r.get('model', '?')
        turns = r.get('turns', '?')
        tools = r.get('tool_calls', '?')
        tokens = r.get('total_tokens', 0)
        duration = r.get('duration_seconds', 0)
        cost = r.get('cost_usd', 0)
        outcome = r.get('outcome', '?')
        test_passed = r.get('test_passed', False)

        # 格式化耗时
        if isinstance(duration, (int, float)) and duration > 0:
            if duration >= 60:
                time_str = f'{duration/60:.1f}m'
            else:
                time_str = f'{duration:.0f}s'
        else:
            time_str = '?'

        print(f'\n--- {agent} ({model}) ---')
        print(f'  轮次: {turns}  工具调用: {tools}')
        print(f'  Token: {tokens:,}  耗时: {time_str}  成本: ${cost:.4f}' if cost else f'  Token: {tokens:,}  耗时: {time_str}')
        print(f'  测试: {"通过" if test_passed else "未通过"}')
        print(f'  结果: {outcome}')

    print('\n' + '='*70)
    print(f'  数据来源: {RESULTS_DIR}/')
    print(f'  文件数: {len(results)}')
    print('='*70)

    # 如果有失败案例，分析故障链
    failed = [r for r in results if not r.get('test_passed', False)]
    if failed:
        print('\n失败案例分析:')
        for r in failed:
            print(f'  {r["agent"]}: {r.get("outcome", "?")}')


if __name__ == '__main__':
    main()
