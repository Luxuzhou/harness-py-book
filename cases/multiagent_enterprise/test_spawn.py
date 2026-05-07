"""
快速验证 agent_spawn 工具：只运行 Architect 角色，观察是否会使用子代理。
"""
import os
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

env_file = REPO_ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from harness_py_pro import ModelConfig
from harness_py_pro.swarm import AgentRole, orchestrate

ch8_root = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
ch9_root = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'

# 读取 Architect 角色 prompt
architect_prompt = (CASE_DIR / 'roles' / 'architect.md').read_text(encoding='utf-8')

# 简化上下文
context = f"""
本任务在两个真实业务代码库上同时进行：
- Java 端（Ch8）：{ch8_root}
- Python 端（Ch9）：{ch9_root}

你需要调查两边的代码结构，然后输出 implementation_plan.md。
为了加快速度，你可以使用 agent_spawn 并行调查两边的代码结构。
"""

roles = [
    AgentRole(
        name='Architect',
        role_prompt=architect_prompt + context,
        tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file', 'agent_spawn',
                     'agent_result', 'agent_wait', 'agent_cancel', 'agent_list',
                     'update_plan', 'checklist_write', 'checklist_update', 'checklist_list',
                     'task_create', 'task_list', 'task_update', 'task_cancel'],
        max_iterations=20,
        planning_turns=0,
        allow_shell=False,
        cwd=CASE_DIR,
        filesystem_roots=['..', '../..'],
    ),
]

task = """
请调查 Java 端和 Python 端的代码结构，了解：
1. Java 端现有的异常预警相关代码（AnomalyService、AnomalyController）
2. Python 端现有的 schemas.py 和异常分析相关代码

输出 implementation_plan.md，包含两边的实施计划。
建议使用 agent_spawn 并行调查两边的代码结构，提高效率。
"""

result = orchestrate(
    task,
    roles,
    model_config=ModelConfig.from_env(),
    cwd=CASE_DIR,
    max_rounds=1,
    verbose=True,
)

print(f'\n=== Result ===')
print(f'Turns: {result.agents_run[0]["turns"]}')
print(f'Tools: {result.agents_run[0]["tool_calls"]}')
print(f'Stop: {result.agents_run[0]["stop_reason"]}')
print(f'Tokens: {result.agents_run[0]["tokens"]:,}')
