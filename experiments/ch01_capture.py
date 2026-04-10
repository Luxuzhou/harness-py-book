"""
Ch1实验数据捕获脚本
===================
每次实验运行后执行此脚本，录入实验结果。
数据保存到 experiments/results/ch01_<agent>.json

用法:
  python experiments/ch01_capture.py claude    # Claude Code跑完后
  python experiments/ch01_capture.py codex     # Codex跑完后
  python experiments/ch01_capture.py deepseek  # DeepSeek自动捕获（由ch01_run_deepseek.py调用）
"""

import json
import sys
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def capture_manual(agent_name: str):
    """手动录入实验结果（Claude Code / Codex运行后）。"""
    print(f'\n=== 录入 {agent_name} 实验结果 ===\n')

    model = input('模型名称 (如 Claude Opus 4.6): ').strip()
    turns = int(input('总轮次 (从Agent输出中获取): '))
    tool_calls = int(input('工具调用次数: '))
    input_tokens = int(input('输入Token数 (如无法获取填0): '))
    output_tokens = int(input('输出Token数 (如无法获取填0): '))
    total_tokens = int(input('总Token数: '))
    duration_seconds = float(input('耗时(秒): '))
    cost_usd = float(input('成本(美元, 如无法获取填0): '))
    test_passed = input('测试是否全部通过 (y/n): ').strip().lower() == 'y'
    outcome = input('结果描述 (如"完成，测试全通过"): ').strip()

    record = {
        'agent': agent_name,
        'model': model,
        'turns': turns,
        'tool_calls': tool_calls,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'duration_seconds': duration_seconds,
        'cost_usd': cost_usd,
        'test_passed': test_passed,
        'outcome': outcome,
        'captured_at': datetime.now().isoformat(),
        'task': 'CostTracker集成（summary方法+agent.py集成+单元测试）',
    }

    filename = f'ch01_{agent_name.lower().replace(" ", "_")}.json'
    out_path = RESULTS_DIR / filename
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n已保存: {out_path}')
    print(json.dumps(record, ensure_ascii=False, indent=2))


def capture_auto(record: dict):
    """自动保存实验结果（DeepSeek运行后由程序调用）。"""
    record['captured_at'] = datetime.now().isoformat()
    record['task'] = 'CostTracker集成（summary方法+agent.py集成+单元测试）'

    filename = f'ch01_{record["agent"].lower().replace(" ", "_")}.json'
    out_path = RESULTS_DIR / filename
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'已保存: {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python ch01_capture.py <claude|codex|deepseek>')
        sys.exit(1)

    agent = sys.argv[1].lower()
    if agent in ('claude', 'codex'):
        name_map = {'claude': 'Claude Code', 'codex': 'Codex CLI'}
        capture_manual(name_map[agent])
    elif agent == 'deepseek':
        print('DeepSeek实验请运行 ch01_run_deepseek.py，结果会自动保存')
    else:
        print(f'未知Agent: {agent}')
