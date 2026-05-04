"""
规划阶段对比实验：有规划 vs 无规划
用法: python experiments/planning_comparison.py
需要: .env中的OPENAI_API_KEY
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

task = '请读取 harness_py/ 下的所有.py文件，统计每个文件的行数和函数数量，生成一份代码分析报告写入 report.md'

mc = ModelConfig.from_env()
cwd = Path(__file__).parent.parent

# 实验1：无规划
print('=' * 50)
print('实验1：无规划（所有工具从第1轮起可用）')
print('=' * 50)
r1 = run(task, model_config=mc, agent_config=AgentConfig(cwd=cwd, max_iterations=15, planning_turns=0))
print(f'结果: turns={r1.turns} tools={r1.tool_calls}\n')

# 清理
(cwd / 'report.md').unlink(missing_ok=True)

# 实验2：有规划
print('=' * 50)
print('实验2：有规划（前3轮只有只读工具）')
print('=' * 50)
r2 = run(task, model_config=mc, agent_config=AgentConfig(cwd=cwd, max_iterations=15, planning_turns=3))
print(f'结果: turns={r2.turns} tools={r2.tool_calls}\n')

# 对比
print('=' * 50)
print('对比')
print('=' * 50)
print(f'  无规划: {r1.turns}轮 {r1.tool_calls}工具 stop={r1.stop_reason}')
print(f'  有规划: {r2.turns}轮 {r2.tool_calls}工具 stop={r2.stop_reason}')
has_report = (cwd / 'report.md').exists()
print(f'  report.md生成: {has_report}')
