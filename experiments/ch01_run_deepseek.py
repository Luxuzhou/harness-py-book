"""
Ch1实验 Run 3: 用harness_py + DeepSeek跑CostTracker任务
========================================================
自动运行并捕获真实实验数据。

用法: python experiments/ch01_run_deepseek.py
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 加载.env
env_file = ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

TASK = """给harness_py框架的CostTracker模块补充以下功能：

1. 在 src/cost_tracker.py 中给 CostTracker 类添加 summary() 方法，返回一个字典包含：
   - total_calls: 总记录次数
   - total_input_tokens: 输入token总数
   - total_output_tokens: 输出token总数
   - total_cost_usd: 总成本（美元）
   - by_model: 按模型分组的统计

2. 在 harness_py/agent.py 中集成CostTracker：
   - 每次API调用后记录token消耗
   - 在run()结束时将summary写入RunResult.cost_summary

3. 写单元测试 tests/test_cost_tracker.py，覆盖：
   - record()基本功能
   - summary()汇总计算
   - 空记录时的边界情况

完成后运行 python -m pytest tests/test_cost_tracker.py -v 确认全部通过。"""


def main():
    from harness_py import run, ModelConfig, AgentConfig

    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('[FATAL] 未配置API key')
        sys.exit(1)

    print(f'模型: {mc.model}')
    print(f'任务: CostTracker集成')
    print(f'开始时间: {time.strftime("%H:%M:%S")}')

    t0 = time.time()
    result = run(
        TASK,
        model_config=mc,
        agent_config=AgentConfig(
            cwd=ROOT,
            max_iterations=40,
            planning_turns=3,
        ),
    )
    duration = time.time() - t0

    # 自动保存
    from ch01_capture import capture_auto
    capture_auto({
        'agent': 'harness_py+DeepSeek',
        'model': mc.model,
        'turns': result.turns,
        'tool_calls': result.tool_calls,
        'input_tokens': 0,  # harness_py的RunResult里有total_tokens
        'output_tokens': 0,
        'total_tokens': result.total_tokens,
        'duration_seconds': round(duration, 1),
        'cost_usd': 0,
        'test_passed': 'stop' in result.stop_reason,
        'outcome': f'{result.stop_reason}, turns={result.turns}, tools={result.tool_calls}',
    })

    print(f'\n完成: {result.turns}轮, {result.tool_calls}工具, {result.total_tokens:,} tokens, {duration:.1f}s')


if __name__ == '__main__':
    main()
