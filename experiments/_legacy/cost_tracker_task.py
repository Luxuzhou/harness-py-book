"""
CostTracker集成任务：书中反复引用的核心实验
用法: python experiments/cost_tracker_task.py
需要: .env中的OPENAI_API_KEY + src/cost_tracker.py
"""
import os, sys
from pathlib import Path

for line in (Path(__file__).parent.parent / '.env').read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))
from harness_py.agent import run
from harness_py.config import ModelConfig, AgentConfig

task = (Path(__file__).parent.parent / 'TASK.md').read_text(encoding='utf-8')
result = run(
    task,
    model_config=ModelConfig.from_env(),
    agent_config=AgentConfig(
        cwd=Path(__file__).parent.parent,
        max_iterations=40,
        allow_write=True,
        allow_shell=True,
        planning_turns=3,
    ),
)
print(f'\n结果: turns={result.turns} tools={result.tool_calls} stop={result.stop_reason}')
print(f'\n验证:')
ct = (Path(__file__).parent.parent / 'src' / 'cost_tracker.py').read_text(encoding='utf-8')
print(f'  summary()存在: {"def summary" in ct}')
tests = list((Path(__file__).parent.parent / 'tests').glob('*.py'))
print(f'  测试文件: {[f.name for f in tests]}')
