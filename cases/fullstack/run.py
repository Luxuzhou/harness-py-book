"""
Case 3: 多Agent协作全栈开发 — 一键运行脚本
============================================
用法: python cases/fullstack/run.py
需要: .env中的OPENAI_API_KEY
"""

import os
import sys
from pathlib import Path

# 加载.env
project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(project_root))

from harness_py_pro import ModelConfig
from harness_py_pro.swarm import orchestrate, AgentRole

case_dir = Path(__file__).parent
output_dir = case_dir / 'output'
output_dir.mkdir(exist_ok=True)

# 读取需求和角色定义
spec = (case_dir / 'spec.md').read_text(encoding='utf-8')
task = (case_dir / 'TASK.md').read_text(encoding='utf-8')
planner_prompt = (case_dir / 'roles' / 'planner.md').read_text(encoding='utf-8')
generator_prompt = (case_dir / 'roles' / 'generator.md').read_text(encoding='utf-8')
evaluator_prompt = (case_dir / 'roles' / 'evaluator.md').read_text(encoding='utf-8')

# 定义三个角色
roles = [
    AgentRole(
        name='Planner',
        role_prompt=planner_prompt,
        tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file'],
        max_iterations=10,
        planning_turns=1,
        allow_shell=False,
    ),
    AgentRole(
        name='Generator',
        role_prompt=generator_prompt,
        tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search', 'glob_search'],
        max_iterations=20,
        planning_turns=2,
    ),
    AgentRole(
        name='Evaluator',
        role_prompt=evaluator_prompt,
        tool_filter=['read_file', 'grep_search', 'glob_search', 'bash', 'write_file'],
        max_iterations=12,
        planning_turns=1,
        allow_write=True,  # 需要写review.md
    ),
]


def convergence_check(round_num, work_dir):
    """检查是否收敛（Evaluator给出PASS）。"""
    review_file = work_dir / 'output' / 'review.md'
    if not review_file.exists():
        return False, ''

    content = review_file.read_text(encoding='utf-8')
    if 'PASS' in content.upper() and '判定' in content:
        # 提取分数
        import re
        score_match = re.search(r'(\d+)\s*/\s*100', content)
        score = int(score_match.group(1)) if score_match else 0
        if score >= 70:
            return True, f'Evaluator评分 {score}/100 ≥ 70, PASS'
    return False, ''


# 执行编排
result = orchestrate(
    task,
    roles,
    model_config=ModelConfig.from_env(),
    cwd=case_dir,
    max_rounds=3,
    convergence_check=convergence_check,
)

print(f'\n{"="*50}')
print(f'Case 3 完成')
print(f'  总轮次: {result.rounds}')
print(f'  Agent执行记录:')
for ar in result.agents_run:
    print(f'    Round {ar["round"]} {ar["agent"]}: {ar["turns"]} turns, {ar["tool_calls"]} tools, {ar["tokens"]:,} tokens')
print(f'  总Token: {result.total_tokens:,}')
print(f'  最终状态: {result.final_status}')
print(f'\n运行验证: python cases/fullstack/verify.py')
